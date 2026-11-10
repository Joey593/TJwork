from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
class Login(Strict):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)
class UserIn(Login):
    password: str = Field(min_length=10, max_length=200)
    role: Literal['admin','reviewer','tester','viewer'] = 'tester'
class ProjectIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default='', max_length=5000)
    base_url: str = Field(max_length=500)
    @field_validator('base_url')
    @classmethod
    def http_url(cls, v):
        u = urlsplit(v)
        if u.scheme not in ('http','https') or not u.hostname or u.username or u.password or u.fragment or u.query:
            raise ValueError('目标必须是不含认证、查询或片段的 HTTP(S) 地址')
        return v.rstrip('/')
class Point(Strict):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,40}$')
    text: str = Field(min_length=1, max_length=2000)
class RequirementIn(Strict):
    project_id: str
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20000)
    points: list[Point] = Field(min_length=1, max_length=100)
    @field_validator('points')
    @classmethod
    def unique_points(cls,v):
        if len({p.id for p in v}) != len(v): raise ValueError('需求点编号不能重复')
        return v
class Locator(Strict):
    by: Literal['role','label','text','test_id','css','xpath']
    value: str = Field(min_length=1, max_length=500)
    name: str | None = Field(default=None, max_length=200)
class Step(Strict):
    action: Literal['goto','fill','click','check','select','expect_text','expect_visible','expect_url']
    locator: Locator | None = None
    value: str = Field(default='', max_length=2000)
    @model_validator(mode='after')
    def valid_step(self):
        if self.action == 'goto':
            if not self.value.startswith('/') or self.value.startswith('//') or '\\' in self.value or any(ord(c)<32 for c in self.value):
                raise ValueError('goto 只能使用目标站点内的相对路径')
        elif self.action != 'expect_url' and self.locator is None:
            raise ValueError('此操作需要 locator')
        return self
class CaseBody(Strict):
    title: str = Field(min_length=1, max_length=200)
    requirement_points: list[str] = Field(min_length=1, max_length=100)
    preconditions: str = Field(min_length=1, max_length=2000)
    steps: list[str] = Field(min_length=1, max_length=50)
    test_data: dict = Field(default_factory=dict)
    expected_result: str = Field(min_length=1, max_length=3000)
    priority: Literal['P0','P1','P2','P3'] = 'P1'
    scenario: Literal['login','register','search','form','custom'] = 'custom'
    script: list[Step] = Field(min_length=2, max_length=60)
    @model_validator(mode='after')
    def assert_script(self):
        if self.script[0].action != 'goto': raise ValueError('脚本第一步必须为 goto')
        if not any(s.action.startswith('expect_') for s in self.script): raise ValueError('脚本必须包含可执行断言')
        return self
class CaseIn(Strict):
    project_id: str
    requirement_id: str
    body: CaseBody
class CaseEdit(Strict):
    version: int = Field(ge=1)
    body: CaseBody
    note: str = Field(default='', max_length=2000)
class ReviewIn(Strict):
    version: int = Field(ge=1)
    decision: Literal['approved','rejected']
    note: str = Field(min_length=1, max_length=2000)
class GenerateIn(Strict):
    requirement_id: str
    method: Literal['rules','direct_llm','constrained_llm'] = 'constrained_llm'
    count: int = Field(default=4, ge=1, le=20)
class RunIn(Strict):
    project_id: str
    name: str = Field(default='回归测试', min_length=1, max_length=160)
    case_ids: list[str] = Field(min_length=1, max_length=100)
    browser: Literal['chromium','firefox','webkit'] = 'chromium'
    repeat: int = Field(default=1, ge=1, le=20)
    @model_validator(mode='after')
    def max_tasks(self):
        if len(set(self.case_ids)) != len(self.case_ids): raise ValueError('用例编号不能重复')
        if len(self.case_ids)*self.repeat > 200: raise ValueError('单个任务最多 200 次用例执行')
        return self
class AnalyzeIn(Strict):
    method: Literal['rules','direct_llm','constrained_llm'] = 'rules'
class Observation(Strict):
    requirement_total: int = Field(ge=1)
    covered_points: int = Field(ge=0)
    generated: int = Field(ge=1)
    valid: int = Field(ge=0)
    executable: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    defects_total: int = Field(ge=0)
    defects_detected: int = Field(ge=0)
    revision_seconds: float = Field(ge=0)
    generation_ms: int = Field(ge=0)
    evidence_ref: str = Field(min_length=1, max_length=2000)
    @model_validator(mode='after')
    def check_counts(self):
        if self.covered_points>self.requirement_total or self.valid>self.generated or self.executable>self.valid or self.duplicates>self.generated or self.defects_detected>self.defects_total:
            raise ValueError('计数分子不能大于分母，且可执行数不得大于结构有效数')
        return self
class ExperimentIn(Strict):
    project_id: str
    name: str = Field(min_length=1, max_length=160)
    method: Literal['rules','direct_llm','constrained_llm']
    observations: Observation
