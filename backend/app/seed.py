import os
from sqlalchemy import select
from .auth import hash_password
from .config import ADMIN_PASSWORD
from .db import Session, User, Project, Requirement, Case, Revision
from .templates import scenario

def seed():
    with Session.begin() as db:
        if db.scalar(select(User).limit(1)): return
        admin=User(username='admin',password_hash=hash_password(ADMIN_PASSWORD),role='admin');db.add(admin);db.flush()
        project=Project(name='Campus Lab · Web 回归测试',description='覆盖账号、课程查询与反馈流程的毕业设计演示项目。8 条种子用例经过人工设计，审核后即可执行。',base_url=os.getenv('DEMO_BASE_URL','http://127.0.0.1:8000'),owner_id=admin.id);db.add(project);db.flush()
        points=[{'id':'REQ-001','text':'有效账号登录成功，错误密码被拒绝'},{'id':'REQ-002','text':'注册邮箱应通过格式校验'},{'id':'REQ-003','text':'按关键词查询课程，无匹配时提示未找到'},{'id':'REQ-004','text':'反馈表单内容必填，合法内容提交成功'}]
        req=Requirement(project_id=project.id,title='Campus Lab 核心业务需求',content='演示应用包括登录、注册、课程查询、反馈表单。登录账号 student，密码 Study123!。有效登录提示“欢迎回来，student”，错误凭据提示“用户名或密码错误”。注册有效邮箱提示“注册成功”，否则“请输入有效邮箱”。查询 Playwright 返回“Playwright 实战”，其他关键词返回“未找到结果”。反馈非空提示“提交成功”，空值提示“请填写反馈内容”。',points=points);db.add(req);db.flush()
        for kind,p in zip(['login','register','search','form'],points):
            for variant in [0,1]:
                case=Case(project_id=project.id,requirement_id=req.id,status='pending',version=1,body=scenario(kind,p['id'],variant));db.add(case);db.flush()
                db.add(Revision(case_id=case.id,actor_id=admin.id,version=1,action='created',body=case.body,note='人工设计种子用例；仍需在界面显式审核'))
