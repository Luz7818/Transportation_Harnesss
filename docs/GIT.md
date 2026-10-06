# Transportation Harness Git 规范

> 用途：给提交本仓代码的人。分支、CI 与探针、入库边界、敏感信息约束都在这里。

## 分支与提交策略

- 单 `main` 分支，推 `main` 触发 CI（`ci.yml`：ruff → pytest → verify → check_release）。
- **一批一提交**；端点改动与 `openapi.json`/`docs/API.md`/`help.html`/SDK 的同步必须在
  同一次提交里（关键约定 4）。
- 评测归档的处理规则：`harness.evolve`/`run_eval.py` 试跑后新增的 `reports/` 文件，
  **要么一起提交（归档即历史），要么删干净再提交**，别留下半套不一致的归档。

## 必须入库 / 禁止上传

| 判定 | 规则 |
|---|---|
| 必须入库 | `harness/`、`pipeline/`（含 `data/` 情景数据）、`llm/`、`webapp/`、`cases/`、`evalsets/`、`reports/`（归档即历史）、`scripts/`、`sdk/`（`dist/` 下 wheel 按约定入库）、`miniprogram/`、`tests/`、九件文档 |
| 禁止上传 | `drafts/`、`llm_cache/`、`llm_runs.jsonl`（运行期产物，gitignore，前导斜杠只匹配仓库根）；`webapp/auth.json`、`.env`、`miniprogram/config.js`、`启动后端.bat` |
| **绝不** | 公网 IP、真实令牌值、`AUTH_TOKEN`/口令实际取值；示例一律 `<你的服务地址>`、`<AUTH_TOKEN>`、`<你的口令>`；`LIVE_HEALTH_URL` 存仓库 secret 不入库 |

## CI 与线上探针

- `ci.yml`：Python 3.11/3.12 矩阵，四条门禁。
- `probe.yml` 已随线上服务下线移除（2026-10-06）：服务连续失联 6 天，每日探针连败失去
  信号价值。复活部署后从 git 历史恢复（`git log --oneline -- "**/probe.yml"`），
  重新配置 `LIVE_HEALTH_URL` secret 即可。

## 发布

- 版本号四处同步（根 `pyproject.toml`、`sdk/pyproject.toml`、`sdk/harness_client/__init__.py`、
  FastAPI version 参数），由 `check_release.py` 断言进 CI。
- tag 命名 `v主.次.补`；Release 附 SDK wheel（待办，见 `TODO.md`）。
- 版本演进记录：`HISTORY.md`（从 2.0.0 起向前记录）。

## commit message

- 风格沿用既有历史：`<type>(<scope>): 中文一句话` 或 `<type>: 中文一句话`
  （复核：`git log --oneline -10`）。
