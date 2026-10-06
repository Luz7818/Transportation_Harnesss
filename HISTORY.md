# HISTORY —— 版本更新记录

> 用途：记录 Transportation Harness 的版本演进。只追加，禁止删除或改写既有条目；写错了就追加
> 一条更正。本文件从 v2.0.0 起向前记录（更早版本不追溯补写，历史见 git 提交记录）。
> 格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本遵循语义化版本：
> 破坏契约 = 主版本，加能力 = 次版本，修缺陷 = 补丁。
> 原 `CHANGELOG.md` 的条目于 2026-10-05 逐条无损转入本文件，内容未改写。

## 2026-09-29 · v1.6.0 安全收口

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

## 2026-09-29 · v2.0.0 前向迭代留痕与真实模型判分

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

## 2026-10-05 · 文档规范体系落位（原 [Unreleased] 视觉重造收纳）

- **视觉体系去「AI 模板感」重造:靛蓝/紫/青 → 石墨中性底 + 信号绿单一强调**。
  绿 = 通行/通过/前进,与本产品「评测通过、管线放行」的核心语义一致;红灯/黄灯语义
  (bad/ok/warn 等级徽章)保持不变。落在:
  - 设计令牌整体换装(明暗两套,`index.html`/`help.html` 同步):海军蓝暗底 → 石墨绿暗底,
    蓝灰纸面 → 绿灰纸面;主按钮/链接/激活态 = 信号绿,暗色下主按钮自动切深色文字保对比
  - 资产重绘:`icon.svg` 母版换装后由 `scripts/generate_pwa_icons.py` 重新生成全套
    PNG/lockup/banner(生成器内 banner 配色同步);`hero-bg` 明暗两版重绘
    (石墨绿夜色,一条放行主流线,去紫环光晕);`texture` 明暗重着色
  - 去渐变扫描:KPI 大数字、进化回放分数、进度条、时间线、头像、欢迎页 CTA 的
    渐变全部改纯色;hero 标题强调词由渐变字改为「车道标线」式绿色虚线下划线
  - 布局去模板化:看板 KPI 四张同款圆角卡 → 发丝线分栏的仪表条;欢迎页三张特性玻璃卡 →
    编辑式分栏;卡片标题的彩色图标底座统一中性化(激活态仍用强调色)
  - 文案与形状:hero 徽章改「信号灯三色点 + 评测驱动的迭代闭环」;中圆点装饰串清零;
    圆角收敛为 容器14/控件8/胶囊 一套规则
  - **侧栏 / 任务区可收起**(桌面):任务区收起后由顶栏左缘固定「面板切换钮」恢复,
    状态记忆于 localStorage
  - **动效体系统一**(参照 Emil Kowalski 动效规范):新增 `--ease-out` / `--ease-drawer`
    两条权威曲线令牌;toast 的 `transition: all`(禁令)改为指名属性;侧栏宽度变化加过渡;
    悬停位移统一加触屏门控;图标钮/筛选 chip 按压回弹
  - **侧栏宽度自适应(容器查询)**:内容按列的实际宽度分级降级(≤240px 纵排、≤180px 图标轨),
    拖拽下限同步放到 64px
  - **主题合一**:欢迎页/登录页不再各存一份主题,统一跟随工作台的 `data-theme`
  - **弹层退场动效**:五个弹层统一「与入场对称」的退场(共享 `animateHide` 助手),
    `prefers-reduced-motion` 下退化为直接隐藏;任务区收起/展开由瞬变改为宽度推拉滑动
  - **细节质感层**(纯 CSS/微标注,零依赖,尊重 prefers-reduced-motion):纸面颗粒噪点、
    hero 徽章三色点轮换、滚动进度细线、进化时间线脉冲环等;资产版本参数递增至 `?v=6`
- **Fixed**：页面壳路由与 `/static/*` 补 `Cache-Control: no-cache`（浏览器启发式缓存让换装
  停留旧视觉数小时）；资产引用统一加 `?v=4` 起步的版本参数；hero 背景去掉
  `background-attachment: fixed`（合成 bug）与左下残留绿色光斑；欢迎页布局收缩与对比表
  跨主题泄漏两处修复
- **Changed**：字体栈优先新字体（零外部资源）；图标按钮悬停语义中性化（红色只留删除类）；
  全屏区块追加 `100dvh`；SW 壳缓存 v2 → v3 → v4 → v6
- **文档迁移**：五件套 → 九件体系——新增 `docs/CODE-STYLE.md`、`docs/TESTING.md`、
  `docs/GIT.md`、`HISTORY.md`、`TODO.md`；`docs/getting-started.md` 更名
  `docs/GET-START.md`；原 `docs/ARCHITECTURE.md`（设计决策）与 AGENTS 内的架构数据流/
  鉴权事实/常见任务表合并重写为九件口径的 ARCHITECTURE；`AGENTS.md` 重写为规范入口；
  `CHANGELOG.md` 并入本文件后删除；清理 `transportation_harness.egg-info/` 本机残留。
- 变更缘由：落位《项目整体规范.md》九件必建。

## 2026-10-06 · 文档核查修复（requirements 断链收口 + 数字对齐实测）

- **requirements 断链收口**：README 快速开始改 `pip install -e .`；GET-START 安装/故障表、
  DEPLOY.md Render 构建命令、AGENTS 技术栈复核命令、webapp/app.py 缺依赖报错文案共 7 处
  从 `requirements*.txt` 改为 pyproject 单源口径（文件已于 f834605 删除，文档与报错没跟上）。
- **数字对齐实测**：tests/README 190→210（15 个文件，补 test_packaging_paths 行，
  webapp 39/llm 30/auth 17/versions 19/evolve 7），fixtures 差异口径改为
  「快照不含 rc-0015」（生产库 18 条已反超快照 17 条）；cases/README 16→18、
  目录 10→8、结论缺失/边界处理补 rc-0015/rc-0014；webapp/README 与 ARCHITECTURE 的
  index.html 行数三处统一为 3354（help 940、sw.js 112）；AGENTS 测试 208→210/15 文件。
- **杂项**：scripts/README 的 sys.path.insert 计数改「7 个脚本、2 个为 0」；
  目录说明去掉 requirements 行、dist/ 描述改为「清理后会再生成」；sdk/ 子目录补 `dist/`；
  tests/README 引用 AGENTS 章节名「当前真实状态」→「当前状态」；
  `CHANGELOG.md` 兑现删除（内容已逐条在档，抽查「石墨绿暗底」「口令门禁」等条目命中）。

## 2026-10-06 · 线上服务下线处置（TODO 任务 1 走①）

- **决策**：线上 TCP 8765 自 10-02 起连续失联 6 天（每日 Live Probe 连败,最后一次
  success 停在 09-30),本机 Secrets 无主机 SSH/面板凭据,「修复重启」不可执行;
  按 TODO 任务 1 预案①执行下线。
- **动作**：删除 `.github/workflows/probe.yml`(连带 README 徽章,防 404);
  README 安全模型/Roadmap、AGENTS「当前状态/已知坑」、GIT.md「CI 与线上探针」、
  DEPLOY.md 探针节全部改注下线状态与复活路径。
- **复活路径**：主机恢复后按 DEPLOY.md 重新部署(记得先改初始口令、确认 2.0.0 版本),
  从 `git log --oneline -- "**/probe.yml"` 取恢复点还原探针工作流,重配
  `LIVE_HEALTH_URL` secret;`scripts/probe_live.py` 保留可本地探测。
