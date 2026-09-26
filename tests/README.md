# tests/ —— 测试与隔离夹具

> 用途：说明 190 个用例分布在哪、夹具如何隔离副作用、加测试该照哪个样子写。

评测系统自己先要可信，所以这里覆盖到三层：
数据结构与存储的单元断言、判分与管线的算法断言、走真实鉴权流程的接口断言，
外加真起 uvicorn 的 SDK 集成、离线 Mock 下的 LLM 全链路、PWA 资产校验。

跑法（`python -m pytest` 与裸 `pytest` 都可用，靠 `pyproject.toml` 的 `pythonpath = ["."]`）：

```bash
python -m pytest -q                            # 全部,预期 190 passed
python -m pytest tests/test_webapp.py -q       # 只跑某个文件
python -m pytest tests/test_judge.py -q -k metric   # 只跑匹配的用例
python -m pytest --collect-only -q             # 只看分布
```

## 用例分布（复核：`python -m pytest --collect-only -q`）

| 文件 | 例数 | 覆盖什么 |
| --- | --- | --- |
| `test_settings_api.py` | 37 | `/api/settings` 准入（默认拒绝、本机直连 vs 会话、机器令牌不算）、密钥掩码、原子写与「重启才生效」边界、`SETTING_SPECS` 单测 |
| `test_webapp.py` | 34 | 三种凭据各自的通行路径、401/429、评测集选择、用例生命周期、评测与自进化端点、路径穿越被拒、`/` 与 `/help` 可服务、checks 级差分 |
| `test_llm.py` | 27 | Runtime 配置/缓存/审计/JSON 容错、LLMJudge 打分与故障降级、草稿工作流、诊断工作流与幻觉过滤、API 全链路（全程离线 Mock） |
| `test_auth.py` | 14 | PBKDF2 哈希、旧哈希透明升级、登录限流与锁定剩余秒数、HMAC 令牌签发/校验/过期 |
| `test_judge.py` | 14 | 每种 `checks.type` 的判分语义与 `CompositeJudge` 路由（含无 judge 支持时的失败） |
| `test_versions.py` | 14 | v0 已知缺陷的负断言、v1/v2 的分级与数值行为、空数据与缺数据降级 |
| `test_storage.py` | 9 | 名称白名单与路径安全、沉淀/删除与评测集清单一致性、原子写 |
| `test_pwa.py` | 7 | `/sw.js` 从根路径提供、页面注册 SW、manifest 可安装字段、图标尺寸与 maskable 不透明（用 `Pillow`） |
| `test_sdk.py` | 13 | 线程内真起 uvicorn（随机空闲端口）走 SDK → TCP → 中间件 → 端点 → 判分的完整链路，含 CLI 退出码 |
| `test_evolve.py` | 5 | 自进化闭环：逐轮提升、无回归、归档齐全（在临时目录跑真数据） |
| `test_report.py` | 5 | 差分容错（评测集扩充后不 KeyError）、payload、Markdown 渲染 |
| `test_activity.py` | 4 | 活动流聚合、时间归一排序、limit 钳制、草稿注入 |
| `test_runner.py` | 3 | 崩溃捕获、分标签统计、耗时 |
| `test_models.py` | 4 | `to_dict`/`from_dict` 往返一致 |

## 文件清单

| 文件 | 干什么 | 备注 |
| --- | --- | --- |
| `conftest.py` | 全部共享夹具与测试凭据 | 见下节 |
| `fixtures/cases/<标签>/<case_id>.json` | 冻结的种子资产快照（17 个文件，比 `cases/` 多一条 `结论缺失/rc-0014`） | 测试的唯一用例来源，改动会影响 190 例的断言基线 |
| `fixtures/evalsets/*.json` | 与快照配套的清单（`evalset_v1` 13 条、`evalset_scenario_rain` 3 条） | 快照多出的 `rc-0014` **不在**清单里，用于断言「沉淀后编号递增且自动入集」 |
| `test_*.py` | 上表 14 个测试文件 | 命名固定 `test_<模块>.py`，`testpaths = ["tests"]` |

## 夹具怎么保证不污染真实环境

| 夹具 | 隔离了什么 |
| --- | --- |
| `_hermetic_dotenv`（autouse） | 把 `settings_mod.ENV_FILE`/`BACKUP_DIR` 指到 `tmp_path`，并在用例后还原被改过的环境变量 —— 否则 `/api/settings` 的测试会写到你本机真实 `.env` |
| `_reset_login_guard`（autouse） | 逐用例清空进程内登录限流状态，避免用例间互相锁定 |
| `hermetic_storage` | `cases`/`evalsets`/`reports` 三个目录重定向到 `tmp_path`（从 `fixtures/` 拷快照）；`pipeline/data` 保持真实只读 |
| `make_client(client_host=...)` | 造 `TestClient` 并决定 TCP 对端地址；同时清掉 `LLM_*` 环境变量 + `reset_runtime()`，保证 API 级测试**始终走离线确定性 Mock**；`auth.json` 换成 `tmp_path` 下的临时账号库 |
| `client` / `loopback_client` / `authed_client` / `bearer_client` | 分别对应「非回环地址访问」「本机直连访问」「已登录 Cookie」「只带 Bearer 不带 Cookie（小程序形态）」 |
| `admin_credentials` / `api_token` | 夹具账号口令与机器令牌，仅存在于 pytest 进程内（默认值 `test-only-*`，可用 `TEST_ADMIN_USER` / `TEST_ADMIN_PASSWORD` / `TEST_API_TOKEN` 覆盖） |

`conftest.py` 用**硬赋值**而不是 `setdefault` 设置 `AUTH_MODE`/`AUTH_TOKEN`/`ADMIN_USER`/`ADMIN_PASSWORD`，
因为 `webapp.app` 在 import 期就读环境变量：本机残留的同名变量不该能改掉测试账号。

## 加测试时的三条惯例

1. 需要评测资产就用 `hermetic_storage`，**不要**读仓库里的 `cases/`、`evalsets/`、`.env`、`webapp/auth.json`。
2. 需要接口就用 `client` / `authed_client` / `bearer_client`，不要自己 `import webapp.app` 造客户端
   （那会绕过 LLM 变量清理与 `auth.json` 隔离）。
3. 断言要写成**不变量**而不是硬编码得分（照 `scripts/verify.py` 的路子）：
   评测集扩充后测试还得能用，别把 `accuracy == 1.0` 写死在用例上。

## 已知限制

- `python -m pytest tests/test_sdk.py` 单独跑会得到 1 个 error（登录夹具读到本机
  `webapp/auth.json`）；原因与绕开办法写在 [AGENTS.md](../AGENTS.md) 的「已知坑」。
- `tests/test_pwa.py` 需要 `Pillow`（在 `requirements-dev.txt`），`tests/test_sdk.py` 需要
  已 `pip install ./sdk`：两者都是「干净环境必须显式装、胖环境看不出缺」的依赖，CI 里已各占一步。
- 全量在本机约 40 秒（`python -m pytest` 末尾的 `in 39.92s`），大头是 SDK 那个真起 uvicorn 的模块级夹具。
