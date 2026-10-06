# harness/ —— 评测框架（领域无关）

> 用途：说明本目录管哪一段、每个文件干什么、改完要跑什么。

这里是「badcase → 评测集 → 迭代 → 回归验证」闭环的引擎，与交通无关：
它读 `cases/` 与 `evalsets/` 里的资产、调用外部登记的 `analyze(segments) -> dict` 函数、
按用例自带的 `checks` 判分、把结果写成 `reports/` 归档。
去掉它，仓库就只剩一份交通算法脚本，没有任何可重放、可回归的能力。

依赖方向是硬约束：本目录**不 import** `pipeline/`、`llm/`、`webapp/`
（被测管线由调用方注入，判分器由 `BaseJudge` 子类注入）。

## 文件清单

| 文件 | 干什么 | 备注 |
| --- | --- | --- |
| `paths.py` | 项目根定位（全仓唯一）：源码模式按本文件位置向上找仓库根；exe 封装模式优先读启动器设的 `HARNESS_HOME` | `cases/`、`evalsets/`、`reports/`、`.env`、`static/` 都从这里出发；其余模块一律引用这里，不要自写 `Path(__file__)` 向上找（契约见 `../packaging/README.md`） |
| `models.py` | 四个数据结构：`CheckSpec`（单条判分规则）、`ReplayCase`、`CaseResult`、`EvalResult` | 只有 `to_dict()`/`from_dict()`；`from_dict` 会丢弃未知字段，所以加字段是兼容的、改名不是 |
| `storage.py` | 落盘读写：`cases/`（按标签分目录）、`evalsets/`、`pipeline/data/`、`reports/` | 原子写（临时文件 + `os.replace`）+ 进程锁 + 路径白名单 `_safe_name()`；`delete_case()` 同步清理所有评测集清单 |
| `judge.py` | 判分器：`RuleJudge`（`classify`/`metric`/`no_crash`/`recommendations`/`congested_empty`）、`HeuristicJudge`（`conclusion_keyword`）、`CompositeJudge`（按 `spec.type` 路由）、`case_score()` | 路由不到 judge 时该检查判失败并写明「没有任何 judge 支持规则类型 X」；`LLMJudge` 在 `llm/judge.py`，懒加载、失败即退回纯规则 |
| `runner.py` | `ReplayRunner`：逐用例加载数据集 → 跑管线 → 判分 → 汇总 `EvalResult`（总分、分标签统计、耗时） | 管线抛异常被吞成 `error` 字段并照常判分 —— 「崩溃」本身就是被测行为（`no_crash` 类用例） |
| `report.py` | 报告：`build_payload()`（看板/对比用的 JSON）、`render_markdown()`（code-optimization 模板：基线 → 【优化版本】→ 最终总结）、`diff()` | `diff()` 只对两轮**共有**的用例判新通过/回归，评测集扩充过也不会误报 |
| `evolve.py` | 自进化主流程 `run_evolution()` + CLI（`python -m harness.evolve`） | 基线 → 逐个登记版本验证 → 提升且无回归 → 收益 <5% 或全通过即停；上限 `EVOLVE_MAX_ROUNDS`（默认 2），未验证版本进 `pending_versions`；三份归档都在这儿写 |
| `activity.py` | 看板「最近动态」的读模型：把用例沉淀、评测、自进化、AI 草稿聚合成倒序时间流 | 只读聚合，不引入新写入路径；草稿列表由调用方注入（保持不依赖 `llm/`）；`limit` 被钳在 1~50 |
| `__init__.py` | 空文件 | 只作为包标记 |

## 判分口径（写文档/排错时最容易踩的三条）

- **一条用例全过才算过**：`case_score()` 返回 `(全部 passed, 通过检查数/总检查数)`，
  所以报告里 `score=0.5` 但 `passed=false` 是正常状态。
- **accuracy = 通过的用例数 / 用例总数**（`runner.py` 保留 4 位小数），不是检查项的通过率。
- **等级判定看字符串相等**：`classify` 拿管线输出的 `classification` 与 `expected` 直接比较，
  六档取值见 `webapp/app.py` 的 `VALID_LEVELS`；拼错等级不会报错，只会永远 FAIL。

## 和谁打交道

- **上游**：`cases/`、`evalsets/`、`pipeline/data/`（读）；被测函数由 `pipeline/versions.py` 的 `PIPELINES` 提供。
- **下游**：`reports/`（写）；`webapp/app.py` 与 `scripts/` 调用这里的类；`llm/workflows.py` 复用 `ReplayRunner`。
- **改完要跑**：`python -m pytest tests/test_models.py tests/test_storage.py tests/test_judge.py tests/test_runner.py tests/test_report.py tests/test_evolve.py -q`，
  再 `python scripts/verify.py`（端到端不变量）。

## 别动

- `storage._safe_name()` / `safe_label()` 的白名单不能放宽：这些名字直接拼进文件路径，
  而入口参数来自 HTTP。有测试断言 `../` 之类会被拒（`tests/test_storage.py`、`tests/test_webapp.py::test_report_id_traversal_rejected`）。
- `runner.run_case()` 里的 `except Exception` 不能改成向上抛：`no_crash` 与「健壮性」类用例
  靠它把崩溃变成可判分的结果，抛出去整轮评测就断了。
- `evolve.py` 的 `MIN_IMPROVEMENT = 0.05` 与 `_max_rounds()` 默认 2 是迭代纪律本体，不是可调参数；
  要放宽请在提交说明里写清理由。
- `report.render_markdown()` 的模板标题（`基线性能(v0)`、`【优化版本】v1`、`【优化内容】`、
  `【优化后性能】`、`最终总结`）是人读归档的固定结构，`verify.py` 检查
  `report_evolution_*.md` 是否存在、看板与文档按这些名字引用它；改标题等于改接口。
- `harness/` 里不要出现 `import llm` 或 `import webapp`：`CompositeJudge` 用 try/except 懒加载
  `llm.judge`，这条边界就是「框架可整体迁移到别的领域」的凭证。
