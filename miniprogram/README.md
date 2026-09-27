# miniprogram/ —— 微信小程序客户端

> 用途：说明本目录负责什么、每个文件干什么。使用步骤与鉴权方式在下面的原有章节里。

本目录是一个**独立的小程序工程**（微信开发者工具直接导入本目录），
与 FastAPI 后端共用同一套 HTTP API，不额外含任何业务逻辑：
4 个 Tab（评测看板 / 版本对比 / 分析提交 / Case 库）+ 5 个非 Tab 页
（报告详情 / 进化详情 / 用例详情 / AI 草稿 / 登录）。
它服务的是「外业现场提交 badcase、手机上回看进化结果」这一段。

## 文件清单

| 文件 / 目录 | 干什么 | 备注 |
| --- | --- | --- |
| `app.json` | 注册 9 个页面、4 个 TabBar 项、窗口样式 | TabBar 为纯文字（合法，无需图标） |
| `app.js` / `app.wxss` | 应用入口与全局样式 | `app.js` 只有一行,不承担逻辑 |
| `config.example.js` | 配置模板：只有 `BASE_URL` 一项 | 复制为 `config.js` 后填写；**不要再写任何令牌** |
| `config.js` | 本机后端地址 | 已 gitignore，克隆后不存在；缺失时 `utils/api.js` 兜底成空串并提示去登录页填 |
| `utils/api.js` | `wx.request` 封装：地址解析（storage 覆盖 > `config.js`）、会话令牌读写、`Authorization: Bearer` 注入、401/过期→清令牌跳登录、临期提示、错误带 `statusCode` | 小程序与后端唯一的接口层；页面不直接调 `wx.request` |
| `pages/login/` | 登录页：换会话令牌、覆盖服务器地址、显示剩余有效期 | 连续失败 5 次锁定 10 分钟，页面不自动重试 |
| `pages/dashboard/` | 评测看板：得分卡片、运行评测、一键自进化、进化时间线、报告列表 | 并发拉 `health`/`llm/status`/`versions`/`reports`/`evolutions`/`evalsets`/`activity` |
| `pages/report/` | 单份评测报告详情（逐用例判分明细） | 由 `dashboard` 或时间线跳入 |
| `pages/evolution/` | 单次自进化完整记录（逐轮轨迹） | 读 `/api/evolutions/{id}` |
| `pages/compare/` | 版本对比：任选两份报告逐用例差分 | 读 `/api/reports` + `/api/compare?a=&b=` |
| `pages/analyze/` | 分析提交：版本 × 数据集，展示场景解读 | 读 `/api/versions`、`/api/datasets`、`POST /api/analyze` |
| `pages/cases/` | Case 库：浏览、沉淀表单（数据集 → 路段下拉 → 期望）、批量删除 | 写 `POST /api/cases`、`POST /api/cases/batch-delete` |
| `pages/case-detail/` | 单条用例详情（含 `checks`）与删除 | 读 `/api/cases/{id}` |
| `pages/drafts/` | AI 草稿：起草、列表、人工确认、丢弃、失败诊断 | 写 `/api/llm/drafts`、`.../confirm`、`/api/llm/diagnose` |
| `project.config.json` / `project.private.config.json` / `sitemap.json` | 开发者工具工程配置（含 AppID）、本机私有配置、索引规则 | 换主体时替换 `appid` |
| `README.md` | 本文件 | — |

`preview_qr.png`、`preview_info.json` 若出现在本机，是预览产物且已 gitignore，不要提交。

## 子目录

| 子目录 | 负责 |
| --- | --- |
| `pages/` | 9 个页面目录（4 个 Tab + 5 个非 Tab），每个固定 4 个同名文件：`.js` 逻辑、`.wxml` 结构、`.wxss` 样式、`.json` 页面配置（管 `navigationBarTitleText`）。逐页职责见上面的文件清单 |
| `utils/` | 只有 `api.js` 一个文件：`wx.request` 的唯一封装，页面不直接发请求 |

规模与一致性（复核，在仓库根执行：`python -X utf8 -c "import glob;print(len(glob.glob('miniprogram/pages/*/')),len(glob.glob('miniprogram/pages/*/*')),len(open('miniprogram/utils/api.js',encoding='utf-8').readlines()))"`
→ `9 36 200`）。`pages/` 下的 9 个目录名必须与 `app.json` 的 `pages` 数组一一对应，核对见「别动」第 2 条。

## 和谁打交道

- **上游**：`webapp/app.py` 的 `/api/*`。登录用 `POST /api/auth/login` 换会话令牌，其余页面各引用 1–9 个 `/api/` 路径
  （逐页对应关系在上面的文件清单里，`login/` 是 `0` 因为路径写在 `utils/api.js`）；端点与字段口径以 `docs/openapi.json`、`docs/API.md` 为准。
- **下游**：微信开发者工具与真机上的用户。本目录的代码不被仓库内任何 Python 模块 import，
  也不在 `tests/` 与 CI 的覆盖范围内（复核，在仓库根执行：`grep -rn miniprogram tests/*.py .github/workflows/ci.yml` → 无输出）。
- **改这里之后要跑**：Python 侧的门禁（`python -m ruff check .`、`python -m pytest`）碰不到本目录，
  能自动核对的只有配置一致性与每页引用了几个端点（Git Bash，在仓库根执行；三条的预期分别是 `9 4`、`[] []`、每页 0–9）：

  ```bash
  python -X utf8 -c "import json;d=json.load(open('miniprogram/app.json',encoding='utf-8'));print(len(d['pages']),len(d['tabBar']['list']))"
  python -X utf8 -c "import json,os;a={x.split('/')[1] for x in json.load(open('miniprogram/app.json',encoding='utf-8'))['pages']};d=set(os.listdir('miniprogram/pages'));print(sorted(a-d),sorted(d-a))"
  for f in miniprogram/pages/*/; do echo "$f $(grep -oh '/api/[a-z/]*' "$f"*.js | sort -u | wc -l)"; done
  ```

  界面行为只能在微信开发者工具里导入 `miniprogram/` 人工回归：登录 → 逐个点开 4 个 Tab → 沉淀一条 case。
- **改了后端契约**：这里要同步的通常是 `utils/api.js` 的错误分支与页面里的字段名；
  同一次改动还要落到 `docs/API.md`、`webapp/static/help.html`、`sdk/`（约定见 [AGENTS.md](../AGENTS.md) 关键约定 4）。

## 别动

- **`config.js` 不入库但编译期硬依赖**：`utils/api.js:24` 直接 `require("../config.js")`，缺文件就编译报错。
  克隆后第一步是复制 `config.example.js` 改名为 `config.js`。核对：`grep -n 'require("../config.js")' miniprogram/utils/api.js`。
- **`pages/login/login.wxml` 三个 `<input>` 上的 `bindinput="onInput"`**（核对，在仓库根执行：
  `grep -c 'bindinput="onInput"' miniprogram/pages/login/login.wxml` → `3`）：2026-09-27 三处全缺过，
  打字永远进不了 `data`、点登录必提示「请填写用户名与口令」，登录整条链路不可用；它属 WXML 层，
  ruff / pytest / CI 全都测不到。修复在提交 `63f2690`，别当成重复属性删掉。
- **`app.json` 的 `pages` 与 `pages/` 目录必须互相齐平**：注册了没目录 → 编译失败；有目录没注册 → 页面打不开。
  `.gitignore` 里 `/drafts/` 的前导斜杠就是为此——去掉斜杠会连带吞掉 `miniprogram/pages/drafts/` 那 4 个文件，
  而 `app.json` 照样注册它（当前 4 个文件都在库里，核对：`git ls-files miniprogram/pages/drafts` → 4 行；
  两边齐平的核对命令见上面「改这里之后要跑」，应输出 `[] []`）。
- **四个本机存储键** `harness_base_url` / `harness_session_token` / `harness_session_expires_at` / `harness_return_to`
  是登录态与「登录后回跳原页」的唯一载体（核对：`grep -n "harness_" miniprogram/utils/api.js` → 4 行常量）。
  改名不报错，只会让已登录用户当场掉回登录页、登录后回不到原来那一页。
- **`project.config.json` 的 `urlCheck: false`**：它让本机与局域网的 `http` 地址能在开发者工具里直接请求，
  去掉就只能连备案过的 https 域名（核对：`grep -n urlCheck miniprogram/project.config.json`）。
  同文件的 `appid` 是个人主体 `wx5455bfec9b610cd7`，换主体才动它。
- **TabBar 的 4 项是纯文字**（`app.json` 的 `tabBar.list` 里没有 `iconPath`，这是合法配置）：
  别只给其中几项加图标，要加就四套齐全，见上面「正式发布的要求」第 5 条。

---

# 微信小程序端接入说明

这是「交通分析自进化 Harness」的微信小程序客户端,与 FastAPI 后端共用同一套 HTTP API,
功能与网页版对齐:一键自进化、进化时间线、版本对比、场景化分析、Case 沉淀。

## 页面(4 个 Tab)

| Tab | 功能 |
| --- | --- |
| 评测看板 | 各版本得分卡片、单版本运行评测、**一键自进化**(弹窗展示逐轮结果)、**进化时间线**、报告归档(标注评测集) |
| 版本对比 | 任选两份报告逐 case 差分:新通过/回归统计 + 每条用例的 PASS/FAIL 变化 |
| 分析提交 | 版本 × 情景数据集(雨天/事故/晚高峰等)选择,**展示场景解读**,即时查看分级/指标/处置建议 |
| Case 库 | 浏览 replaycase;提交表单沉淀新 badcase(选数据集 → 选路段 → 设期望),自动加入评测集 |

## 使用步骤

1. **准备配置文件(必做)**:`miniprogram/config.js` 不入库(内含真实服务器地址),克隆仓库后
   先把 `config.example.js` **复制一份改名为 `config.js`**,填入你的后端地址。
   小程序没有构建期环境变量,`utils/api.js` 直接 `require("../config.js")`,少了这个文件会编译报错。
2. 用**微信开发者工具**导入 `miniprogram/` 目录。AppID 已接入
   `wx5455bfec9b610cd7`(个人主体,已写入 `project.config.json`),点「预览」即可真机调试;
   如需换主体,替换为自己的 AppID 即可。
3. 开发阶段在开发者工具「详情 → 本地设置」勾选 **不校验合法域名、web-view(业务域名)、TLS 版本以及 HTTPS 证书**;
   手机首次进入:小程序右上角「…」→ 打开调试,放行 http 请求。
4. 打开小程序:本机没有有效会话令牌时,进任意 Tab 都会自动跳到**登录页**(`pages/login`,普通页面、不在 TabBar 内),
   填服务器地址 + 管理员分配的账号口令登录,登录成功后回到原来那一页。

## 鉴权:登录换短期会话令牌

**小程序端不再携带任何长期静态密钥。** 小程序包会分发到用户手机上,打进包里的常量等于公开,
所以旧版本写在 `config.js` 里的静态机器令牌已废弃,改为按用户登录换取短期会话令牌:

- **申请账号**:账号与口令由**服务器管理员**分配(后端 `webapp/auth.json`,管理员可用
  `ADMIN_USER` / `ADMIN_PASSWORD` 初始化、在网页端「修改口令」里改),小程序里**不预置任何默认口令**;
- **登录**:`POST /api/auth/login`,请求体 `{username, password}`;成功后响应里的
  `token`(HMAC 签名会话令牌)与 `expires_at`(unix 秒)存进手机 `wx.setStorageSync`;
- **有效期 7 天**;剩余不足 24 小时时小程序会 toast 提示一次续登,登录页也显示剩余时长,
  重新登录即续期;
- **发请求**:统一走 `Authorization: Bearer <会话令牌>`(`wx.request` 不适合走 Cookie,
  所以不用后端也支持的 `harness_session` Cookie 方式);
- **失效处理**:本地没有令牌、令牌已过期,或后端返回 401,都会清掉本机令牌并跳登录页
  (并行请求同时失败时只提示、只跳一次),登录后回到原来的页面。
  所有业务错误仍带 `err.statusCode`,页面据此区分 409(自进化运行中)等场景;
- **登录失败限流**:服务端对同一用户名连续失败 5 次锁定 10 分钟,后端返回的剩余秒数会原样显示在
  登录页错误条上;前端**不做任何自动重试**(重试只会加重锁定)。

## 切换服务器地址

两种方式,后者优先:

1. 改 `config.js` 的 `BASE_URL`(对所有页面生效,需要重新编译);
2. 直接在**登录页的「服务器地址」输入框**里填,登录时会覆盖并保存到本机 storage,
   便于在外业现场于 本机 `http://127.0.0.1:8765` / 局域网 `http://192.168.x.x:8765`(手机与电脑同一 Wi-Fi)
   / 公网 `https://你的域名` 之间来回切换,不用重新编译。

## 正式发布的要求(重要)

微信对线上小程序的网络请求有硬性要求,发布前需要:

1. **HTTPS**:后端必须通过 HTTPS 对外提供服务(DEPLOY.md 的 Nginx + 证书方案);
   登录口令在 http 明文通道上提交,公网/外网环境下只用 http 会被中间网络窃听,上线前务必换 HTTPS;
2. **备案域名**:request 合法域名必须是 ICP 备案过的域名;
3. **配置合法域名**:小程序管理后台 → 开发设置 → 服务器域名 → `request` 合法域名,加入 `https://你的域名`;
4. **AppID**:`project.config.json` 已接入个人主体 AppID `wx5455bfec9b610cd7`,换主体时替换即可;
5. TabBar 图标:当前为纯文字 Tab(合法);如需图标,提供 81×81 PNG(普通/选中各一套)放入对应页面目录并配置 `app.json` 的 `iconPath`/`selectedIconPath`。

> 替代方案:如果只是内部工具、不想走小程序发布流程,可以用**公众号 H5 / 企业微信自建应用**直接打开网页版看板,或保留网页 + 内网穿透使用。

## 目录结构

```
miniprogram/
├── app.json / app.js / app.wxss     # 全局配置与样式(4 个 Tab + 5 个二级页)
├── config.example.js                # 配置模板:复制为 config.js 再填地址
├── config.js                        # 本机服务器地址(不入库,不含任何令牌)
├── utils/api.js                     # wx.request 封装:自动带 Bearer 会话令牌 + 401 回登录页
├── pages/login/                     # 登录页(换会话令牌、覆盖服务器地址)
├── pages/dashboard/                 # 评测看板(一键自进化 + 进化时间线)
├── pages/report/                    # 单份评测报告详情
├── pages/evolution/                 # 单次自进化的逐轮轨迹
├── pages/compare/                   # 版本对比(逐 case 差分)
├── pages/analyze/                   # 分析提交(场景化数据集)
├── pages/cases/                     # Case 库(浏览 + 沉淀 + 批量删除)
├── pages/case-detail/               # 单条 replaycase 详情(含 checks)与删除
└── pages/drafts/                    # AI 草稿(起草 / 确认 / 丢弃)与失败诊断
```
