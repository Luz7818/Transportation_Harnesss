# scripts/ —— 命令行工具箱

> 用途：说明每个脚本管哪一段、命令怎么写、成功输出长什么样、失败会是什么样。

这些脚本都不启动 HTTP 服务（`export_openapi.py` 只导入应用取 schema），
从仓库根目录以 `python scripts/<名>.py` 运行；它们复用 `harness/` 的类，
所以**会读写评测资产**——哪几个会写文件，见下面每条的「写入」列。

## 文件清单

| 文件 | 干什么 | 写入 | 关键行为 |
| --- | --- | --- | --- |
| `seed_cases.py` | 沉淀 13 条种子 replaycase 并生成 `evalset_v1` 清单（内容硬编码在脚本里，含 `created_at` 固定值） | `cases/<标签>/rc-*.json`、`evalsets/evalset_v1.json` | 幂等：按 `case_id` 覆盖同名文件；清单里的 `case_ids` 会被整体重写为脚本内顺序 |
| `seed_scenario_cases.py` | 沉淀雨天场景 3 条用例（`rsc-001..003`）并生成 `evalset_scenario_rain` | `cases/雨天场景/`、`evalsets/evalset_scenario_rain.json` | 期望值按 v2 公式人工核算（脚本头注释给了算式） |
| `run_eval.py` | 单版本评测 CLI：重放 → 判分 → 打印逐用例结果 → 归档 JSON | `reports/report_<v>_<时间>.json`（`--md` 再加 `.md`） | `--version` 只能取已登记版本；耗时与得分来自 `EvalResult` |
| `verify.py` | 端到端不变量校验（CI 的第三步） | 不写（只读 `reports/` 判断归档是否齐） | 断言种子行为冻结、通过集单调不减、v2 关键数值与降级、归档存在；新沉淀用例只给 WARN（但见「注意」） |
| `backup.py` | 评测资产一键打包 zip | `backups/harness_backup_<时间>.zip`（`backups/` 已 gitignore） | 收 `cases/`、`evalsets/`、`reports/`、`pipeline/data/`，跳过 `__pycache__` |
| `export_openapi.py` | 离线导出 FastAPI 的 OpenAPI 3.1 规范 | `docs/openapi.json`（默认，可用 `--out` 改写别处） | 导出前把 `AUTH_MODE=login`、`AUTH_TOKEN=export-placeholder` 固定下来，保证 schema 稳定 |
| `generate_pwa_icons.py` | 从 `webapp/static/assets/icon.svg` 栅格化 PWA 图标四件套，并内联组合 `logo-lockup.svg`、`banner.svg` | `webapp/static/assets/` 下 4 个 PNG + 2 个 SVG（都入库） | 需要 `resvg-py`（不在 `requirements*.txt` 里，属可选工具链）；缺它直接退出并给安装提示 |

## 命令与真实输出

```bash
python scripts/seed_cases.py
```

```
沉淀 rc-0001 [阈值错误] -> cases\阈值错误\rc-0001.json
...
沉淀 rc-0013 [回归保护] -> cases\回归保护\rc-0013.json
生成评测集清单 -> evalsets\evalset_v1.json(共 13 条)
```

`python scripts/seed_scenario_cases.py` 同构，末行 `生成评测集清单 -> evalsets\evalset_scenario_rain.json(共 3 条)`。
（Windows 下路径分隔符是反斜杠，Linux/macOS 是正斜杠。）

```bash
python scripts/run_eval.py --version v2
python scripts/run_eval.py --version v1 --md
python scripts/run_eval.py --version v0 --evalset evalset_scenario_rain
```

预期分别是 `13/13 通过(100.0%)`、额外一份 Markdown 归档、`0/3 通过(0.0%)`。
逐用例表格的「说明」列就是判分明细原文，例如 v0 那行
`期望「拥堵」,实际「严重拥堵」; 期望 0.91±0.01,实际 2`。

```bash
python scripts/verify.py
python scripts/verify.py --evalset evalset_scenario_rain
```

```
[1] 得分轨迹(evalset=evalset_v1,共 13 条 case)
  PASS  v0 得分 1/13
  PASS  v1 得分 11/13
  PASS  v2 得分 13/13
...
VERIFY PASS:最小闭环与两轮自进化结果全部符合预期。
```

退出码 0 才算过；不通过时末行是 `校验未通过:[<检查名>, ...]` 且退出码 1。
跑指定评测集时第 [3] 组会打印 `种子不变量(非 evalset_v1,跳过)`。

```bash
python scripts/backup.py
python scripts/backup.py --out D:/备份目录
```

```
备份完成:C:\<项目所在路径>\backups\harness_backup_20260927_033533.zip(53.3 KB)
```

（默认输出目录是仓库根的 `backups/`，脚本按绝对路径打印；`--out` 给相对路径时按其原样打印，
例如 `tmpbak\harness_backup_20260927_033533.zip`。）体积随 `reports/` 增长；
服务器上按 cron 每日跑（写法见 [DEPLOY.md](../DEPLOY.md) 的备份一节）。

```bash
python scripts/export_openapi.py
```

```
OpenAPI 3.1.0 -> docs\openapi.json
路径数:29;分组:analysis, auth, cases, eval, llm, metadata, pages, reports, settings
导入指引:Postman/Apifox -> Import -> 该 JSON 文件
```

改了任何端点、请求体字段或响应模型都要重跑它，并同步 `docs/API.md` 与
`webapp/static/help.html`（约定写在 [AGENTS.md](../AGENTS.md)）。

```bash
python scripts/generate_pwa_icons.py
```

```
webapp\static\assets\icon-192.png  (24168 bytes)
webapp\static\assets\icon-512.png  (89855 bytes)
webapp\static\assets\icon-maskable-512.png  (67499 bytes)
webapp\static\assets\apple-touch-icon-180.png  (21994 bytes)
完成:4 个图标 + 横版 Logo + 品牌横幅已生成
```

字节数取决于图标内容，只用于确认「四个都生成了」。改完必跑
`python -m pytest tests/test_pwa.py -q`（断言尺寸与 maskable 不透明）。

## 与另外两个入口的分工

| 想做的事 | 用什么 |
| --- | --- |
| 跑完整自进化并看逐轮轨迹 | `python -m harness.evolve`（不在本目录，属评测框架的 CLI） |
| 只在脚本里调一次评测/对比 | SDK：`harness-client eval --version v2` 或 `client.run_eval(...)`（[sdk/README.md](../sdk/README.md)） |
| 起服务给浏览器/小程序用 | `python webapp/app.py`（[webapp/README.md](../webapp/README.md)） |

## 注意

- `verify.py` 的头注释说「新沉淀、尚未被 v2 覆盖的 case 不判失败，输出 WARN」——
  这只对第 [4] 组成立。第 [2] 组的单调性是对**全量通过集**做的：如果新用例恰好被 v0 判对、
  被 v1/v2 判错，就会 `FAIL v1 通过集 ⊇ v0 通过集(丢失 ['rc-00NN'])` 并返回退出码 1。
  这不是回归（回归指老用例被改坏），处理见
  [docs/getting-started.md](../docs/getting-started.md) 的常见故障表。
- `seed_cases.py` / `seed_scenario_cases.py` 会**整体重写**清单文件：如果你在 `evalsets/*.json` 里
  手工排过 `case_ids` 顺序（重放顺序就是它），跑种子脚本会打回去。
- 种子脚本写的用例与 `tests/fixtures/cases/` 不是同一份：夹具快照多一条 `rc-0014`，
  测试只认夹具，不认 `cases/`。
- `export_openapi.py` 会覆盖 `docs/openapi.json`：先确认端点改动是有意的再跑，
  否则用 `--out` 导到别处做对比。
- 不要给这些脚本加交互式提问：CI 与 cron 都直跑，任何等待输入都会挂住流水线。
