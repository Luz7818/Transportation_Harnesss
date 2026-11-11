# TODO —— 开发计划与当前进度

> 用途：给开发者与 AI。当前在做哪个任务、每个任务按什么标准验收、接下来做什么。
> 完成一项就勾一项并写明下一项；历史性记录写进 [HISTORY.md](HISTORY.md)，这里只留计划。

## 当前进度

- 正在做：无——「v2.3.0 收口批」（数据集溯源贯通 / 摄取 CLI / 对比守卫 / CLI compare / 看板体验批）已完成（2026-11-09，见 HISTORY）
- 下一个：任务 3（2.0 真实数据接入；前置已清——`source`/`captured_at` 溯源字段与 `scripts/import_dataset.py` 摄取通道已就位，换数据源即走该 CLI）或任务 4（建议文案真实复验,仍待端点配额）

## 任务计划

| # | 任务 | 验收标准（可验证） | 状态 |
|---|---|---|---|
| 1 | **线上服务处置（P0，需人决策）**：线上 TCP 8765 自 10-02 起不可达（连败 5 天+）。二选一：① 主动停服——明确「下线」并在 README/Roadmap 注明，撤 `probe.yml` 免得 CI 天天红；② 修复重启——借机改口令并确认 2.0.0 已部署，探针转绿 | ① `probe.yml` 删除 + README 注明；或 ② 探针 workflow 连续 3 天绿 | **完成（走①）**：失联 6 天且无主机访问渠道，2026-10-06 执行下线——probe.yml 已撤、README/Roadmap/AGENTS/GIT/DEPLOY 已注明，复活路径见 HISTORY 当日条目 |
| 2 | 发布：tag + GitHub Release 附 SDK wheel（Roadmap 项，版本一致性断言已进 CI） | `git tag` 出现对应版本 tag；Release 页可见并附 `sdk/dist/` wheel | **完成（2026-11-01）**：v2.2.0 tag + Release 页已发布，附 2.2.0 重出的 wheel/sdist 双附件（2.1.0 旧构建已替换入库）；发布经 GitHub API（本机 git 凭据）完成 |
| 3 | 2.0 真实数据接入：换掉合成快照（公开轨迹集或外业采集），数据集记录 `source`/`captured_at` | 至少一个数据集来自真实源并标注，`verify.py` 全绿 | 待开始 |
| 4 | 建议文案可执行性短板：rc-0015 真实模型判 0.70 恰在阈值（建议模板化、缺具体分流路径） | 改进建议模板后在真实 LLM judge 下 `conclusion_quality` > 0.70，对比记录进 `docs/LLM.md` | **待确认**：文案已数据据点化（升级带/严重度差异化 + 实测值 + 具名分流落点，离线四门禁全绿）；真实复验被端点配额耗尽阻塞（403「token 使用完毕」，2026-11-04 实测），复验命令与判据已留档 `docs/LLM.md` |
| 5 | 2.4 线上化：HTTPS + 备案域名，小程序正式发布（或明确定位为内网演示端） | 域名备案与 HTTPS 就绪，或 README/Roadmap 写明内网演示定位 | 待开始 |

状态取值：待开始 / 进行中 / 待确认 / 完成。

## 完成记录

- [x] v2.3.0 收口批:数据集溯源字段贯通(`list_datasets` 增回 `source`/`captured_at` 经 `/api/datasets` 透出)+ 数据集摄取 CLI `scripts/import_dataset.py`(CSV/JSON 校验原子写,落地「新数据源」扩展点)+ `/api/compare` 跨评测集守卫(400 + 看板下拉按 A 侧评测集过滤)+ `harness-client compare` 子命令(回归退出码 1,「CI 里守回归」落地)+ 看板体验批(`--ease-spring` 弹簧曲线 / 主题切换 VT 圆形揭示 / 缓存穿透)—— 2026-11-09(见 HISTORY)
- [x] 令牌归仓批2:动效时长散值贴梯收权(app.css 79 处+help.html 12 处,行占比 26%→59%,非豁免散值行清零)+ tokens.css 扩静态全 token 单源(字号阶九档 R1/间距九档 R3/tnum R9,tnum 随批消费 14 处)+ 删 --hv-fico-bg 死令牌两处 + SW shell v14/css v=3 缓存穿透 —— 2026-11-12(核查报告批2,见 HISTORY)
- [x] 文档清零批3:TH4-3 文档侧随批核对——deploy-guide.md 部署第 3 步不再承诺「load 后直接 up -d(免网络)」(docker-compose.yml:6 仍钉 2.1.0 未随版本升位,交付 tar 打的是 2.3.0 标签,直接 up 会去 registry 拉不存在的 2.1.0 而部署失败),改为 load 后 `docker tag` 对号 compose 标签(以 `grep image:` 实测为准,升位修复后此步可省)再 `up -d`;升级条目 `up -d --build` 改对号后 `up -d`(用交付镜像,免目标机重建),删「compose 已对号」不实承诺;docs/DEPLOY.md:145 交付包三步走同步;顺带清零 目录说明.md「四个数据卷」漂移(实为 6:评测资产 4 + LLM 层 2);compose 标签升位(2.1.0→2.3.0)属配置/代码侧另批处理 —— 2026-11-12(核查报告批3,见 HISTORY)
- [x] readyz 就绪探针与健康检查分离(核查报告批4·部署件):新增 `/healthz` 存活探针(零依赖,进程在即 200,带 uptime_s,重启判定专用)与 `/readyz` 就绪探针(四类存储目录可列即 200,任一失败 503 带 checks 逐项布尔 + detail 指名;刻意不做资产全量扫描,不与坏文件容错耦合),拨测三件套分工成形(/healthz 存活 / /readyz 就绪 / /api/health 全量诊断);Dockerfile 与 docker-compose healthcheck 改指 /readyz(存储卷不可读即 unhealthy 可见);探针不带 /api/ 前缀,初始口令门禁期间同样可达,OpenAPI public_paths 豁免同步(Swagger 如实标 security: []);端点改动维护矩阵走全:openapi.json 重导 29→31 路径 + API.md/help.html/DEPLOY.md/AGENTS 随动(SDK 刻意不接探针,health() 继续对应 /api/health,对齐 /api/settings 先例);TestProbes 6 例(231→237:liveness 零依赖/就绪 200/缺目录 503+detail/同名文件顶替 503/门禁期可达/schema 免鉴权)—— 2026-11-12(核查报告批4,见 HISTORY)
- [x] TH-04 前端无构建拆分:静态前端 1 文件 3915 行 → 9 文件(index 壳 270 + tokens.css 56 + app.css 1375 + app-core 759/app-board 782/app-manage 677 三经典脚本按 core→board→manage 加载 + help 1025 + sw 117),零构建零依赖不变;浏览器全功能回归 + 计算样式逐项对比零回归,SW 注册断言随架构适配 —— 2026-11-02~04(见 HISTORY 三条)
- [x] v2.2.1 看板韧性收口:auth 行为缺陷修复(改密下限统一 8 位/用户名白名单,周报 TH-05/TH-07)+三栏外壳挤压韧性(顶栏标题竖排折行容器查询修复/侧栏品牌完整显示/AI 面板覆盖化阈值上提 1200)+数字区 tabular-nums 清尾 —— 2026-11-02(见 HISTORY)

- [x] 看板质感/动效/流程收口:按钮内高光与按压反馈、样式化确认弹窗、任务区文本搜索、报告/case 导出、趋势图描线动画、自进化→回放衔接(回放可暂停)、版本卡 sparkline、分析页饱和度微条、对比页 A/B 得分条与差分一键展开、沉淀表单沿用参考判定、健康心跳、流程竞态修复、文档中心质感对齐、后台渲染加固、README 界面截图刷新、v2.2.0 四处同步 —— 2026-10-31(见 HISTORY.md v2.2.0 及当日补充条目)
- [x] 双轨交付：桌面 exe GUI 收口（单实例竞态修复/信息图标）+ 私有化部署交付包（build_deploy.py + 部署说明，该文件后更名 `deploy-guide.md`）+ .dockerignore 修复 + v2.1.0 四处同步/tag/wheel —— 2026-10-07（见 HISTORY.md v2.1.0）
- [x] 遗留清理（batch_demo_ids/空目录/dist 残留）、v2/v3 合并 `_analyze`、文档数字对齐 2.0.0 —— 2026-10-05（核查报告整理轮）
- [x] 文档九件体系迁移 + egg-info 清理 —— 2026-10-05（见 HISTORY.md 对应条目）
