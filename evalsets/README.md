# evalsets/ —— 版本化评测集清单

> 用途：说明评测集是什么、清单字段与顺序的含义、改它要跑什么。

评测集 = 一组 `case_id` 的**有序清单**，是「评什么」与「按什么顺序评」的唯一答案。
用例本体在 `cases/`，这里只存引用，所以扩充评测集就是往清单里加一个 ID，
不需要复制用例；反过来，删除用例时 `storage.delete_case()` 会同步把所有清单里的该 ID 摘掉，
保证不出现悬空引用。

## 文件清单

| 文件 | `evalset_id` | 条数 | 覆盖 |
| --- | --- | --- | --- |
| `evalset_v1.json` | `evalset_v1` | 13 | 8 月底线上反馈沉淀的种子用例（`rc-0001..rc-0013`），8 个失败标签 |
| `evalset_scenario_rain.json` | `evalset_scenario_rain` | 3 | 雨天早高峰场景（`rsc-001..003`），数据集 `rain_peak` |

（复核：`python -c "import glob,json;print({p: len(json.load(open(p, encoding='utf-8'))['case_ids']) for p in glob.glob('evalsets/*.json')})"`，
Windows 下输出 `{'evalsets\\evalset_scenario_rain.json': 3, 'evalsets\\evalset_v1.json': 13}`）

## 清单格式

```json
{
  "evalset_id": "evalset_scenario_rain",
  "description": "雨天早高峰场景评测集:检验恶劣天气下的分级与指标稳健性(3 条)",
  "created_at": "2026-09-05",
  "case_ids": ["rsc-001", "rsc-002", "rsc-003"]
}
```

| 字段 | 谁在用 | 注意 |
| --- | --- | --- |
| `evalset_id` | 报告与看板显示的评测集名；缺省时 `storage.load_evalset()` 用文件名兜底填 | 要与文件名一致，否则 `/api/eval/run` 返回的 `evalset_id` 会跟请求名不同 |
| `description` | 看板、自进化 Markdown 报告抬头 | 无 |
| `created_at` | 列表展示 | 无 |
| `case_ids` | **顺序就是重放顺序**；`load_evalset_cases()` 按它取用例 | 有重复 ID 会被重复重放（不去重）；引用不存在的 ID 直接 `KeyError` → API 回 `400` |

文件名即评测集名，`storage` 先过 `_safe_name()` 白名单（只允许字母、数字、下划线、连字符、中文），
所以 `..` 之类的名字会得到 `400 非法评测集名`。

## 新建一份评测集

没有专门的接口，直接加文件即可：

1. 先沉淀用例（`POST /api/cases`，或把 `add_to_evalset` 设为 `false` 只入库不进集）；
2. 在 `evalsets/` 下新建 `<名字>.json`，按上面的格式写 `case_ids`；
3. 跑 `python scripts/verify.py --evalset <名字>` 与
   `python scripts/run_eval.py --version v2 --evalset <名字>` 确认能重放；
4. 看板的评测集下拉（`GET /api/evalsets`）自动列出它，不需要改前端。

场景化评测的价值在于**同一份管线跑不同评测集**：例如
`python scripts/run_eval.py --version v0 --evalset evalset_scenario_rain` 得到 `0/3`，
而 v0 在主评测集上是 `1/13` —— 两个视角暴露的是不同的弱点。

## 和谁打交道

- **上游**：`scripts/seed_cases.py`、`scripts/seed_scenario_cases.py`（整体重写清单）、
  `storage.add_case_to_evalset()`（沉淀时追加，默认加进 `evalset_v1`）。
- **下游**：`harness/runner.run_evalset()`、`harness/evolve.py`、`/api/eval/run`、
  `/api/evolve/run`、`/api/evalsets`、看板与小程序的评测集选择器。
- **改完要跑**：`python scripts/verify.py` + `python -m pytest tests/test_storage.py tests/test_webapp.py -q`。

## 别动

- 不要往 `evalset_v1` 里塞与种子无关的用例后又改 `verify.py` 的 `SEED_CASE_IDS`：
  种子冻结断言（v0 只过 rc-0013、v1 剩 rc-0009/rc-0010、v2 全过）是这个仓库的可信基线。
  新场景请开新评测集（像 `evalset_scenario_rain` 那样）。
- 默认沉淀目标写死在 `storage.add_case_to_evalset(case_id, name="evalset_v1")`，
  要进别的集得改调用方（`app.py` 目前不传 name），别靠手工挪文件。
- `reports/` 里的每份报告都记着它属于哪个 `evalset_id`；
  改名或删清单会让历史报告在看板上「找不到评测集说明」，归档不要动。
