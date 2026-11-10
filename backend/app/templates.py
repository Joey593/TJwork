"""可审查的演示场景映射；只产出声明式步骤，不拼接 Python。"""
def loc(by, value, name=None):
    d={'by':by,'value':value}
    if name: d['name']=name
    return d

def step(action, value='', locator=None):
    d={'action':action,'value':value}
    if locator: d['locator']=locator
    return d

def scenario(kind, point, variant=0):
    goto=step('goto','/demo/')
    if kind=='login':
        bad=variant%2==1
        data={'username':'student','password':'wrong' if bad else 'Study123!'}
        expected='用户名或密码错误' if bad else '欢迎回来，student'
        script=[goto,step('fill',data['username'],loc('label','用户名')),step('fill',data['password'],loc('label','密码')),step('click',locator=loc('role','button','登录')),step('expect_text',expected,loc('test_id','login-result'))]
        title='错误密码被拒绝' if bad else '有效账号成功登录'
    elif kind=='register':
        data={'email':'invalid-email' if variant%2 else 'student@example.com'}
        expected='请输入有效邮箱' if variant%2 else '注册成功'
        script=[goto,step('fill',data['email'],loc('label','注册邮箱')),step('click',locator=loc('role','button','注册')),step('expect_text',expected,loc('test_id','register-result'))]
        title='注册邮箱格式校验' if variant%2 else '有效邮箱注册成功'
    elif kind=='search':
        data={'query':'不存在的产品' if variant%2 else 'Playwright'}
        expected='未找到结果' if variant%2 else 'Playwright 实战'
        script=[goto,step('fill',data['query'],loc('label','搜索关键词')),step('click',locator=loc('role','button','查询')),step('expect_text',expected,loc('test_id','search-result'))]
        title='无匹配结果提示' if variant%2 else '按关键词查询课程'
    else:
        kind='form';data={'message':'' if variant%2 else '自动化测试反馈'}
        expected='请填写反馈内容' if variant%2 else '提交成功'
        script=[goto,step('fill',data['message'],loc('label','反馈内容')),step('click',locator=loc('role','button','提交反馈')),step('expect_text',expected,loc('test_id','form-result'))]
        title='空表单禁止提交' if variant%2 else '有效反馈提交成功'
    return {'title':title,'requirement_points':[point],'preconditions':'演示被测站点可访问；每条用例使用独立 Browser Context','steps':['访问演示站点','输入测试数据','提交并校验提示'],'test_data':data,'expected_result':expected,'priority':'P1','scenario':kind,'script':script}
