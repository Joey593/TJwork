#!/usr/bin/env python3
"""可复现的受控 DOM 变更实验，不将故意变更造成的失败称为自然偶发失败。"""
import argparse, csv, json, os, time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8000/demo/');p.add_argument('--repeats',type=int,default=20);p.add_argument('--output',default='experiments/results/locator-stability');args=p.parse_args()
output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);rows=[]
with sync_playwright() as driver:
    opts={'headless':True}
    if os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE'): opts['executable_path']=os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE')
    browser=driver.chromium.launch(**opts)
    for method in ['css','xpath','semantic']:
        for i in range(args.repeats):
            context=browser.new_context();page=context.new_page();page.set_default_timeout(600)
            start=time.perf_counter();error='';passed=False;mutated=i%2==1
            try:
                page.goto(args.url)
                # 原始旧选择器在变更前有效。变更只重命名样式 class 和 id，不改变业务或语义。
                page.evaluate("""() => { const b=[...document.querySelectorAll('button')].find(e=>e.textContent==='登录'); b.id='legacy-submit'; b.className='legacy-login-button'; }""")
                if mutated: page.evaluate("""() => { const b=document.getElementById('legacy-submit'); b.id='refactored-submit'; b.className='refactored-primary'; }""")
                page.get_by_label('用户名',exact=True).fill('student');page.get_by_label('密码',exact=True).fill('Study123!')
                if method=='css': page.locator('.legacy-login-button').click()
                elif method=='xpath': page.locator('xpath=//*[@id="legacy-submit"]').click()
                else: page.get_by_role('button',name='登录',exact=True).click()
                expect(page.get_by_test_id('login-result')).to_have_text('欢迎回来，student');passed=True
            except Exception as exc: error=str(exc)
            rows.append({'method':method,'iteration':i+1,'controlled_dom_mutation':mutated,'passed':passed,'duration_ms':round((time.perf_counter()-start)*1000),'error':error})
            context.close()
    browser.close()
with output.with_suffix('.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
summary={'experiment':'controlled DOM selector mutation, not natural flakiness','url':args.url,'repeats_per_method':args.repeats,'results':{m:{'passed':sum(r['passed'] for r in rows if r['method']==m),'total':args.repeats} for m in ['css','xpath','semantic']},'raw_csv':str(output.with_suffix('.csv'))}
output.with_suffix('.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
