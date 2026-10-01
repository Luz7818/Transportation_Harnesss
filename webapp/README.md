# webapp/ —— HTTP 服务与前端

> 用途：说明后端三个模块各管什么、前端页面与后端端点的对应关系、哪些东西不能动。

本目录是系统唯一的在线入口：`app.py` 提供 31 个 `/api/*` 操作与 3 条页面路由，
`auth.py` 管账号与会话，`settings.py` 管服务器 `.env` 的读写；
`static/` 是零构建、零外部依赖的单文件前端（看板 + 文档中心 + PWA 资产）。
网页、小程序、SDK、CLI 走的是同一套端点，前端不含任何业务算法。

## 文件清单

| 文件 | 干什么 | 备注 |
| --- | --- | --- |
| `app.py` | FastAPI 应用：环境变量与 `.env` 加载、CORS、鉴权中间件、全部端点、请求体模型（`CaseBody` 等）、启动 banner | 直接 `python webapp/app.py` 即可运行（`__main__` 里 `uvicorn.run`）；启动时会把仓库根插入 `sys.path`，所以允许 `E402` |
| `auth.py` | 本地账号与会话：`auth.json` 读写、PBKDF2-HMAC-SHA256（12 万次迭代）口令哈希、旧单轮 SHA-256 登录时透明升级、HMAC 签名会话令牌（7 天）、登录失败限流（5 次锁 10 分钟） | 签发/校验只在这一处（`make_token` / `parse_token`），别新增第二套会话格式 |
| `settings.py` | `.env` 的读、掩码、校验、原子写与写前备份；`SETTING_SPECS` 是键的唯一元数据来源（是否密钥 / 是否需重启 / 说明 / 示例） | 谁能访问由 `app.py::_settings_actor()` 决定，本模块不含 HTTP 或鉴权代码 |
| `__init__.py` | 空 | 包标记 |
| `auth.json` | 本机账号库（口令哈希 + 会话签名密钥 `secret` + `default_credentials` 标记） | **已 gitignore，严禁提交**；删掉重启会重建并随机生成新初始口令 |
| `static/index.html` | 应用壳：欢迎页 + 登录页 + 三栏工作台（5 个页签，侧栏/任务区可收起为图标轨）+ 常驻 AI 面板 + 命令面板 + 深浅主题（全站同步） | 单文件 3126 行，含全部 CSS/JS，无框架无 CDN；改前端就是改这个文件 |
| `static/help.html` | 文档中心（`/help`，免登录）：核心概念、工作流、接口参考、错误码 | 内容与 `docs/API.md` 同构，改一份必须改另一份 |
| `static/sw.js` | Service Worker：页面壳预缓存、`/static/*` stale-while-revalidate、`/api/*` network-first 回退缓存、非 GET 与 `/api/auth/*` 直连 | 必须从根路径提供（`GET /sw.js`），SW 作用域 = 脚本所在目录；缓存名带版本 `harness-shell-v4` / `harness-api-v1` |
| `static/manifest.webmanifest` | PWA 清单：`start_url`/`scope` 为 `/`、`display: standalone`、4 个图标、2 个快捷方式（`/` 与 `/help`） | 可安装性字段由 `tests/test_pwa.py` 断言 |
| `static/assets/` | 图标四件套（`icon.svg` 母版 + `icon-192/512.png` + `icon-maskable-512.png` + `apple-touch-icon-180.png`）、`logo-lockup.svg`、`banner.svg`、深浅纹理与背景 SVG | PNG 全套与两个 lockup/banner 由 `python scripts/generate_pwa_icons.py` 生成，不要手改 |

## 子目录

| 子目录 | 负责 |
| --- | --- |
| `static/` | 零构建前端的根：4 个入口文件（`index\.html` 2982 行、`help.html` 935 行、`sw.js` 106 行、`manifest.webmanifest` 35 行）加 `assets/` 的 11 个图标与背景（4 PNG + 7 SVG），共 15 个文件 |

本目录唯一的二级目录（`__pycache__/` 已 gitignore）。规模核对（在仓库根执行：
`python -X utf8 -c "import glob;print(len(glob.glob('webapp/static/*')),len(glob.glob('webapp/static/assets/*')))"` → `5 11`）。
它由 `app.py:107` 挂到 `/static`，另外三个路径**不按这个前缀**提供：`GET /` → `index.html`、
`GET /help` → `help.html`、`GET /sw.js` → `sw.js`（后一条是刻意的，见「别动」第 1 条）。
逐文件职责见上面的文件清单，页签与端点的对应关系见「前端 ↔ 后端对应」。

`assets/` 里 11 个文件中 10 个被页面或清单引用;`logo-lockup.svg` 不被看板页面引用,
但自 1.6.0 起作为 README 顶部的项目标识使用(核对,在仓库根执行:
`grep -roh "/static/assets/[a-zA-Z0-9._-]*" webapp/static/index.html webapp/static/help.html webapp/static/manifest.webmanifest | sort -u`
只覆盖看板侧;README 侧用相对路径引用)——
它是 `generate_pwa_icons.py` 每次都会重写的入库产物,手删只会在下次运行时冒回来。

## 后端：路由分组

| 组 | 端点 |
| --- | --- |
| auth | `POST /api/auth/login`、`POST /api/auth/logout`、`GET /api/auth/me`、`POST /api/auth/password` |
| metadata | `GET /api/health`、`/api/versions`、`/api/datasets`、`/api/segments/{dataset}`、`/api/evalsets`、`/api/activity` |
| analysis | `POST /api/analyze` |
| cases | `GET/POST /api/cases`、`GET/DELETE /api/cases/{case_id}`、`POST /api/cases/batch-delete` |
| eval | `POST /api/eval/run`、`POST /api/evolve/run` |
| reports | `GET /api/reports`、`/api/reports/{report_id}`、`/api/evolutions`、`/api/evolutions/{evolution_id}`、`/api/compare?a=&b=` |
| llm | `GET /api/llm/status`、`GET/POST /api/llm/drafts`、`DELETE /api/llm/drafts/{draft_id}`、`POST /api/llm/drafts/{draft_id}/confirm`、`POST /api/llm/diagnose` |
| settings | `GET/PUT /api/settings` |
| pages | `GET /`、`GET /help`、`GET /sw.js`（后者 `include_in_schema=False`，不进 OpenAPI） |

鉴权裁决顺序与 `/api/settings` 的例外，照代码写在 [AGENTS.md](../AGENTS.md) 的「鉴权事实」；
逐端点的请求/响应字段在 [docs/API.md](../docs/API.md)。这里只补三条只有读码才知道的事实：

- `/api/settings` 在中间件里被**豁免**通用 401（否则本机未登录用户只会看到「请先登录」而拿不到可操作指引），
  真正的准入在端点内 `_settings_actor()`，失败回 `403`。
- 「本机直连」的判定同时看 TCP 对端与转发头：带 `Forwarded`/`X-Forwarded-For`/`X-Real-IP` 的请求一律不算本机，
  这是为了防反代之后把公网访客当成本机。
- `POST /api/evolve/run` 用非阻塞锁，抢不到直接 `409`；请求体可以整体省略（兼容旧客户端，默认 `evalset_v1` + `baseline=v0`）。

## 前端 ↔ 后端对应（按页签）

前端所有请求都经过 `index.html` 里的 `api(url, body, method)`：相对路径 + `fetch`（浏览器自动带
`harness_session` Cookie），出错时把服务端的 `detail` 原文抛给调用方并附 `e.status`
（`403` 之类要分支给指引）。没有前端专用的数据接口 —— 每条 UI 都落在上面那张路由表里。

| 页签 / 区块 | 渲染入口（`static/index.html`） | 调用的端点 |
| --- | --- | --- |
| 启动与登录态 | `boot()` / `enterApp()` / `doLogin()` / `doLogout()` / `doChangePassword()` | `/api/auth/me`、`/api/auth/login`、`/api/auth/logout`、`/api/auth/password` |
| 顶栏状态徽标 | `loadHealth()` / `statusBadge()` | `/api/health`、`/api/llm/status` |
| 评测看板 | `renderDashboard()`（左栏 `renderDashTaskPanel()`、中栏 `renderDashWorkspace()`、概览 `dashOverview()`） | `/api/health`、`/api/versions`、`/api/reports`、`/api/evolutions`、`/api/evalsets`、`/api/activity?limit=10` |
| 看板上「运行评测」/「一键自进化」 | `runEval()` / `runEvolve()`（配 `withBusy()` 按钮态） | `POST /api/eval/run`、`POST /api/evolve/run` |
| 报告详情与进化时间线回放 | `showReport()` / `renderReportWorkspace()` / `replayEvolution()` + `replayStart()`/`replayShowStep()`/`replayCountTo()` | `/api/reports/{id}`、`/api/evolutions/{id}` |
| Case 管理 | `renderCases()`（列表）/ `renderCaseWorkspace()` / `renderCaseDetail()` / `renderCaseForm()` | `/api/cases`、`/api/datasets` |
| 沉淀表单联动 | `onFormDatasetChange()` → 路段下拉；`onFormSegmentChange()` → 用 v2 试跑给参照 | `/api/segments/{dataset}`、`/api/analyze` |
| 保存 / 删除 / 批量删除 / 导出 | `createCase()` / `deleteCase()` / `batchDelete()` / `exportSelected()` | `POST /api/cases`、`DELETE /api/cases/{id}`、`POST /api/cases/batch-delete` |
| 版本对比 | `renderCompare()` / `doCompare()` / `quickCompare()` / `quickCompareVersion()` / `toggleDiffRow()` / `diffDetailHtml()` | `/api/reports`、`/api/compare?a=&b=` |
| 分析提交 | `renderAnalyze()` / `doAnalyze()` / `onAnalyzeDatasetChange()` | `/api/versions`、`/api/datasets`、`POST /api/analyze` |
| 设置（运行时配置） | `renderSettings()` / `putSetting()` / `saveSetting()` / `clearSetting()` / `repaintSetting()` / `settingsDeniedCard()` | `GET /api/settings`、`PUT /api/settings` |
| 常驻 AI 面板 | `initAiPanel()` / `renderAiPanel()` / `renderAsstDrafts()` / `llmDraft()` / `llmLoadDraft()` / `llmConfirmDraft()` / `llmDiscardDraft()` / `llmDiagnose()` / `onAsstDatasetChange()` | `/api/llm/status`、`/api/llm/drafts`（GET/POST/DELETE）、`/api/llm/drafts/{id}/confirm`、`/api/llm/diagnose`、`/api/versions`、`/api/datasets`、`/api/segments/{dataset}` |
| 命令面板（Ctrl/Cmd+K） | `openCmdk()` / `renderCmdk()` / `cmdkActions()` / `runCmdkItem()` | `/api/reports`（报告检索与跳转、动作派发） |
| PWA 注册 | 页面尾部注册 `serviceWorker.register("/sw.js")`，仅在安全上下文生效 | `/sw.js`、`/static/manifest.webmanifest` |

`help.html` 是纯静态文档，不发请求；它同样注册 SW 与 manifest，所以可离线打开。

## 和谁打交道

- **上游**：`harness/`（评测与自进化）、`llm/`（智能层）、`pipeline/versions.py`（版本登记）。
- **下游**：浏览器看板、微信小程序、`sdk/harness_client`、`scripts/*.py`；
  `docs/openapi.json` 由 `app.py` 的 FastAPI 应用导出。
- **改完要跑**：`python -m pytest tests/test_webapp.py tests/test_auth.py tests/test_settings_api.py tests/test_pwa.py -q`
  → 再 `python scripts/export_openapi.py` 重导规范并同步 `docs/API.md`、`static/help.html`（改了端点时）。

## 别动

- 不要把 `/sw.js` 挪到 `/static/` 下或改用其他路径：SW 作用域由脚本 URL 决定，挪了就只能控制那一个目录，
  离线与安装能力当场失效（`tests/test_pwa.py::test_sw_served_at_root` 会红）。
- 不要把 `CORS_ORIGINS` 默认值改成具体域名去「顺手开 credentials」：
  `allow_credentials` 与通配符 `*` 互斥是浏览器规范，代码按「显式配置了来源才开」实现。
- 不要在 `settings.py` 里加鉴权判断，也不要在 `auth.py` 里拼 HTTP 响应；两层的边界就靠「谁都不越界」维持。
- 不要给 `/api/settings` 放开 `X-API-Token`：它与小程序等客户端共用同一枚机器令牌，
  认了就等于任何令牌持有者可改服务器配置（含换 `AUTH_TOKEN`）。
- 不要手改 `webapp/auth.json`、也不要把它或 `.env` 的内容摘进任何文档；
  登录页与看板都不显示口令，`/api/settings` 对密钥只回掩码。
- 前端没有构建步骤，`index.html` 里的 JS 就是最终产物：不要在仓库里另建 `src/`+`dist/` 双份，
  那会让「改了前端但产物没重编」这类漂移重新出现（根目录 `dist/harness-frontend.zip` 是历史打包物，已 gitignore）。
