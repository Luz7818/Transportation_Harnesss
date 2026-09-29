# 更新日志

本文件从 1.6.0 起向前记录(更早版本不追溯补写,历史见 git 提交记录)。
格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/),
版本遵循语义化版本:破坏契约 = 主版本,加能力 = 次版本,修缺陷 = 补丁。

## [2.0.0] - 2026-09-29

### Added(新增)

- **管线 v3「排队回溢升级带」**:V/C ∈ [0.70,0.8) 且速度比 < 0.50 时升级为「拥堵」
  (v2 仅覆盖 [0.75,0.8) × <0.35,是 v3 的子集,对既有场景只扩不缩);
  由 rc-0014/rc-0015(晚高峰排队回溢外业复核)驱动的前向迭代:
  同一评测集 v2 13/15 → v3 15/15,零回归
- **新沉淀用例**:rc-0014(边界处理,经看板 API 沉淀)、rc-0015(结论缺失,首次引入
  `conclusion_quality` 检查),evalset_v1 扩至 15 条
- **真实模型判分(2.3)**:qwen3.8-27b 对 rc-0015 判 0.70(恰在阈值,理由:建议模板化、
  可执行性偏弱),Mock 判 1.0 —— 差异与解读归档在 `docs/LLM.md` 与两份 v3 报告
- **LLM Runtime 韧性**:`LLM_EXTRA_BODY` 支持 `{"response_format": null}` 关闭 JSON
  引导解码(SEU vLLM 端点会与模型输出叠加产生畸形 JSON);`_parse_json_content`
  剥 `<think>` 思考块、容忍围栏,并从带噪声文本提取首个平衡 JSON 对象

### Changed(变更)

- `scripts/verify.py` 判据链扩展到全部已登记版本:得分/通过集单调性随版本前进,
  种子不变量改查最新版本,[5] 增补「v3 与 v2 在 base 判定一致 + evening_peak 升级行为」
- 版本号 1.6.0 → 2.0.0,SDK 构建产物同步重建(`sdk/dist/`)
- 文档:README 战绩表/Roadmap/已知局限随 v3 更新;手册 4.2 增前向迭代真实输出

## [1.6.0] - 2026-09-29

### Security(安全收口)

- **账密改为部署者自备**:启动环境提供 `ADMIN_PASSWORD` 即视为已设置
  (`default_credentials=false`);未提供时随机生成只打印一次,并进入门禁状态
- **初始口令门禁**:`default_credentials=true` 期间,除 `/api/health` 与 `/api/auth/*` 外,
  全部业务接口对三种凭据(X-API-Token / Bearer / Cookie)一律 403,
  「部署后忘了改口令」不再可能静默存活;看板登录后自动弹出改密引导
- **存量部署轮换通道**:已存在 `auth.json` 且默认口令未改时,重启提供
  `ADMIN_PASSWORD` 即自动轮换并翻转标记;界面改过口令的部署不受环境变量影响
- 机器令牌 `AUTH_TOKEN` 短于 16 字符时拒绝启动;启动横幅提示未设令牌/口令未改状态
- 未处理异常不再把类型与消息回显给客户端(只进服务端日志)

### Fixed(缺陷修复)

- `python -m harness.evolve --baseline v2`(基线传最末登记版本)由 `IndexError` 改为
  明确报错;API 侧同参数返回 400 并说明原因,补用例钉住
- `tests/test_sdk.py` 单独运行失败:`server_url` 夹具现在把 `AUTH_FILE` 与模块级
  `_AUTH_STORE` 隔离到临时文件,与 `make_client` 同源(测试隔离缺陷,非产品缺陷)
- `harness/report.py` 报告渲染对「只有基线、无迭代版本」的输入不再越界

### Added(新增)

- `scripts/check_release.py` + CI 步骤:版本号四处同步断言与 OpenAPI 无漂移断言进 CI
- `scripts/probe_live.py` + `Live Probe` workflow:每天只读探针守护线上
  「服务在线 + 初始口令已改」(服务地址存仓库 secret `LIVE_HEALTH_URL`,不入库)
- OpenAPI 声明三种安全方案(`X-API-Token` / Bearer / Cookie),Swagger UI 出现锁标;
  导出脚本移除失效的环境变量占位 hack
- README 重排为项目主页样式;新增本更新日志

### Changed(变更)

- 版本号 1.5.0 → 1.6.0,SDK 构建产物同步重建(`sdk/dist/`)
- 文档:DEPLOY.md 重写「凭据与首次启动」、写明单实例部署边界;
  miniprogram/README.md 落记四类点击区实测尺寸
