# Transportation Harness 测试规范

> 用途：给写测试和跑门禁的人与 AI。测试数的事实口径在根目录 `AGENTS.md` 的「当前状态」。
> 「评测系统自己先要有测试」——分层与隔离策略的设计理由见 `docs/ARCHITECTURE.md` §8。

## 测试分层

| 层 | 管什么 | 数量级 |
|---|---|---|
| 单元层 | models 序列化/storage 路径安全/judge 全规则语义/runner 崩溃捕获/report 差分/管线算法行为(含负断言) | 14 文件 208 例 |
| 集成层 | evolve 完整闭环在临时目录跑真数据,断言逐轮提升、无回归、归档齐全 | `test_evolve.py` |
| 接口层 | TestClient 走真实鉴权流程(登录 Cookie/API Token/401/限流锁定/删除同步清单/穿越拦截) | `test_webapp.py` 等 |
| 端到端 | `scripts/verify.py` 用**不变量**(种子行为冻结 + 通过集单调不减 + 数值抽查)而非硬编码得分 | VERIFY PASS |
| 发布一致性 | 版本四处同步 + OpenAPI 无漂移 | `check_release.py` |
| CI | ruff → pytest → verify → check_release(3.11/3.12 矩阵) | `.github/workflows/ci.yml` |

## 运行命令

```bash
ruff check .
python -m pytest                       # 208 passed(30–55 s 浮动,含真起 uvicorn 的 SDK 用例)
python scripts/verify.py               # VERIFY PASS;雨天评测集同样 PASS
python scripts/check_release.py        # RELEASE CHECK PASS
```

**SDK 用例真起 uvicorn 走 `127.0.0.1`**：本机开了系统代理时请求会被代理截走，表现为
`test_sdk.py` 集中 `httpx.ReadTimeout`（2026-10-05 实测：不禁代理 11 failed + 1 error，
禁后 208 全过）。先禁代理再跑：

```bash
NO_PROXY="127.0.0.1,localhost" HTTP_PROXY= HTTPS_PROXY= python -m pytest
```

## 用例编写规范

- **评测资产用 `tests/fixtures/` 的冻结快照,不用真实 `cases/`**:`conftest.seed_asset_dirs()`
  重定向三个目录到 `tmp_path`。夹具比真实库多一条 `rc-0014`(断言「沉淀后编号递增」用),
  17 个 fixture 文件 ≠ 18 条生产 case,别让测试去读 `cases/`。
- 隔离夹具:`hermetic_storage` / `make_client` / `_hermetic_dotenv`——登录限流状态逐用例清零,
  `test_sdk.py` 的 `server_url` 夹具会把 `AUTH_FILE` 与模块级 `_AUTH_STORE` 换到临时文件
  (别拆这个隔离,否则单跑会读到本机真实 `webapp/auth.json` 而 401)。
- `pyproject.toml` 的 `pythonpath = ["."]` 是裸 `pytest` 与 `python -m pytest` 的 sys.path
  差异的修复——别删。
- `ruff` 的 `per-file-ignores` 允许 `webapp/app.py`、`scripts/*.py`、`tests/conftest.py` 的
  E402(先插 sys.path 再 import 是刻意的运行模式),别为了"干净"调顺序。
- 任何要求联网才能过的测试或校验都不许进 CI——确定性只在全程离线 Mock 下成立。

## 改动后的验证

| 你动了 | 必须跑 |
| --- | --- |
| `pipeline/versions.py`（含新增版本与 CHANGELOG 登记） | `python scripts/verify.py` + `pytest tests/test_versions.py tests/test_evolve.py -q` |
| `pipeline/data/*.json` | `python scripts/verify.py`（第 [5] 组是数值抽查,改了数据要同步期望值） |
| `cases/`、`evalsets/`、`tests/fixtures/` | `pytest tests/test_storage.py -q` + `verify.py` |
| `harness/judge.py`、`harness/models.py` | `pytest tests/test_judge.py tests/test_models.py -q` |
| `harness/evolve.py`、`harness/report.py` | `pytest tests/test_evolve.py tests/test_report.py -q` + `python -m harness.evolve` |
| `webapp/auth.py`、鉴权中间件、初始口令门禁 | `pytest tests/test_webapp.py tests/test_auth.py tests/test_settings_api.py -q` + 手动过一遍看板（改密前 403 → 改密后放行） |
| 版本号 / `docs/openapi.json` | `python scripts/check_release.py` |
| `webapp/settings.py` 的键元数据 | `pytest tests/test_settings_api.py -q` + 更新 `.env.example` 与看板「设置」页说明 |
| 任何端点/请求体字段 | `python scripts/export_openapi.py` 重导 + 同步 `docs/API.md`、`webapp/static/help.html`、`sdk/` |
| `sdk/harness_client/*` | `pip install ./sdk` 后 `pytest tests/test_sdk.py -q` |
| `webapp/static/**`（前端与 PWA） | `pytest tests/test_pwa.py -q` + 浏览器手测;改图标则 `generate_pwa_icons.py` |
| `llm/*` | `pytest tests/test_llm.py -q`（全程离线 Mock） |
| 任何代码 | `ruff check .` + `python -m pytest` + `verify.py` + `check_release.py`（CI 就这四条） |
