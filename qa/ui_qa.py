import json,time,os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'qa';out.mkdir(exist_ok=True)
checks=[];errors=[]; UI_STAMP=str(int(time.time())); UI_TITLE='浏览器操作验收需求-'+UI_STAMP; UI_POINT='UI-QA-'+UI_STAMP
with sync_playwright() as p:
 options={'headless':True}
 executable=os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE')
 if executable: options['executable_path']=executable
 b=p.chromium.launch(**options)
 page=b.new_page(viewport={'width':1440,'height':1080},device_scale_factor=1)
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8000');page.get_by_label('密码',exact=True).fill(os.getenv('AURORA_PASSWORD','Admin12345!'));page.get_by_role('button',name='登录工作空间').click();page.wait_for_selector('.welcome-banner')
 for name in ['需求管理','测试用例','AI 用例生成','测试任务','报告与追踪','对比实验','平台设置','工作概览']:
  page.locator('nav button').filter(has_text=name).click();expect(page.locator('.page-heading h1')).to_contain_text(name);checks.append('navigation:'+name)
 page.locator('nav button').filter(has_text='需求管理').click();page.get_by_role('button',name='新增需求',exact=True).click()
 dialog=page.get_by_role('dialog');dialog.get_by_label('需求标题').fill(UI_TITLE)
 dialog.get_by_label('业务描述').fill('有效登录账号 student / Study123! 应提示欢迎回来，student。')
 dialog.get_by_label('需求点（每行：编号 | 描述）').fill(UI_POINT+' | 有效账号登录成功')
 dialog.get_by_role('button',name='保存',exact=True).click();expect(page.get_by_role('dialog')).to_have_count(0)
 page.locator('nav button').filter(has_text='AI 用例生成').click()
 page.get_by_label('关联需求',exact=True).select_option(label=UI_TITLE);page.get_by_label('候选用例数').fill('1')
 page.get_by_role('button',name='生成候选测试用例').click();expect(page.get_by_text('生成处理完成',exact=True)).to_be_visible(timeout=15000);checks.append('generation:real rules API')
 page.screenshot(path=str(out/'ai-generation.png'),full_page=True)
 page.get_by_role('button',name='前往人工审核').click()
 row=page.locator('tbody tr').filter(has_text=UI_POINT);expect(row).to_have_count(1);row.get_by_role('button',name='审核',exact=True).click()
 dialog=page.get_by_role('dialog');dialog.get_by_label('审核意见').fill('逐项检查业务预期、登录数据与可执行步骤，确认一致。')
 dialog.get_by_role('button',name='提交审核决定').click();expect(page.get_by_role('dialog')).to_have_count(0)
 page.locator('.tabs button').filter(has_text='已通过').click();row=page.locator('tbody tr').filter(has_text=UI_POINT);expect(row).to_have_count(1);row.get_by_role('checkbox').check();checks.append('manual review:approved')
 page.get_by_role('button',name='创建执行任务',exact=True).click();dialog=page.get_by_role('dialog');dialog.get_by_label('任务名称').fill('界面端到端验收')
 dialog.get_by_role('button',name='创建并执行').click();expect(page.get_by_role('dialog')).to_have_count(0)
 row=page.locator('tbody tr').filter(has_text='界面端到端验收');expect(row.locator('.badge')).to_contain_text('通过',timeout=45000);checks.append('UI task:create + browser passed')
 row.get_by_role('button',name='查看详情',exact=True).click();dialog=page.get_by_role('dialog');expect(dialog.get_by_text('所有步骤与断言均已通过。')).to_be_visible()
 with page.expect_download() as download:
  dialog.get_by_role('button',name='HTML 报告',exact=True).click()
 download.value.save_as(str(out/'ui-report.html'));checks.append('report:authenticated HTML download')
 dialog.get_by_role('button',name='关闭弹窗').click()
 row=page.locator('tbody tr').filter(has_text='四类预置缺陷检出');row.get_by_role('button',name='查看详情',exact=True).click();dialog=page.get_by_role('dialog')
 dialog.get_by_role('button',name='分析失败日志',exact=True).click();expect(dialog.locator('.analysis-output')).to_be_visible(timeout=15000)
 with page.expect_download() as download: dialog.get_by_role('button',name='失败截图',exact=True).click()
 download.value.save_as(str(out/'ui-failure-download.png'));checks.append('failure:rules analysis + screenshot download')
 page.screenshot(path=str(out/'failure-analysis.png'),full_page=True)
 dialog.get_by_role('button',name='关闭弹窗').click()
 page.locator('nav button').filter(has_text='工作概览').click();page.screenshot(path=str(out/'overview.png'),full_page=True)
 page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(out/'mobile.png'),full_page=True)
 assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'mobile horizontal overflow'
 checks.append('mobile:390px no document overflow')
 b.close()
assert not errors,errors
(out/'ui-checks.json').write_text(json.dumps({'checks':checks,'page_errors':errors},ensure_ascii=False,indent=2));print(json.dumps(checks,ensure_ascii=False,indent=2))
