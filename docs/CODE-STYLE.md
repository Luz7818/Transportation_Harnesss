# Transportation Harness 代码风格

> 用途：给改本仓代码的人与 AI。静态检查是 ruff（`All checks passed!` 门禁）；
> 分层与安全约定是会咬人的约束，详见 `docs/ARCHITECTURE.md`。

## 代码风格

- Python 3.11+，运行时依赖只有 `fastapi` 与 `uvicorn`（开发另需 pytest/httpx/ruff/Pillow）。
- 分层不许反向依赖：`harness/` 不 import `pipeline/`、`llm/`、`webapp/`；被测管线靠
  `PIPELINES` 注册表注入，判分器靠 `BaseJudge` 子类注入。
- 会话签发只在 `webapp/auth.py`，凭据裁决只在 `webapp/app.py` 中间件，检查类型路由只在
  `CompositeJudge._route`——不要新增第二个会话格式或第二套判分入口。

## 命名与结构约定

- 产物文件名带版本前缀：`report_<version>_<timestamp>.json`——前缀是 `list_reports()`/
  `verify.py`/看板对比认得的唯一筛选条件，去掉会让归档混在一起。
- 产物里除时间戳外不带可变值；`storage.save_report()` 的 timestamp 去掉 `-` 与 `:`。
- case 按失败标签分目录（`safe_label()` 用作目录名，空标签兜底「未分类」）。
- `llm/` 新工作流：强制 JSON Schema + 必须有降级路径（`docs/LLM.md`）。

## 错误处理与安全

- 写盘都是「临时文件 + `os.replace`」，复合操作在进程锁内（`_CASE_LOCK`/`_EVOLVE_LOCK`/
  `storage._LOCK`/`settings_mod._WRITE_LOCK`）；多进程部署锁不跨进程。
- 路径与标签一律过 `_safe_name()`/`safe_label()` 白名单——新增「按名字拼路径」的接口必须
  复用它们，否则等于开 `../` 穿越口（有测试断言）。
- 删除 case 必须同步评测集清单（同一把锁内）；`load_evalset_cases()` 对悬空引用直接抛错。
- 未处理异常只回显通用提示，细节进服务端日志；对外输出不回显令牌/口令/内网地址。
- 迭代纪律不许放宽：`MIN_IMPROVEMENT`(5%)、`EVOLVE_MAX_ROUNDS`(2)、回归一票否决——
  这三条是这个仓库存在的理由。
