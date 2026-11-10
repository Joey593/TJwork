# Aurora Test · 融合大语言模型的 Web 智能自动化测试平台

本工程现托管于 [Joey593/TJwork](https://github.com/Joey593/TJwork)。当前云会话的工作目录为 `/workspace/TJwork`；后续项目开发在该仓库中进行。见 [云环境使用说明](docs/云环境使用说明.md)。

按《毕业论文任务书（正式）》与《毕业论文开题报告（正式）》实现的毕业设计工程。采用 **Vue 3 + FastAPI + SQLAlchemy/MySQL + Playwright + pytest**，提供需求输入、候选生成、人工审核、异步执行、失败证据、报告与实验采集的闭环。

不是仅展示页面：所有统计由 API 查询数据库计算，任务通过独立 pytest 子进程启动真实浏览器。未配置大模型时明确显示未配置，可使用确定性规则基线。

## 运行

### 方式一：Docker + MySQL（推荐部署方式）

需要 Docker Engine / Docker Desktop 与 Compose v2。进入本目录：

```bash
cp .env.example .env
# 按需修改 .env 中的初始密码、MySQL 密码和大模型配置
# 数据库连接串中的密码如含 @ / : 等保留字符，需做 URL 编码。
docker compose up --build -d
```

打开 http://localhost:8000 。API 文档：http://localhost:8000/docs 。演示被测系统：http://localhost:8000/demo/ 。

初始管理员：`admin / Admin12345!`，仅首次空数据库初始化时读取 `ADMIN_PASSWORD`。MySQL 与平台证据分别保存在 `mysql-data`、`platform-data` 卷中。修改 `.env` 不会重置既有账号的密码。不要将实际 `.env` 提交到仓库。

```bash
docker compose logs -f platform
docker compose down
# 不带 -v 停止不会删除数据；需要保留实验数据时勿删除卷。
```

### 方式二：本地快速演示（SQLite）

Python 3.12、Node.js 22.12+ 或 24+。Linux/macOS：`bash start.sh`；Windows PowerShell：`.\start.ps1`。

手工启动：

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows: .venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
python -m playwright install chromium firefox webkit
# Linux 若缺少浏览器系统依赖：python -m playwright install-deps
cp .env.example .env
cd frontend
npm ci
npm run build
cd ../backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

开发前端可另外运行 `cd frontend && npm run dev`，访问 http://localhost:5173 ，Vite 会代理 API 到 8000。生产构建由 FastAPI 同源托管。

默认 SQLite 用于零数据库依赖演示。MySQL 在 `.env` 设置：

```dotenv
DATABASE_URL=mysql+pymysql://aurora:your-url-encoded-password@127.0.0.1:3306/aurora?charset=utf8mb4
```

SQLAlchemy 自动创建初始表，MySQL 数据库需先创建。当前版本是单实例平台，**只运行一个 API worker、一个平台容器**，不支持多实例争抢队列。

## 首次演示流程

1. 登录后打开「需求管理」，查看 4 个业务需求点。
2. 打开「测试用例」，逐条查看 8 条人工设计的种子用例与脚本。以管理员/审核员提交审核意见并批准。
3. 打开「测试任务」→「新建测试任务」，选择已批准用例，使用 Chromium 创建任务。
4. 查看执行状态、逐步日志、Trace、JUnit 和 HTML/CSV/JSON 报告。
5. 创建新需求后使用「AI 用例生成」。选择规则基线可离线演示；配置真实模型后可比较直接 LLM 与规则约束 + LLM。
6. 生成用例只进入待审核集合。审核后才能执行；编辑任何已有用例都会增加版本并重置为待审核。
7. 按下文实验脚本创建预置缺陷场景，查看失败截图与 AI/规则候选原因。

演示被测系统账号 `student / Study123!`。`/demo/?bug=login`、`register`、`search`、`form` 分别打开可复现缺陷。用例保持正确业务预期，故意失败才代表检出预置缺陷。

## 大模型配置

服务端 `.env`：

```dotenv
LLM_API_KEY=your-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

支持 OpenAI 兼容 `/chat/completions` 与 JSON Object 响应。需供应商支持 `response_format: {type: json_object}`。重启后在「平台设置」查看配置状态。密钥不返回前端、不进入 pytest 子进程。

三组生成方法都接受同样字段验证和执行门禁，以保证安全性和评价口径一致；约束组额外加入覆盖、边界、语义定位与去重规则。保存 Prompt 版本、完整提示、模型名、SHA-256 输入哈希、耗时、原始响应、校验错误、组内与库内重复数。

失败分析仅给出**候选原因**，支持规则、直接 LLM、规则 + LLM。模型服务不可用会返回明确错误，不会冒充真实 AI 结果。本次交付未使用实际模型密钥，LLM 效果实验留待配置后运行。

## 用例脚本

用例是通过 Pydantic 校验的 JSON，包含需求点编号、标题、前置条件、自然语言步骤、测试数据、预期、优先级、场景类型和声明式脚本。示例见 `docs/case-schema.json`、`docs/example-case.json`。

允许动作：`goto / fill / click / check / select / expect_text / expect_visible / expect_url`；允许定位：`role / label / text / test_id / css / xpath`。第一步必须站内 `goto`，至少有一条断言。不会执行模型生成的 Python，也不使用 `eval/exec`。典型场景映射在 `backend/app/templates.py`；统一页面对象在 `backend/runner/pom.py`。

自定义被测站点需由工程师提供实际页面契约，并在 JSON 编辑器维护步骤/Locator；本平台不具备自动理解任意网站的自主 Agent 能力。语义 Locator 优先，CSS/XPath 用于兼容和对比实验。

## 测试与实验

```bash
cd backend
python -m pytest tests -q
cd ../frontend
npm ci && npm run build
cd ..
python experiments/ci_smoke.py
```

`ci_smoke.py` 针对已维护的固定人工基线执行真实浏览器脚本，不会批准平台 AI 候选。

启动平台后：

```bash
# 密码通过交互输入，或临时环境变量 AURORA_PASSWORD 传入。
python experiments/collect.py --suite prepare
# 该步骤仅创建24条待审核人工基线，请在平台逐条核对并批准。
python experiments/collect.py --suite acceptance
python experiments/collect.py --suite generation
python experiments/locator_stability.py --repeats 20
python experiments/failure_analysis.py
```

如使用已安装的本机 Chromium，可设置 `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium`；未设置时使用 Playwright 自己的浏览器。FireFox/WebKit 必须安装对应 Playwright 浏览器及系统依赖。

验收包括：20 条用例批量执行、单例重复 20 次、四类预置缺陷检出、失败截图和 Trace 的认证下载。创建 API 测量不包含实际浏览器执行时间。原始 JSON/CSV 和证据保存在 `experiments/results/`。验收数据见 `docs/验收报告.md`。

GitHub Actions 配置位于 `.github/workflows/ci.yml`，含 API 测试、Vue 构建和 Chromium/Firefox/WebKit 矩阵；源码上传到 GitHub 后即可触发。未声称已在远程仓库运行 CI。

## 目录

```text
backend/app/            API、认证、数据模型、生成校验、持久化队列
backend/runner/         pytest Fixture、参数化、POM、证据钩子
backend/tests/          API、审核门禁、版本追踪等测试
frontend/src/          Vue 3 管理平台与响应式样式
experiments/           实验准备、采集、定位与失败分类对比
experiments/results/   本次真实采集数据与部分证据
qa/                    浏览器截图、API/MySQL 验证记录
.github/workflows/     持续集成工作流
Dockerfile             包含浏览器的前后端镜像
compose.yaml           MySQL 8.4 + 平台 + 持久化卷
start.sh / start.ps1   本地启动脚本
docs/                  架构、需求映射、Schema、实验方案、验收与答辩指引
```

## 实现边界

- 角色权限是共享工作空间的全局 RBAC：管理员、审核员、测试工程师、只读成员；未实现企业多租户与项目成员隔离。
- 队列采用数据库 + 单调度线程 + 隔离 pytest 子进程；意外重启将活动任务标记为 interrupted，不自动认定通过。任务可取消，超时与异常有明确状态。
- 截图仅失败时保存，Trace 成功/失败均保存；浏览器启动前失败时无法截图，错误堆栈与执行器日志仍可查询。
- 「执行耗时」是用例阶段耗时之和；pytest 墙钟时间还包含启动、上下文清理和证据保存，不能混为一谈。
- 直接生成与约束生成、失败分类的真实模型实验，以及人工修订计时需进一步采集。论文应如实引用现有原始数据，不能填造未做实验。
- 全文论文、正式 PPT 和录屏不属于本次“平台实现”交付；随附章节建议与答辩演示路线，供后续制作使用。

界面截图为本次验收后的真实运行状态；首次空数据库只提供 8 条待审核种子。完整镜像构建在本环境遇到磁盘 ENOSPC，MySQL 单独验证已通过；详情见验收报告。
