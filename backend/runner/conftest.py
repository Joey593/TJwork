import json, os, time, traceback
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright

JOB=Path(os.environ['AURORA_JOB'])
SPEC=json.loads((JOB/'spec.json').read_text())

def pytest_generate_tests(metafunc):
    if 'case_item' in metafunc.fixturenames:
        metafunc.parametrize('case_item',[pytest.param(i,marks=pytest.mark.smoke) if i['body']['priority']=='P0' else i for i in SPEC['items']],ids=[f"{i['ordinal']:04d}-{i['case_id'][:8]}" for i in SPEC['items']])

@pytest.fixture(scope='session')
def browser():
    with sync_playwright() as p:
        kind=SPEC['browser']
        options={'headless':True}
        executable=os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE')
        if kind=='chromium' and executable: options['executable_path']=executable
        b=getattr(p,kind).launch(**options)
        yield b
        b.close()

@pytest.fixture
def scenario_page(browser, case_item, request):
    context=browser.new_context(viewport={'width':1280,'height':800},locale='zh-CN')
    context.set_default_timeout(5000)
    context.tracing.start(screenshots=True,snapshots=True,sources=True)
    page=context.new_page()
    from runner.pom import ScenarioPage
    request.node.page=page
    request.node.context=context
    request.node.steps=[]
    yield ScenarioPage(page,SPEC['base_url'])
    # makereport 已保存证据。fixture 始终释放隔离上下文。
    context.close()

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome=yield
    report=outcome.get_result()
    if report.when=='setup': item.started=time.perf_counter()
    if report.when not in ('setup','call') or (report.when=='setup' and not report.failed): return
    case_item=item.callspec.params['case_item']
    ordinal=case_item['ordinal'];prefix=f'{ordinal:04d}'
    failed=report.failed
    evidence={'title':case_item['body']['title'],'case_version':case_item['version'],'requirement_points':case_item['body']['requirement_points'],'error':str(report.longrepr) if failed else '', 'steps':getattr(item,'steps',[])}
    page=getattr(item,'page',None);context=getattr(item,'context',None)
    if failed and page:
        try:
            page.screenshot(path=str(JOB/f'{prefix}.png'),full_page=True,timeout=5000)
            evidence['screenshot']=f'{prefix}.png'
        except Exception as exc: evidence['screenshot_error']=str(exc)
    if context:
        try:
            context.tracing.stop(path=str(JOB/f'{prefix}.trace.zip'))
            evidence['trace']=f'{prefix}.trace.zip'
        except Exception as exc: evidence['trace_error']=str(exc)
    record={'case_id':case_item['case_id'],'ordinal':ordinal,'status':'failed' if failed else 'passed','duration_ms':round((time.perf_counter()-getattr(item,'started',time.perf_counter()))*1000),'evidence':evidence}
    temporary=JOB/f'{prefix}.result.tmp'
    temporary.write_text(json.dumps(record,ensure_ascii=False))
    temporary.replace(JOB/f'{prefix}.result.json')
