from urllib.parse import urlsplit
from playwright.sync_api import expect

class ScenarioPage:
    """声明式用例的页面对象；定位与动作规则集中管理。"""
    def __init__(self, page, base_url):
        self.page=page
        self.base_url=base_url.rstrip('/')
        self.origin=urlsplit(base_url)
    def locator(self, specification):
        by=specification['by']; value=specification['value']; name=specification.get('name')
        if by=='role': return self.page.get_by_role(value, **({'name':name,'exact':True} if name else {}))
        if by=='label': return self.page.get_by_label(value,exact=True)
        if by=='text': return self.page.get_by_text(value,exact=True)
        if by=='test_id': return self.page.get_by_test_id(value)
        return self.page.locator(('xpath=' if by=='xpath' else '')+value)
    def perform(self, step):
        action=step['action'];value=step.get('value','')
        if action=='goto': self.page.goto(self.base_url+value,wait_until='domcontentloaded');return
        if action=='expect_url': expect(self.page).to_have_url(self.base_url+value);return
        locator=self.locator(step['locator'])
        if action=='fill': locator.fill(value)
        elif action=='click': locator.click()
        elif action=='check': locator.check()
        elif action=='select': locator.select_option(value)
        elif action=='expect_text': expect(locator).to_have_text(value)
        elif action=='expect_visible': expect(locator).to_be_visible()
        else: raise ValueError('Unsupported action')
