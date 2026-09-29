# Transportation Harness 上手手册

> 用途：给要真的把它用起来或改它的人。每一步给命令、给真实输出、给出错时怎么办。
> 阅读顺序：从第 1 节往下做，不需要跳读。术语第一次出现都有一句解释，汇总在第 10 节。
> 测试数、端点数、CI 状态这类事实在 [AGENTS.md](../AGENTS.md) 里唯一维护，本手册只链接不复述。

## 1. 需要准备什么

| 项目 | 要求 | 怎么确认 |
| --- | --- | --- |
| 操作系统 | Windows / Linux / macOS 均可（本手册的命令以 Windows cmd 为准，另给 PowerShell 与 Linux 写法） | — |
| Python | 3.11 以上（`pyproject.toml` 的 `requires-python`；CI 跑 3.11 与 3.12） | `python --version` → 本机 `Python 3.12.0` |
| 运行时依赖 | 只有 `fastapi` 与 `uvicorn`（`requirements.txt`） | 第 2 节 |
| 开发/测试依赖 | `pytest`、`httpx`、`ruff`、`Pillow`（`requirements-dev.txt`） | 第 2 节 |
| 网络 | **用不到**。评测、判分、自进化全程本地；LLM 不配密钥时走离线确定性 Mock | — |
| 密钥 | 无。真实模型、公网部署、小程序发布才分别需要模型密钥、服务器、备案域名 | 第 6/8 节 |
| 想装成 PWA | Chrome / Edge 等现代浏览器，且地址是 `localhost` 或 HTTPS | 第 3 节 |
| 想用小程序 | 微信开发者工具 + 你自己的后端地址 | 第 6 节 |

## 2. 装好它

```bash
pip install -r requirements.txt -r requirements-dev.txt
pip install ./sdk
```

`pip install ./sdk` 装的是仓库内的官方 SDK（导入名 `harness_client`，带 `harness-client` 命令行）。
装完用这几条确认（本机实测输出）：

```bash
python -c "import fastapi,uvicorn,httpx,PIL,pytest;print(fastapi.__version__,uvicorn.__version__,httpx.__version__,PIL.__version__,pytest.__version__)"
python -c "import harness_client;print(harness_client.__version__)"
ruff --version
```

```
0.141.1 0.52.4 0.28.1 12.0.0 8.3.5
2.0.0
ruff 0.16.7
```

要接真实大模型才需要配置；不配一切照常（离线 Mock）。复制 `.env.example` 为 `.env` 后，
只有这几项会改变行为（完整清单看 `.env.example` 的注释与看板「设置」页）：

| 变量 | 作用 | 不填会怎样 |
| --- | --- | --- |
| `HOST` / `PORT` | 监听地址与端口（重启生效） | 默认 `127.0.0.1:8765`，只有本机可访问 |
| `AUTH_MODE` | `login`（默认，浏览器要登录）/ `open`（免登录，仅限内网演示）（重启生效） | 按 `login` 走，未登录访问受保护接口得 `401` |
| `AUTH_TOKEN` | 机器客户端令牌，`X-API-Token` 那条通道（重启生效） | 该通道不参与裁决，只能用会话令牌或 Cookie |
| `ADMIN_USER` / `ADMIN_PASSWORD` | 部署者自己提供的管理员账号口令:创建账号即视为已设置;对「默认口令未改」的存量部署,重启时就地轮换 | 用户名 `admin`,口令随机生成只打印一次,且改掉口令前业务接口一律 403(见第 3 节) |
| `SETTINGS_ENABLED` | 开启 `/api/settings` 在线读写 `.env`（默认关） | 看板「设置」页恒得 `403` |
| `COOKIE_SECURE` | HTTPS 部署时设 `1`，会话 Cookie 只经加密通道回传 | Cookie 允许经 http 回传 |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | 接任意 OpenAI 兼容端点（`base_url` + `api_key` 两枚齐了才启用） | 整条 LLM 链路走离线确定性 Mock |
| `LLM_EXTRA_BODY` | JSON 对象，原样并入请求体（如关闭 Qwen3 思考模式）；含 `"response_format": null` 时关闭默认的 JSON 引导解码（个别 vLLM 端点会与模型输出叠加产生畸形 JSON） | 不附加供应商专属参数 |

> `.env` 已在 `.gitignore` 里；不要把真实地址、令牌、口令写进任何文档或提交物。

## 3. 起服务、打开看板

最快的体验方式是免登录模式（只有本机用）：

```bash
set AUTH_MODE=open && python webapp/app.py
```

PowerShell 用 `$env:AUTH_MODE="open"; python webapp/app.py`，Linux/macOS 用
`AUTH_MODE=open python webapp/app.py`。看到这两行就是起来了：

```
交通分析自进化 Harness -> http://127.0.0.1:8765(鉴权模式:open);/api/settings 未启用(设 SETTINGS_ENABLED=1 开启)
INFO:     Uvicorn running on http://127.0.0.1:8765 (Press CTRL+C to quit)
```

浏览器打开 <http://127.0.0.1:8765>（标题 `Transportation Harness · 交通分析自进化评测系统`），
左侧 5 个页签：**评测看板**（各版本得分卡片、运行评测、一键自进化、进化时间线回放）、
**Case 管理**（用例库 + 沉淀表单 + 详情判分明细）、**版本对比**（两份报告逐用例差分）、
**分析提交**（版本 × 数据集，含雨天/事故/晚高峰解读）、**设置**（在线读写 `.env`，默认被 `403` 挡住）。
右侧常驻「智能助手」面板：Runtime 状态、AI 草稿、失败诊断。
文档中心在 <http://127.0.0.1:8765/help>（免登录可读），交互式调试在 <http://127.0.0.1:8765/docs>。

拨测接口给的真实响应：

```bash
curl http://127.0.0.1:8765/api/health
```

```json
{"status":"ok","app_version":"2.0.0","auth_mode":"open","default_credentials":true,
 "versions":["v0","v1","v2"],"case_count":16,"evalset_count":2}
```

`case_count`/`report_count` 会随沉淀与运行增长;`default_credentials` 是
「初始口令还没改掉」的布尔标记 —— 为 `true` 时业务接口处于 403 门禁状态
(登录模式),改口令或提供 `ADMIN_PASSWORD` 后翻转为 `false`。

想按默认的登录模式跑（更接近公网部署形态）：

```bash
python webapp/app.py
```

首次启动会在 `webapp/auth.json`（已 gitignore）里建账号：没给 `ADMIN_PASSWORD` 时随机生成一枚
强口令并只在控制台打印一次，用户名默认 `admin`。**在口令被改掉之前，业务接口对一切凭据
（含机器令牌与已登录会话）一律 `403`，只放行 `/api/health` 与 `/api/auth/*`**：
用那枚口令登录后看板会自动弹出「修改密码」，改完门禁立即解除。
之后未登录访问受保护接口得到 `401`：

```json
{"detail":"未登录或会话已过期"}
```

想一次到位（推荐公网部署用）：启动前在环境或 `.env` 里设好 `ADMIN_PASSWORD` 与强随机
`AUTH_TOKEN`，服务起来即是收口状态，无需手动改密。步骤与轮换通道见 [DEPLOY.md](../DEPLOY.md)。

PWA：在 `localhost` 或 HTTPS 下，浏览器地址栏的「安装」即可得到独立窗口与图标；
断网后仍能浏览最后一次加载的看板数据（Service Worker 缓存了页面壳与 GET 接口结果）。
公网用 `http://IP:8765` 访问时 SW 不注册，页面功能不受影响（浏览器的安全上下文限制）。

## 4. 跑一次评测与一键自进化

评测不需要服务，命令行即可。

### 4.1 单版本评测（看基线错在哪）

```bash
python scripts/run_eval.py --version v0
```

真实输出（末行是归档报告路径）：

```
[v0] 评测集 evalset_v1:1/13 通过(7.7%),耗时 3.04 ms
case       标签       结果     得分     说明
rc-0001    阈值错误     FAIL   0.0    期望「拥堵」,实际「严重拥堵」; 期望 0.91±0.01,实际 2
rc-0005    指标计算错误   FAIL   0.0    期望 0.64±0.02,实际 -0.64
rc-0006    健壮性      FAIL   0.0    管线崩溃; 管线崩溃,无法判分:TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'
rc-0012    健壮性      FAIL   0.0    管线崩溃; 管线崩溃,无法判分:ZeroDivisionError: division by zero
rc-0013    回归保护     PASS   1.0
...

JSON 报告 -> reports\report_v0_<时间>.json
```

看到什么算对：`1/13 通过(7.7%)`，且唯一通过的是 rc-0013（回归保护用例）。
`--version v2` 则应得到 `13/13 通过(100.0%)`。参数：

| 参数 | 作用 | 常用值 |
| --- | --- | --- |
| `--version` | 必填，只能是已登记版本 | `v0` / `v1` / `v2` |
| `--evalset` | 评测集名（`evalsets/` 下的文件名） | `evalset_v1`（默认）、`evalset_scenario_rain` |
| `--md` | 额外出 Markdown 报告 | 需要贴给别人看时加 |

换数据集视角（同一份 v2 管线跑不同评测集，检验恶劣天气下的稳健性）：

```bash
python scripts/run_eval.py --version v0 --evalset evalset_scenario_rain
```

```
[v0] 评测集 evalset_scenario_rain:0/3 通过(0.0%),耗时 0.84 ms
```

### 4.2 一键自进化

```bash
python -m harness.evolve
```

真实输出的关键几行(2026-09-29,15 条评测集;单轮上限 2,本轮验证 v1/v2,v3 留待下轮):

```
=== 自进化循环启动:评测集 evalset_v1(15 条 replaycase)===
--- 基线测量(v0)---
得分 1/15(6.7%);失败案例如下:
--- 第 1 轮迭代(v1:算法修正)---
得分 11/15(73.3%),较上一轮 66.7%;新通过 10 条,回归 0 条
--- 第 2 轮迭代(v2:边界与聚合优化)---
得分 13/15(86.7%),较上一轮 13.3%;新通过 2 条,回归 0 条
=== 总结 ===
停止原因:已达本轮迭代上限(v3 待验证)(本轮迭代 2 轮,上限 2)
待验证版本:v3 —— 用 --baseline <上一版本> 继续验证
最佳版本:v2,得分 13/15(86.7%)(基线 6.7%) → 提升 80.0%
Markdown 报告 -> reports\report_evolution_<时间>.md
```

**前向迭代留痕**:沉淀新 badcase 后写新版本,再用 `--baseline` 增量验证 ——
v3 就是这样产生的(rc-0014/rc-0015 沉淀 → 登记 `analyze_v3` → 增量验证):

```bash
python -m harness.evolve --baseline v2
```

```
--- 第 1 轮迭代(v3:排队回溢升级带)---
得分 15/15(100.0%),较上一轮 13.3%;新通过 2 条,回归 0 条
=== 总结 ===
停止原因:评测集已全部通过(本轮迭代 1 轮,上限 2)
最佳版本:v3,得分 15/15(100.0%)(基线 86.7%) → 提升 13.3%
```

它同时写三份归档:逐版本 JSON(`reports/report_v*_*.json`)、进化摘要
(`reports/evolution_*.json`,看板时间线读它)、Markdown 总报告。

| 参数 | 作用 | 注意 |
| --- | --- | --- |
| `--evalset` | 用哪个评测集 | 默认 `evalset_v1` |
| `--baseline` | 基线版本;只验证登记在它之后的版本 | 默认 `v0`;传最末登记版本(现为 `v3`)会得到明确报错退出码 1(第 9 节) |
| `EVOLVE_MAX_ROUNDS`(环境变量) | 单轮运行的迭代上限 | 默认 2;设 1 时未验证版本会列在「待验证版本」里而不是被丢弃 |

### 4.3 端到端校验（改完必须绿）

```bash
python scripts/verify.py
```

```
VERIFY PASS:最小闭环与两轮自进化结果全部符合预期。
```

它断言的是**不变量**而不是硬编码得分：种子用例行为冻结（v0 只过 rc-0013、v1 剩
rc-0009/rc-0010、v2 全过）、通过集单调不减、关键数值抽查（v2 在 `base` 上全局指数
0.7944、拥堵路段降序、缺失数据与空数据降级）、`reports/` 归档齐。
`--evalset evalset_scenario_rain` 会跳过种子冻结那一组，其余照跑。

## 5. 把一条 badcase 沉淀为可重放用例

这是闭环的第 1–2 步，做完这条用例就进库并进评测集，之后每次评测都会重放它。

1. **准备**：按第 3 节把服务起起来（演示用 `AUTH_MODE=open` 免登录；真实部署按凭据方式带
   `X-API-Token` 或登录后拿 Cookie）。
2. **看板路径**：左栏 **Case 管理** → 中间「沉淀新用例」表单 →
   依次填：标题、失败标签（可新写，标签会成为目录名）、数据集（选 `base` 等 6 个之一）、
   路段（下拉直接列该数据集里的路段 ID，来自 `GET /api/segments/{dataset}`）、
   期望拥堵等级（六档枚举）、可选的期望饱和度与容差、备注 → 保存。
3. **命令行路径**（等价，便于脚本批量沉淀）：

```bash
curl -X POST http://127.0.0.1:8765/api/cases -H "Content-Type: application/json" ^
  -d "{\"title\":\"解放西路(V/C 0.71)现场已排队回溢,应按「拥堵」预警\",\"label\":\"边界处理\",\"dataset_name\":\"base\",\"segment\":\"S-06\",\"expected_level\":\"拥堵\",\"notes\":\"外业复核:早高峰排队已回溢至上游交叉口\"}"
```

真实响应（`case_id` 自动取当前最大 `rc-` 序号 +1；Windows 下 `saved` 用反斜杠）：

```json
{"saved":"cases\\边界处理\\rc-0014.json","added_to_evalset":true,
 "case":{"case_id":"rc-0014","title":"解放西路(V/C 0.71)现场已排队回溢,应按「拥堵」预警",
   "label":"边界处理","dataset_name":"base",
   "checks":[{"type":"classify","segment":"S-06","expected":"拥堵","tol":0.01,
              "field":null,"keywords":[],"min_score":0.7}],
   "source":"网页提交","created_at":"2026-09-27T03:30:25","notes":"外业复核:…"}}
```

4. **确认它真的进了评测集**：`evalsets/evalset_v1.json` 的 `case_ids` 末尾应多出 `rc-0014`，
   用例文件落在 `cases/<标签>/<case_id>.json`。「写文件 + 改清单」是同一把锁里的原子操作，
   不会出现用例存在而清单没更新。
5. **重放它**：

```bash
python scripts/run_eval.py --version v2
```

```
[v2] 评测集 evalset_v1:13/14 通过(92.9%)
rc-0014    边界处理     FAIL   0.0    期望「拥堵」,实际「缓行」
```

**这一步的"对"恰恰是出现一条 FAIL**：它说明评测集捕获了一个当前最佳版本还没满足的场景。
接下来就是迭代 `pipeline/versions.py`：登记 `analyze_v3` 进 `PIPELINES`/`CHANGELOG`，
再 `python -m harness.evolve --baseline v2` 增量验证新版本。
（`verify.py` 对这种新用例只给 WARN 不判失败的承诺见第 9 节最后一条 —— 某些新用例会让
[2] 单调性检查直接 FAIL，原因和解法写在那里。）

6. **删除误沉淀的用例**：`DELETE /api/cases/{case_id}`（会同步从所有评测集清单里移除，
   不留悬空引用）；批量用 `POST /api/cases/batch-delete`（单次上限 200）。

### 5.1 让 AI 先起草、人工再确认

配置密钥前它走离线 Mock，链路一样可跑（草稿只落 `drafts/`，不碰评测资产）：

```bash
curl -X POST http://127.0.0.1:8765/api/llm/drafts -H "Content-Type: application/json" ^
  -d "{\"complaint\":\"用户点踩:泉山南路明明已经堵死了(V/C 0.95),系统只说严重拥堵却没有处置建议\",\"dataset_name\":\"base\"}"
```

```json
{"draft_id":"draft-0001","status":"pending","segment_id":"S-10",
 "title":"用户点踩:泉山南路明明已经堵死了(V/C 0.95),系统只说严重拥堵却没有处置建议",
 "label":"结论缺失","expected_level":"严重拥堵","expected_saturation":0.95,
 "llm":{"model":"mock-deterministic","kind":"mock","purpose":"draft"}}
```

没给 `segment_id` 时助手按 v2 的实际判定挑一个拥堵路段作靶子。确认后走
`POST /api/llm/drafts/{draft_id}/confirm`，内部复用与手工沉淀**完全相同**的校验与落盘路径 ——
人工确认不能绕过字段校验；重复确认得 `409 草稿已处理`。

## 6. 接入微信小程序

小程序共用同一套 HTTP API，不写死任何地址与令牌。要填的只有：

| 位置 | 填什么 | 说明 |
| --- | --- | --- |
| `miniprogram/config.js` 的 `BASE_URL` | `http://<你的服务地址>:8765` | 该文件不入库：把 `config.example.js` 复制一份改名为 `config.js` 再填。缺它则编译期 `require("../config.js")` 报错 |
| 登录页（`pages/login`）的「服务器地址」 | 同上，可临时覆盖 `config.js` | 本机 / 局域网 / 公网来回切不用重编译；优先级高于 `config.js` |
| 登录页的用户名与口令 | 服务端账号（默认用户名 `admin`） | 小程序里不预置任何口令；账号由管理员分配 |
| `project.config.json` 的 `appid` | 你自己的 AppID（若要换成别的主体） | 换主体时替换 |

**小程序不再携带长期静态令牌**：登录换一枚 7 天有效的会话令牌存本机 storage，
每个请求带 `Authorization: Bearer <令牌>`；无令牌、令牌过期或后端回 `401` 都会清掉本地令牌并跳登录页。
开发阶段在微信开发者工具「详情 → 本地设置」勾选「不校验合法域名…TLS 版本以及 HTTPS 证书」，
手机首次进入需在小程序「…」→ 打开调试放行 http。
正式发布要 HTTPS + 已备案域名并在小程序后台配 `request` 合法域名（清单在 [DEPLOY.md](../DEPLOY.md)）。
细节与页面清单见 [miniprogram/README.md](../miniprogram/README.md)。

## 7. Python SDK 与命令行

SDK 覆盖除 `/api/settings` 之外的全部端点；评测结果与版本对比返回强类型对象。

```python
from harness_client import TransportationHarnessClient

with TransportationHarnessClient(base_url="http://<你的服务地址>:8765",
                                 token="<AUTH_TOKEN>") as client:      # 机器令牌通道
    print(client.health()["case_count"], client.health()["versions"])
    result = client.run_eval(version="v2")                 # 强类型 EvalResult
    print(result.version, result.passed_count, result.total, result.accuracy, result.report_id)
    v0 = client.run_eval(version="v0")
    diff = client.compare(v0.report_id, result.report_id)  # 逐用例差分
    print("新通过:", diff.newly_passed, "回归:", diff.regressed)   # 回归非空即应阻止合入

# 只有账号口令时(没有 AUTH_TOKEN)走登录通道,SDK 自己持有会话 Cookie:
# TransportationHarnessClient(base_url="...", username="admin", password="<你的口令>")
```

命令行（装完 SDK 即得，本机起服务后不用传地址就能用）：

```bash
harness-client health
harness-client versions
harness-client datasets
harness-client analyze --version v2 --dataset rain_peak
harness-client eval --version v2
```

`eval` 的真实输出形如：

```
v2 于 evalset_v1:13/13 通过(100.0%)
报告:report_v2_<时间>
```

地址与令牌也可以用环境变量 `HARNESS_BASE_URL` / `HARNESS_TOKEN` 提供；
命令行出错时统一返回退出码 1 并把 `错误:…` 写到 stderr。
更多场景（CI 守回归、批量沉淀）见 [docs/INTEGRATION.md](INTEGRATION.md)。

## 8. Docker 与生产部署（导读）

本手册不管上线，只给入口：**镜像 `python:3.12-slim`、非 root（UID 1000）运行、
`/api/health` 做健康检查、`cases/`、`evalsets/`、`reports/`、`pipeline/data/`、`drafts/`、
`llm_cache/` 挂成数据卷**（容器重建不丢评测资产）。三条路线（内网穿透演示 /
云服务器 Docker + Nginx + HTTPS / 免费托管平台）与 systemd 常驻写法、备份 cron、
小程序发布清单都在 [DEPLOY.md](../DEPLOY.md)。

最快的容器起法（先按 `.env.example` 准备 `.env`，公网必须设强随机 `AUTH_TOKEN`）：

```bash
docker compose up -d --build
docker logs -f transportation-harness
```

## 9. 常见故障

| 现象 / 报错原文 | 原因 | 处理 |
| --- | --- | --- |
| `缺少依赖 'fastapi':请先在当前 Python 环境执行  pip install -r requirements.txt` | `python webapp/app.py` 的进程里没有装 FastAPI（虚拟环境没激活，或装到了另一个解释器） | 先 `pip install -r requirements.txt`，再确认 `python --version` 与 `pip` 指向同一个环境 |
| `ModuleNotFoundError: No module named 'harness_client'` | 没装仓库内 SDK（`tests/test_sdk.py` 与所有 SDK 示例都要它） | `pip install ./sdk`；CI 里这一步是显式的一步，别指望仓库根目录能 import 到 |
| 裸 `pytest` 收集期 `ModuleNotFoundError: No module named 'harness'`、退出码 2 | `pytest` 不把当前目录放进 `sys.path`（`python -m pytest` 才会），`pyproject.toml` 里的 `pythonpath = ["."]` 就是修这个的 | 别删那一行；被误删后重新加回 `[tool.pytest.ini_options] pythonpath` |
| `POST /api/cases` 得 `400 {"detail":"路段 'S-99' 不在该数据集中(可用:S-01, S-02, …)"}` | `segment` 必须是所选数据集中存在的路段 ID | 先 `GET /api/segments/{dataset}` 或看板下拉取合法 ID；数据集名写错会得到 `404 未知数据集 …` |
| `python scripts/run_eval.py --version v9` → `argument --version: invalid choice: 'v9' (choose from 'v0', 'v1', 'v2', 'v3')`，退出码 2 | 版本必须已在 `pipeline/versions.py` 的 `PIPELINES` 里登记 | 想验新版本就照第 5 节末登记 `analyze_v4`；只是打错则改用已登记版本 |
| `python scripts/run_eval.py --evalset no_such_set` → `FileNotFoundError: [Errno 2] No such file or directory: '…\\evalsets\\no_such_set.json'` | CLI 直读文件，不做 404 包装 | 评测集名取 `evalsets/*.json` 的文件名；HTTP 侧同样的错误会返回 `404 评测集不存在 …(可选:…)` |
| `python -m harness.evolve --baseline v3` → `错误:'v3' 已是最新登记版本,其后没有待验证的版本…`（退出码 1）；HTTP 侧 `POST /api/evolve/run {"baseline":"v2"}` → `400` 同文案 | 基线传了最末登记版本,其后没有可验证的迭代版本(1.6.0 起明确报错,不再 IndexError) | 基线传「上一个版本」（登记 v4 之后用 `--baseline v3`）；只想看单版本表现用 `python scripts/run_eval.py --version v3` |
| 受保护业务接口得 `403 {"detail":"初始口令尚未修改,业务接口暂不开放:…"}`（登录模式，机器令牌/已登录会话同样被挡） | 初始口令未改（`/api/health` 的 `default_credentials` 为 true），门禁只放行 `/api/health` 与 `/api/auth/*` | 用控制台打印的初始口令登录 → 看板「改密」;或在启动环境设 `ADMIN_PASSWORD` 后重启(部署者自备凭据,见 [DEPLOY.md](../DEPLOY.md)) |
| `GET /api/settings` → `403 {"detail":"运行时配置接口未启用:/api/settings 能读写服务器本地的 .env(含密钥),默认关闭。确需使用请在服务启动环境里设 SETTINGS_ENABLED=1 并重启服务;开启后非本机访问仍必须携带已登录会话。"}` | 该接口默认关闭，且只在启动时读一次 | 在服务器环境里设 `SETTINGS_ENABLED=1` 并重启；机器令牌 `X-API-Token` 永远不能用于该接口（设计如此，见 [AGENTS.md](../AGENTS.md) 鉴权事实） |
| 从本机以外访问 `/api/settings` → `403 {"detail":"/api/settings 仅允许本机直连或已登录会话访问。…"}`；经 Nginx 反代后从本机访问也被拒 | 反代之后 TCP 对端恒为 `127.0.0.1`，但请求带 `X-Forwarded-For` 等转发头 → 不算「本机直连」 | 带已登录会话（Bearer 或 Cookie），或在服务器本机浏览器里打开 `127.0.0.1:8765` |
| 受保护接口得 `401 {"detail":"未登录或会话已过期"}` | 三种凭据都没带或都无效 | 依次检查：`X-API-Token` 是否等于服务端 `AUTH_TOKEN`（改了要重启）、会话令牌/Cookie 是否过期（7 天）、`AUTH_MODE` 是否 `login` |
| 登录得到 `429 {"detail":"失败次数过多,账号已锁定,请 600 秒后重试"}` | 同一用户名连续失败 5 次锁定 10 分钟（服务端限流） | 等倒计时结束；小程序/脚本不要自动重试，那只会延长锁定 |
| 看板一直停在登录页、控制台没有 `Set-Cookie` | 反向代理改了协议或 `COOKIE_SECURE=1` 却在用 http | http 部署别设 `COOKIE_SECURE`；HTTPS 部署设 `COOKIE_SECURE=1` 并用 https 访问 |
| `python -m pytest` 报 `Pillow` 缺失（`tests/test_pwa.py` 收集期） | `Pillow` 在 `requirements-dev.txt` 里声明（校验 PWA 图标尺寸与 maskable 透明通道），干净环境没装 | `pip install -r requirements.txt -r requirements-dev.txt`；这两类「胖本地环境跑得过、干净环境跑不过」的坑已在 CI 修过一轮 |
| Windows 管道里中文变成 `δ¼Ựѹ` 之类乱码 | 控制台/子进程按 GBK(cp936) 编解码，而捕获方按 UTF-8 解 | 捕获前 `set PYTHONIOENCODING=utf-8`（评测与校验脚本自带 UTF-8 重配置，第三方输出未必） |
| 跑完评测/自进化后 `git status` 多出 `reports/…` 若干文件 | 这些命令就是会写归档（`report_*`、`evolution_*.json`、`.md`） | 归档即历史，正常一起提交；只是试跑就删掉新增文件再提交，别留半套不一致的归档 |
| `python scripts/verify.py` 报 `FAIL  v1 通过集 ⊇ v0 通过集(丢失 ['rc-0014'])`，同时 `[4]` 只给 WARN | 新沉淀的用例基线恰好判对、v1/v2 判错：`[2]` 单调性是对全量通过集做的，新用例也会参与；脚本头注释「新用例只 WARN 不判失败」只对 `[4]` 成立 | 这不是回归（回归的定义是「老用例被改坏」）。要么把该用例的期望改成与现有分级口径一致，要么接受这条 FAIL 并把 `rc-0014` 当作 v3 的靶子，等 v3 修好后 `[2]` 自然绿 |

## 10. 术语小词典

| 词 | 在这里指什么 |
| --- | --- |
| badcase | 线上被用户点踩/抽检发现的错误分析结果，还没有变成任何可执行的东西 |
| replaycase（用例） | 一条可重放的坏例：复现它需要的数据集 + 判分规则 `checks` + 标签与来源，存成一个 JSON 文件 |
| check（判分规则） | 用例里的一条断言，如 `classify`（某路段等级应为 X）、`metric`（某指标应在 `expected±tol` 内）、`no_crash`、`recommendations`、`congested_empty`、`conclusion_keyword`、`conclusion_quality` |
| 评测集（evalset） | 一份 `case_ids` 的版本化清单；重放顺序就是清单顺序，按场景可以有多份（如雨天） |
| 判分器（judge） | 执行 checks 的组件；规则判分确定性、LLM 判分管文本质量，按类型路由，可插拔 |
| 自进化（evolve） | 把迭代纪律写成流程：基线测量 → 逐个已登记版本验证 → 「提升且无回归」才认 → 收益 <5% 即停 → 归档 |
| 回归 | 新版本把原本通过的用例改坏了；一票否决，`/api/compare` 的 `regressed` 非空就是这个 |
| LLM-as-Judge | 让大模型按评分细则（覆盖性/可执行性/简洁性）给结论文本打 0~1 分，`conclusion_quality` 检查类型；分数与理由随报告落盘可复核，模型故障则降级为「未通过 + 原因可见」 |
| 杀伤（变异分数） | 一套测试能杀掉多少「故意注入的故障」：把代码改坏一点，测试若还全绿就说明没杀伤力。**本仓库没有引入变异测试工具**，所以不报这个指标；它的等价防护是「通过集单调不减 + 用例断言可失败」，即新沉淀的用例必须能真的把不合格版本判 FAIL |
| 管线版本 v0~v3 | 被测的交通分析实现:v0 是带已知缺陷的基线,v1 修公式与分级,v2 精修边界与聚合,v3 扩展排队回溢升级带;登记在 `pipeline/versions.py` 的 `PIPELINES` 里,新版本加一行即可被评测与自进化认得 |
| 全局拥堵指数 | 一个数据集层面的拥堵数字：v1 按有效路段简单平均，v2 改为按流量加权并对单点 V/C 以 1.2 封顶 |
| 边界升级 | v2 的规则：V/C ∈ [0.75, 0.8) 且速度比 < 0.35 时把等级抬到「拥堵」，让"实际体验"和"数字"对齐 |
| 看板（PWA） | `webapp/static/index.html` 那个单文件前端；装了 manifest + Service Worker，所以能被浏览器当应用安装、断网时回退到缓存数据 |
| AI 草稿（draft） | LLM 从反馈原文起草的用例（状态 `pending`），**人工确认后才进 `cases/`**；未配密钥时由离线 Mock 起草，链路完全一样 |
| 离线确定性 Mock | 没有模型密钥时 LLM 层的替身实现：输出只由输入决定、不联网、零成本。它保证的是「工作流编排可离线演示与测试」，不保证与真实模型同等语义质量 |

## 11. 改完之后跑什么

```bash
ruff check .
python -m pytest
python scripts/verify.py
python scripts/check_release.py
```

通过标准：`All checks passed!`、`199 passed`、末行 `VERIFY PASS`、末行 `RELEASE CHECK PASS`，
四条退出码都是 0。这四条就是 CI 的全部步骤；动了端点还要 `python scripts/export_openapi.py`
重导规范并同步 `docs/API.md`、`webapp/static/help.html`、`sdk/`。各项改动对应跑什么，
见 [AGENTS.md](../AGENTS.md) 的「改动后的验证」。
