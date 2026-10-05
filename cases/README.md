# cases/ —— replaycase 用例库

> 用途：说明用例怎么分类、一个文件装什么、哪些字段能动。

这里是闭环的核心资产：每条线上反馈落地成一个**可重放的最小评测单元**。
它不是文字描述，而是「重现它所需的输入 + 怎样才算修好 + 属于哪一类失败」三件套，
`harness/runner.py` 能直接把它喂给任意版本管线并自动判分。

## 文件清单

| 文件 | 干什么 | 备注 |
| --- | --- | --- |
| `README.md` | 本文件 | 根下唯一的非用例文件 |

其余文件全在标签子目录里，命名规律：**一个 case 一个文件、文件名就是 `case_id`**
（`rc-NNNN.json` / `rsc-NNN.json`），字段全部写在这一个 JSON 里（不拆多字段文件、不放共享表）。
当前 16 个用例文件（复核，在仓库根执行：
`python -c "import glob;print(len(glob.glob('cases/*/*.json')))"`）。
条数随线上反馈增长，别把这里或下面表格里的数字当成不变量。

## 子目录

**一级子目录 = 失败标签**（`label` 经 `storage.safe_label()` 净化的结果）。10 个目录、18 条用例。
逐目录计数（复核，在仓库根执行；`-X utf8` 是为了在 GBK 控制台里也不乱码）：
`python -X utf8 -c "import os,glob;print({d:len(glob.glob(os.path.join('cases',d,'*.json'))) for d in os.listdir('cases') if os.path.isdir(os.path.join('cases',d))})"`

| 子目录 | 条数 | 这类用例在测什么 | 里面的文件 |
| --- | --- | --- | --- |
| `阈值错误/` | 4 | 拥堵等级判定与 V/C 口径是否一致 | `rc-0001` `rc-0002` `rc-0003` `rc-0011` |
| `指标计算错误/` | 3 | 公式与聚合方式（车道数、加权、方向） | `rc-0004` `rc-0005` `rc-0010` |
| `雨天场景/` | 3 | 恶劣天气数据集 `rain_peak` 上的分级与指标 | `rsc-001` `rsc-002` `rsc-003` |
| `健壮性/` | 2 | 缺字段、空输入不能崩溃 | `rc-0006` `rc-0012` |
| `精度问题/` | 1 | 指标保留位数、禁止取整 | `rc-0008` |
| `结论缺失/` | 1 | 拥堵路段必须有处置建议 | `rc-0007` |
| `边界处理/` | 1 | 临界 V/C 与极低速的升级规则 | `rc-0009` |
| `回归保护/` | 1 | 基线本来就判对的场景，任何版本都不许改坏 | `rc-0013` |
2026-10-05 清理记录：曾存在的空目录 `未分类/`、`批量演示/`（连同根目录遗留的
`batch_demo_ids.txt`）已删除。目录不用手工预建 —— `storage._write_json()` 会
`mkdir(parents=True)`，真有空标签或新类别的沉淀时目录会自动重建。

标签净化在 `harness/storage.py` 的 `safe_label()`：非法文件名字符替换为 `_`，空标签兜底为 `未分类`。
所以 HTTP 传进来的新标签会当场开一个新目录 —— 这是有意的（失败类别应当能长出来）。
`rsc-` 前是用雨天情景数据集的用例，`rc-` 前是主评测集；前缀不是强制规则，
但 `POST /api/cases` 只会生成 `rc-NNNN`（取当前最大 `rc-` 序号 +1）。

## 文件内容（一个真实例子：`cases/阈值错误/rc-0001.json`）

```json
{
  "case_id": "rc-0001",
  "title": "学府路(V/C 0.91)被按车速误判为「严重拥堵」",
  "label": "阈值错误",
  "dataset_name": "base",
  "checks": [
    {"type": "classify", "segment": "S-02", "field": null, "expected": "拥堵",
     "tol": 0.01, "keywords": [], "min_score": 0.7},
    {"type": "metric", "segment": "S-02", "field": "saturation", "expected": 0.91,
     "tol": 0.01, "keywords": [], "min_score": 0.7}
  ],
  "source": "线上点踩",
  "created_at": "2026-08-31T00:39:00",
  "notes": "用户反馈:该路段饱和度已超 0.9,按 V/C 标准应为「拥堵」;基线只看车速直接判成严重拥堵。"
}
```

| 字段 | 谁在用 | 注意 |
| --- | --- | --- |
| `case_id` | 评测集清单、看板、`/api/cases/{id}`、文件名 | 全局唯一，已删除的 ID 不要复用 |
| `title` / `label` | 报告、看板、目录名、失败聚类 | 沉淀接口限 1~80 / 1~20 字符 |
| `dataset_name` | `storage.load_dataset()` → `pipeline/data/` 下的文件名 | 必须存在，否则重放报错 |
| `checks` | `judge.py` 按 `type` 路由判分 | **全部通过才算这条用例通过**；一条用例可以有多条 check |
| `source` | 溯源（线上点踩 / 人工标注 / 网页提交 / LLM 草稿·人工确认 …） | 沉淀接口写入时截断到 20 字符 |
| `created_at` | 看板「最近动态」排序 | 手工新增用例时请写真实时间（ISO 秒级） |
| `notes` | 人工阅读上下文；草稿确认时兜底沿用反馈原文 | 无长度校验（`docs/API.md` 里那句 ≤200 是文档口径，服务端不拦） |

`checks[].type` 可用值：`classify`、`metric`、`no_crash`、`recommendations`、
`congested_empty`、`conclusion_keyword`、`conclusion_quality`（最后一种由 `llm/judge.py` 的
LLM 判分，未配密钥时走离线 Mock；rc-0015 首次用到它）。字段语义见
[docs/API.md](../docs/API.md) 的「checks 的 type 取值」。

## 和谁打交道

- **上游**：`scripts/seed_*.py`（首批种子）、`POST /api/cases`（看板/小程序/SDK 沉淀）、
  `POST /api/llm/drafts/{id}/confirm`（AI 草稿经人工确认）。
- **下游**：`evalsets/*.json` 按 `case_id` 引用它们；`harness/runner.py` 重放；
  `harness/activity.py` 把「沉淀了哪条用例」推进看板时间流。
- **改完要跑**：`python scripts/verify.py`（第 [1]~[4] 组直接读这里的用例）
  + `python -m pytest tests/test_storage.py tests/test_judge.py -q`。

## 别动

- 不要手改 `checks[].expected` 去迁就某个版本的输出 —— 那等于把「什么是对的」写成
  「现在是什么」，评测集就失去裁决能力。要改进请新增版本并登记。
- 不要删除 `回归保护/rc-0013.json`：它是 v0 唯一通过的用例，`verify.py` 的种子冻结断言
  和 13 条清单都指着它。
- 不要让 `cases/` 与 `tests/fixtures/cases/` 混为一谈：测试只读后者（冻结快照，多一条 `rc-0014`）。
- 不要把用例文件放到 `cases/` 根下：`storage.load_cases()` 的 glob 是 `cases/*/*.json`，
  根下的文件不会被读到，表现为「用例存在但永远不跑」。
