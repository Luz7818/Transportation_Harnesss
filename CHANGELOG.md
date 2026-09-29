# 更新日志

本文件从 1.6.0 起向前记录(更早版本不追溯补写,历史见 git 提交记录)。
格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/),
版本遵循语义化版本:破坏契约 = 主版本,加能力 = 次版本,修缺陷 = 补丁。

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
