import time
import pytest

@pytest.mark.regression
def test_declarative_scenario(scenario_page, case_item, request):
    for index, step in enumerate(case_item['body']['script']):
        entry={'index':index+1,'action':step['action'],'locator':step.get('locator'),'status':'running'}
        request.node.steps.append(entry)
        started=time.perf_counter()
        try:
            scenario_page.perform(step)
            entry['status']='passed'
        except Exception:
            entry['status']='failed'
            raise
        finally:
            entry['duration_ms']=round((time.perf_counter()-started)*1000)
