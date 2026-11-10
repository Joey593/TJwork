"""单实例持久化队列。HTTP 创建任务仅入库，独立调度线程执行 pytest 子进程。"""
import json, os, signal, subprocess, sys, threading, time
from pathlib import Path
from sqlalchemy import select, update
from .db import Session, Run, Result, now
from .config import ARTIFACTS

class Dispatcher:
    def __init__(self):
        self.stop_event=threading.Event()
        self.thread=None
        self.process=None
    def start(self):
        # 意外退出不能将旧任务标记为通过。
        with Session.begin() as db:
            for run in db.scalars(select(Run).where(Run.status.in_(['running','cancelling']))):
                run.status='interrupted';run.finished_at=now();run.summary={**run.summary,'error':'服务重启中断，请重新创建任务'}
        self.thread=threading.Thread(target=self.loop,daemon=True,name='pytest-dispatcher');self.thread.start()
    def close(self):
        self.stop_event.set()
        if self.process and self.process.poll() is None: self.terminate(self.process)
        if self.thread: self.thread.join(timeout=8)
    @staticmethod
    def terminate(proc):
        try:
            if os.name=='posix': os.killpg(proc.pid,signal.SIGTERM)
            else: proc.terminate()
        except ProcessLookupError: pass
    def loop(self):
        while not self.stop_event.wait(.25):
            with Session() as db:
                run=db.scalar(select(Run).where(Run.status=='queued').order_by(Run.created_at).limit(1))
                run_id=run.id if run else None
            if run_id:
                try: self.execute(run_id)
                except Exception as exc:
                    with Session.begin() as db:
                        run=db.get(Run,run_id);run.status='error';run.finished_at=now();run.summary={**run.summary,'error':str(exc)}
    def sync_results(self,db,run,job):
        existing=set(db.scalars(select(Result.ordinal).where(Result.run_id==run.id)))
        for file in sorted(job.glob('*.result.json')):
            data=json.loads(file.read_text())
            if data['ordinal'] not in existing:
                db.add(Result(run_id=run.id,**data));existing.add(data['ordinal'])
        db.flush()
        results=list(db.scalars(select(Result).where(Result.run_id==run.id)))
        run.summary={'total':len(run.snapshot['items']),'completed':len(results),'passed':sum(r.status=='passed' for r in results),'failed':sum(r.status=='failed' for r in results),'skipped':sum(r.status=='skipped' for r in results),'duration_ms':sum(r.duration_ms for r in results)}
    def execute(self,run_id):
        job=ARTIFACTS/run_id;job.mkdir(exist_ok=True)
        with Session.begin() as db:
            run=db.get(Run,run_id)
            claimed=db.execute(update(Run).where(Run.id==run_id,Run.status=='queued').values(status='running',started_at=now()))
            if claimed.rowcount!=1: return
            db.refresh(run)
            spec={**run.snapshot,'browser':run.browser}
            (job/'spec.json').write_text(json.dumps(spec,ensure_ascii=False))
        env=os.environ.copy();env['AURORA_JOB']=str(job)
        # pytest 不需要数据库密码、JWT 或大模型密钥。
        for key in ['LLM_API_KEY','JWT_SECRET','ADMIN_PASSWORD','DATABASE_URL']:
            env.pop(key,None)
        cancelled=False;timed_out=False
        with (job/'pytest.log').open('w') as log:
            self.process=subprocess.Popen([sys.executable,'-m','pytest','runner/test_scenarios.py','-q','--tb=short','--junitxml='+str(job/'junit.xml')],cwd=Path(__file__).resolve().parents[1],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=os.name=='posix')
            started=time.monotonic()
            limit=60+len(spec['items'])*40
            while self.process.poll() is None:
                with Session.begin() as db:
                    run=db.get(Run,run_id);self.sync_results(db,run,job)
                    cancelled=run.status=='cancelling' or self.stop_event.is_set()
                timed_out=time.monotonic()-started>limit
                if cancelled or timed_out:
                    self.terminate(self.process)
                    try: self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        if os.name=='posix': os.killpg(self.process.pid,signal.SIGKILL)
                        else: self.process.kill()
                    break
                self.stop_event.wait(.4)
            exit_code=self.process.wait()
        self.process=None
        with Session.begin() as db:
            run=db.get(Run,run_id);self.sync_results(db,run,job)
            cancelled=cancelled or run.status=='cancelling'
            existing=set(db.scalars(select(Result.ordinal).where(Result.run_id==run_id)))
            for item in spec['items']:
                if item['ordinal'] not in existing:
                    reason='任务被取消' if cancelled else '执行超时' if timed_out else 'pytest 异常退出，请检查 pytest.log'
                    db.add(Result(run_id=run_id,case_id=item['case_id'],ordinal=item['ordinal'],status='skipped' if cancelled else 'failed',duration_ms=0,evidence={'title':item['body']['title'],'case_version':item['version'],'error':reason,'runner_log':'pytest.log','requirement_points':item['body']['requirement_points']}))
            db.flush();self.sync_results(db,run,job)
            run.status='cancelled' if cancelled else 'error' if timed_out or exit_code not in (0,1) else 'failed' if run.summary['failed'] else 'passed'
            run.finished_at=now()
            run.summary={**run.summary,'exit_code':exit_code,'runner_log':'pytest.log','junit':'junit.xml'}
