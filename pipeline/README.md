# pipeline/ —— 被测的交通分析管线

> 用途：说明本目录负责什么、版本怎么登记、数据集字段与口径。

这里放**被测对象**：把路段流量数据换成拥堵分级、指标、处置建议和一句结论。
它不被评测框架反向依赖 —— `harness/` 只要求「输入 `list[dict]`、输出 `dict` 的纯函数」。
工况（雨天、事故、晚高峰）一律建模在 `data/*.json` 的参数里，代码不分支，
所以「加一个场景」是加数据而不是改算法。

## 文件清单

| 文件 | 干什么 | 备注 |
| --- | --- | --- |
| `versions.py` | 四版管线 `analyze_v0`/`analyze_v1`/`analyze_v2`/`analyze_v3` + 两张登记表 `PIPELINES`（版本名 → 函数）与 `CHANGELOG`（版本名 → 名称与本轮优化内容） | 全项目的版本事实来源：看板、CLI、`/api/versions`、报告、自进化都读这两张表 |
| `data/base.json` | 常规早高峰，10 个路段，标定其它情景的基线 | 6 个数据集之一，字段见下 |
| `data/rain_peak.json` | 雨天早高峰：通行能力按 0.85 折算、车速普降 | `evalset_scenario_rain` 用它 |
| `data/incident.json` | 突发事故占道：S-03 车道 6→5、上游车流转移 | |
| `data/evening_peak.json` | 晚高峰通勤：潮汐方向反转、流量重分布 | |
| `data/missing_volume.json` | 11 个路段，S-09 的 `volume` 为 `null`（传感器故障） | 喂给 v0 会崩溃，v1/v2 标「数据缺失」并从聚合剔除 |
| `data/empty.json` | `segments: []`（上游管道故障） | v0 在这里抛 `ZeroDivisionError` |
| `__init__.py` | 一行 docstring | 包标记 |

## 子目录

| 子目录 | 负责 |
| --- | --- |
| `data/` | 6 个情景数据集，文件名就是数据集名（`base` `rain_peak` `incident` `evening_peak` `missing_volume` `empty`）；「加一个场景」= 加一个这样的 JSON，不改代码 |

本目录只有这一个二级目录（`__pycache__/` 是本地字节码，`.gitignore` 已挡）。逐文件的路段数（复核，在仓库根执行：
`python -X utf8 -c "import glob,os,json;print({os.path.basename(p)[:-5]:len(json.load(open(p,encoding='utf-8'))['segments']) for p in sorted(glob.glob('pipeline/data/*.json'))})"`）
→ `{'base': 10, 'empty': 0, 'evening_peak': 10, 'incident': 10, 'missing_volume': 11, 'rain_peak': 10}`。

读它的只有 `harness/storage.py` 的 `DATA_DIR`（`load_dataset()` 按名取文件、`list_datasets()` 遍历 glob），
`webapp/app.py:330` 的「未知数据集」报错也用它列可选项；**仓库里没有任何代码写这个目录**——它是手工维护的资产
（复核，在仓库根执行：`grep -rn "DATA_DIR" --include=*.py . | grep -v __pycache__` → 4 行，全是读）。
`python scripts/backup.py` 会把它与 `cases/`、`evalsets/`、`reports/` 一起打包。字段与口径见下一节。

## 数据集格式

顶层字段：`dataset_id`、`description`、`captured_at`、`segments`，可选 `scenario`
（`{"tag","insight"}`，看板「分析提交」页的场景解读来自它；`empty`/`missing_volume` 没有）。

每个路段的字段（`data/base.json` 的真实一条）：

```json
{"segment_id": "S-07", "name": "科技园路", "length_km": 3.5, "lane_count": 2,
 "capacity_per_lane": 1600, "volume": 990, "speed": 40, "free_flow_speed": 60}
```

| 字段 | 用途 |
| --- | --- |
| `lane_count` × `capacity_per_lane` | 路段通行能力；`volume / 能力` 即饱和度 V/C |
| `volume` | 流量；为 `null` 时 v1/v2 走「数据缺失」分支 |
| `speed` / `free_flow_speed` | 速度比与延误指数；v0 只看 `speed` 分级（这是它的缺陷来源） |

文件名就是数据集名：`storage.load_dataset("base")` 读 `pipeline/data/base.json`，
名字先过 `_safe_name()` 白名单（防 `../`）。

## 四个版本的差异（一句话版）

| 版本 | 分级依据 | 饱和度 | 延误指数 | 缺数据 / 空数据 | 处置建议 | 全局指数 |
| --- | --- | --- | --- | --- | --- | --- |
| v0 | 只看 `speed` 四档 | `round(volume / capacity_per_lane)`，漏乘车道数且取整 | `(speed - ffs) / ffs`，方向写反 | 直接崩溃（`TypeError` / `ZeroDivisionError`） | 无 | 有效路段简单平均 |
| v1 | V/C 五级（0.4/0.6/0.8/1.0） | `volume / (capacity_per_lane × lane_count)`，2 位小数 | `max(0, (ffs - speed) / ffs)` | 标「数据缺失」并从聚合剔除 | 每个拥堵/严重拥堵路段一条 | 有效路段平均 |
| v2 | 同 v1 + 边界升级（V/C∈[0.75,0.8) 且速度比<0.35 → 拥堵） | 同 v1 | 同 v1 | 同 v1，空输入返回空结果集、指数为 `null` | 同 v1 | 按流量加权，单点 V/C 以 1.2 封顶 |

统一输出结构（所有版本一致，判分器只认这个）：

```json
{"version": "v2", "segments": [{"segment_id","name","classification","saturation",
  "delay_index","speed_ratio","status","volume"}],
 "congested_segments": ["S-10","S-05","S-02","S-03","S-11"],
 "global_congestion_index": 0.7944, "recommendations": [{"segment_id","text"}],
 "summary": "共分析 10 个路段(有效 10 个,数据缺失 0 个)…"}
```

`v0` 的行不含 `volume` 字段（其余字段齐全）—— 有测试对这条负断言，别"顺手补上"。

## 和谁打交道

- **上游**：`cases/*.json` 的 `dataset_name` 与 `POST /api/analyze` 决定跑哪个数据集。
- **下游**：`harness/runner.py` 重放时调用；`llm/workflows.py` 用 v2 的判定给 AI 起草当参照。
- **改完要跑**：`python -m pytest tests/test_versions.py -q` + `python scripts/verify.py`
  （后者第 [5] 组直接断言 v2 在 `base`/`missing_volume`/`empty` 上的数值与降级行为）。

## 别动

- **不要往管线里塞场景分支**（`if rain: ...`）。场景属于数据：改 `capacity_per_lane`、
  `volume`、`speed` 就够了，这样同一份代码能被任意评测集检验。
- **不要就地修 v0**：v0 的价值就是「带已知缺陷的基线」，`verify.py` 的种子冻结与
  `tests/test_versions.py::TestV0KnownDefects` 都靠它。要改进请**新增版本**并登记。
- 登记新版本必须同时加 `PIPELINES` 与 `CHANGELOG` 两处，只加一处会在报告或看板上露馅；
  加完 `python -m harness.evolve --baseline v2` 增量验证（基线别传最后一个已登记版本）。
- 分级阈值 `0.4/0.6/0.8/1.0` 是城市道路 V/C 常用口径，也是 13 条种子用例的期望依据；
  改阈值等于改判分标准，必须连带复核 `cases/` 与 `tests/fixtures/cases/`。
