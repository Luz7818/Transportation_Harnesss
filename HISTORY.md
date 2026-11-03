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

## 2026-10-07 · exe 封装改独立桌面窗口(GUI 默认 + `--server` 无头)

- **Added**：双击 exe 默认弹 **pywebview/WebView2 独立应用窗口**(无浏览器地址栏,任务栏应用
  图标,新增 `packaging/harness.ico`);服务跑守护线程,关窗即优雅停机(健康就绪后才开窗,
  `should_exit` 最多等 3 秒);**单实例探测**——已在运行时再次双击弹原生提示后退出。
  部署场景用 `TransportationHarness.exe --server` 切无头:与源码 `python webapp/app.py`
  行为一致,从终端启动接管父控制台,双击启动输出落 `exe.log`。
- **Changed**：`webapp/app.py` 的 `main()` 拆出 `_validate_deploy_params()`/`_print_banner()`,
  新增 `make_server()` 工厂(GUI 拿可停机句柄,与无头共用同一道部署参数门禁,补
  `tests/test_make_server.py` 钉住);错误报告按模式分路:GUI 走原生 MessageBox、无头走
  `_error_console` 黑窗;自动开浏览器的旧行为随 GUI 窗口移除。
- **打包**:`harness.spec` 增 pywebview 平台 hiddenimports(winforms/edgechromium)与图标;
  `build_exe.bat` 构建依赖增 `pywebview>=5`;`pyproject.toml` 的 `[exe]` 组同步。

## 2026-10-07 · v2.1.0 双轨交付:桌面 exe 收口 + 私有化部署包

### Added(新增)

- **私有化部署交付包**:`packaging/build_deploy.py` 一键组装
  `dist/TransportationHarness-deploy-<版本>.zip`(源码树 + Dockerfile/compose +
  .env.example + docs/DEPLOY.md + probe/backup 零依赖脚本 + 《部署说明》);打包机装有
  Docker 时含 `docker save` 镜像 tar(目标机 `docker load` 免网络),否则自动降级为
  在线构建包(`docker compose up -d --build`);装包前扫描并清除混入的 `.env`/`auth.json`/日志
- `packaging/部署说明.md` 随包分发:部署三步、验收命令、数据卷/备份/升级路径
- docker-compose.yml 定名镜像 `transportation-harness:2.1.0`:compose build 的产物名
  与离线 `docker load` 对号入座(随版本发布同步升位)

### Fixed(缺陷修复)

- **exe 单实例竞态**:两次快速双击时,后启动者在对方健康就绪前探测不到,端口绑定失败
  弹裸 traceback;现在 `_wait_healthy` 失败路径再探测一次,命中即转「程序已在运行」
  友好提示并退出(桌面窗口冒烟已过)
- 「程序已在运行」提示误用错误图标 → `_messagebox` 增 icon 参数,单实例提示改信息图标
- `.dockerignore` 反排除 `!README.md`:原 `*.md` 把 pip 安装元数据挡在 build context 外,
  当前配置下 `COPY README.md` 必失败(静态核验;本机无 Docker,镜像构建未实测)
- `build_exe.bat` 首建提示文案补 pywebview(实际已装,仅文案)

### Changed(变更)

- 版本四处同步 2.0.0 → 2.1.0(桌面 exe GUI 壳与部署交付包为加能力,按语义化版本升次版本);
  OpenAPI 重导(`info.version` 随动),SDK wheel 重建入 `sdk/dist/`(2.1.0)
- 文档:DEPLOY.md 增「路线 B+ 交付包部署」;packaging/README 改双轨口径并补部署轨文件;
  TODO 任务 2 更新(tag 已打、wheel 已备,Release 页上传待确认);README Roadmap 增 2.5

## 2026-10-07 · 更正:v2.1.0 镜像构建与离线交付已在真机验证

- 上一条 v2.1.0 里「本机无 Docker,镜像构建未实测」的表述已过时:Docker Desktop 4.94
  (引擎 29.8.2)就位后全链路实测通过——`docker build` → 隔离目录 `docker compose up -d`
  → `/api/health` 返回 `app_version 2.1.0` + `default_credentials=false`(容器 healthcheck
  自绿)→ `scripts/probe_live.py` PROBE PASS;
- 离线整包已产出:`dist/TransportationHarness-deploy-2.1.0.zip`(54.3 MB,内含
  `docker save` 的镜像 tar),`docker rmi` → `docker load -i <tar>` 回灌后镜像 ID 一致
  (4f839618cae9),免网络部署路径成立;
- 打包机若遇 Docker Hub 直连超时:先 `docker pull docker.m.daocloud.io/library/python:3.12-slim`
  再 `docker tag` 为 `python:3.12-slim`(或给引擎配 registry-mirrors),构建流程无需改动。

## 2026-10-07 · 部署说明书文件名 ASCII 化

- `packaging/部署说明.md` 更名 `packaging/deploy-guide.md`:《项目整体规范.md》§1.5 规定
  除仓根 `目录说明.md` 外文件名一律英文小写加连字符(中文文件名在 GitHub 变百分号编码链接,
  命令行要转义);交付包内文件与 `build_deploy.py` 复制路径同步更名,说明书内容(中文)不变;
- 引用同步:packaging/README 文件清单与「构建与使用」、docs/DEPLOY「路线 B+」、TODO 完成记录;
  上方 v2.1.0 条目按「HISTORY 只追加、禁改写」保留旧名,以本条为准。

## 2026-10-21 · 更正:LLM judge 懒加载降级可见化

- `harness/judge.py` 的默认 judge 装配里,`except Exception: pass` 会把 llm 层的**一切**
  初始化异常静默吞掉——llm 未安装属预期降级,但 llm 模块自身的真故障(导入路径改动、
  运行时初始化崩溃)也会无声消失,LLM 判分悄悄退化为纯规则分且无任何痕迹。本仓 webapp
  `_autoload_real_llm` 的同类路径是「降级 + 打印原因」,此处对齐(核查轮后端专项检查发现)。
- 修法:捕获后打印 `[harness] LLM judge 懒加载失败,只用规则/启发式 judge:<type>: <msg>`
  (一行),行为不变(仍降级),故障从此可见。
- 验证:ruff 0、`python -m pytest` 212 全过(进度点 212 + 退出码 0,测试数与基线一致)、
  `python scripts/verify.py` PASS。

## 2026-10-31 · v2.2.0 看板质感/动效/流程收口(纯前端,无端点改动)

### Added(新增)

- **任务区文本搜索**:评测看板与 Case 管理的左栏列表各加搜索框(按 ID/标题/标签/版本过滤);
  键入只重绘条目区,输入框不重建,焦点与输入法组合态不丢
- **资产导出**:报告详情(工作区/抽屉共用)加「导出 JSON」;Case 详情加「复制 JSON」
  (剪贴板 API + 非安全上下文 execCommand 回退);命令面板加「导出全部 case JSON」
- **确认弹窗**:三处原生 `confirm()`(删 case/批量删/删草稿)替换为样式化 alertdialog
  (Promise 化 `askConfirm`,Esc/遮罩点击/防悬挂结算),与全局弹层动效一致
- **自进化闭环衔接**:运行完成后给出「回放本次进化 / 与上一版本对比」入口;
  版本卡片加「对比」按钮与迷你得分趋势线(该版本近 8 次评测 sparkline)
- **命令面板新命令**:回放最近一次自进化 / 导出全部 case / 展开收起任务区 / 展开收起侧栏;
  进化回放弹窗支持 Esc 关闭
- **健康心跳**:工作台可见期间每 30s 静默刷新连接状态(quiet 调用不点亮加载条,
  连续两次失败才判「服务离线」,瞬时抖动不容错误报)
- **全局 API 加载条**:顶缘 2.5px 往复滑块,请求在途可见;Toast 加生命周期进度条

### Changed(变更)

- **按钮质感**:主/次/危险键加顶部内高光与按压内阴影(键帽式物理反馈,全走可过渡的
  box-shadow,主题切换不跳变);输入控件 focus 边框由孤立的绿色统一为主色系
- **动效**:趋势图打开时描线入场(stroke-dashoffset)+ 数据点级差浮入;时间线/版本卡片/
  弹层内容级差浮现;闭环步骤与导航图标悬停微交互;顶栏离开顶部后落影
- **流程竞态修复**:快捷对比的 `setTimeout(500)` 与命令面板「运行自进化」的固定延时,
  改为渲染完成后自消费 preset / `whenReady` 轮询就绪(渲染含多次取数,固定延时必竞态)
- **表单校验**:沉淀 replaycase 空标题/空路段时内联报错 + 输入框标红摇晃,不再撞服务端 400
- **修复**:AI 面板展开时「回到顶部」悬浮钮压在面板上,现随面板展开隐藏

### 校验

- ruff 0、`python -m pytest` 退出码 0(前端改动不触测试面)、`verify.py` PASS、
  `check_release.py` PASS(2.2.0 四处同步);浏览器实测:亮/暗主题、搜索、确认弹窗、
  校验摇晃、命令面板、趋势描线均正常,加载与交互全程零 JS 错误

## 2026-10-31 · v2.2.0 补充:文档中心与分析页质感(同版本追加)

- **文档中心 help.html 与看板质感对齐**:顶栏/返回工作台/交互式 API 按钮加内高光与按压
  反馈;接口条目展开描边带主色、概念卡悬停浮起、暗色卡片顶部 hairline;章节滚动浮现
  (IntersectionObserver + 无 JS/减弱动态双兜底,内容永不隐藏);回到顶部改离顶 480px 浮现,
  顶栏离顶落影;主题切换挂 theme-anim 全要素颜色过渡(与看板同一套语言)
- **分析提交结果表加饱和度内联微条**:0~1.2 归一宽度,≥0.8 红、≥0.6 橙、其余主色,
  从 0 滑向目标值;实测与 API 逐值吻合(0.42→35%…1.02→85%),v0 坏基线的饱和度失真
  也被如实可视化
- 校验:两页 JS node --check 通过、CSS 配平;浏览器实测 help(浮现/落影/回到顶部/滚动高亮)
  与分析页(v0/v2 两版数据)零 JS 错误

## 2026-10-31 · v2.2.0 补充:回放控制与差分总览(同版本追加)

- **进化回放可暂停/继续**:新增 ⏸/▶ 控制(暂停清未播定时器并给旁白,继续从下一步以
  1100ms 紧凑节奏续播;减弱动态下整段直出并藏起暂停钮;关闭/重播正确复位)
- **版本对比一键展开全部差分**:结果条右侧新增「展开/收起全部 N 行差分」,免逐行点开
- **Service Worker shell 缓存 v7→v8**:UI 大改后按 sw.js 自身约定 bump,预缓存强制过网
  重建,前端提示「新版本已就绪,刷新生效」
- 校验:JS node --check 通过;浏览器实测暂停冻结/继续续播、差分 4/4 行一键展开,零 JS 错误;
  ruff/pytest/verify/check_release 全过(test_sdk 版本钉子已于上一批同步 2.2.0)

## 2026-10-31 · v2.2.0 补充:效率细节与后台渲染加固(同版本追加)

- **沉淀 case 提效**:路段参考提示内嵌「沿用该判定」按钮,一键把 v2 参考的期望等级与
  饱和度填进表单(实测 S-02 → 拥堵 · 0.91)
- **版本对比 A/B 得分对比条**:结果表上方双横条按版本配色从 0 滑入,直观读出基线与对比通过率
- **后台渲染加固**(浏览器实测发现):后台页签 rAF 不走针,进度条会停在 0 宽、KPI 停在 0——
  animateBars 改为后台直接落地 + 450ms 幂等兜底;runCountUps 同口径直接落终值;
  顺带修复预存无障碍缺陷:减弱动态偏好下 KPI 此前恒显 0,现直接呈现最终数值
- **help 新增「看板效率功能」FAQ**:命令面板/搜索/导出/回放暂停/差分总览/沿用判定一处可查
- 校验:两页 node --check 通过;浏览器实测沿用判定、对比条(含后台页签)零 JS 错误;
  ruff/pytest/verify/check_release 全过

## 2026-10-31 · v2.2.0 补充:底图纵深与首访 delight(同版本追加)

- **工作台环境光**:body::before 三段径向渐变(顶部品牌色晕染 + 底部冷灰收边),亮/暗各配,
  纯静态零动效,位于纹理之上内容之下 —— 平面底图获得纵深
- **欢迎/登录页极光**:两团品牌色光斑 26s/34s 缓慢漂移(首访页 delight 预算,只动 transform,
  hero-light 减淡;径向渐变天然软边,不过滤镜 blur —— 实测大面积 blur 会拖垮光栅致截图超时);
  减弱动态由全局 reduce 规则停用
- **细节微交互**:hero 主按钮 hover 高光扫过(hover 能力查询门控);折叠摘要 hover 染色 +
  箭头微移(开/闭两态各自衔接);空态图标 4.2s 轻浮;轨迹芯片 hover 边框加深一档;
  theme-btn/侧栏/面板钮 :active scale(.9) 按压反馈
- **动效门禁留档**(按 find-animation-opportunities 四问过滤):命令面板/导航等键盘高频面
  不加动画;时间线节点、KPI 等读数区不加装饰动效 —— 全部拒绝并记录
- 校验:CSS 配平 + node --check 通过;亮/暗两主题浏览器实测(工作台环境光、欢迎页极光、
  hover/active 反馈)正常,零 JS 错误

## 2026-10-31 · v2.2.0 补充:状态栏色联动与表格 hover 一致性(同版本追加)

- **meta theme-color 随主题联动**:看板与文档中心切换明暗时同步更新(移动端 PWA 状态栏/
  标题栏颜色跟随,不再恒为暗色);启动时按恢复的主题就位
- **文档中心表格 hover 补齐**:亮色主题此前只有暗色规则有 tbody hover,补齐一致性
- 校验:两页 node --check + CSS 配平通过;ruff/pytest/check_release 全过;
  浏览器实测暗色 meta=#0e111c

## 2026-10-31 · v2.2.0 补充:微打磨收束(同版本追加)

- 欢迎页统计卡 hover 浮起(hover 能力门控);文档中心 TOC 链接过渡、接口条目收起态
  caret hover 微移、回到顶部悬停浮起 —— 均为低成本一致性细节

## 2026-10-31 · v2.2.0 补充:高级感材质升级(同版本追加)

- **带色阴影令牌**:全局阴影从纯灰改为品牌色调(rgba(64,70,140,…) 系),md 档加大扩散
  形成悬浮感;焦点环升级双环(外柔内实)
- **按钮光泽层**:.btn 叠加永久玻璃光泽渐变(::before),基色保持可过渡主题切换不跳变;
  按压时光泽塌陷、内阴影接管(果冻式物理反馈)
- **玻璃化**:顶栏/文档中心顶栏 blur 12→20 加饱和度提升;KPI 从无边框平铺升级为毛玻璃
  浮条;Toast 玻璃底 + 内高光;全部弹层遮罩 blur 提至 8-9px;暗色侧栏顶部品牌色辉光、
  品牌标识描边光环、导航激活态渐变药丸 + 光晕;亮色卡片顶部 1px 受光 hairline
- **欢迎页材质**:统计卡/hero 徽章玻璃强化、CTA 内高光、对比卡半透明底
- **性能实测教训**:920px 宽对比卡的 backdrop-filter 压在持续动画的极光上,每帧重滤波
  会拖垮光栅(截图超时暴露)—— 大面板一律不用 backdrop-filter,半透明底同样透出极光色彩;
  小面积(徽章/统计卡)保留
- 滚动条 hover 染品牌色
- 校验:CSS 配平 + node --check 通过;亮/暗双主题浏览器实测(工作台 KPI 浮条/侧栏辉光/
  欢迎页极光玻璃)正常;ruff/pytest/verify/check_release 全过

## 2026-10-31 · v2.2.0 补充:主数字渐变与弹层受光面(同版本追加)

- KPI 英雄数字(当前最佳版本)单色系渐变文字(indigo→同族浅紫,background-clip,不跨色相)
- 空态图标渐变底 + 内高光;亮色弹层(modal/cmdk/sheet/replay/drawer)统一顶部受光 hairline

## 2026-11-01 · v2.2.0 补充:点击空白涟漪(同版本追加)

- **空白处落点生涟**:pointerdown 委托,两层动效(内柔光扩散 + 外环扩散,.55s/.62s,
  只动 transform+opacity),品牌色低透明度,亮暗各自调参
- **克制边界**(动效门禁):命中按钮/链接/输入件/导航/任务列表/表格/图表/弹层等一切
  交互件与读数区一律静默 —— 那些区域有自己的反馈或不应动摇;同屏上限 6 个防连点刷屏;
  减弱动态不注入
- **生命周期三重保障**:animationend 自毁 + 800ms 超时兜底 + 新点击按时间戳清扫残影
  (后台页签定时器节流时 animationend/超时都可能迟到,实测发现并加固)
- 校验:node --check 通过;浏览器实测生成/定位/前台自毁/清扫全链路,零 JS 错误;
  ruff/pytest/check_release 全过

## 2026-11-01 · v2.2.0 补充:点击效果换皮为轨道环节点(同版本追加)

- 涟漪的「水」隐喻与交通分析场景不贴,换为 **轨道环节点**:中心品牌色节点弹现 +
  两道椭圆轨道环(-16°/12° 倾角,错峰 70ms)扩散淡出,650ms —— 呼应欢迎页的
  轨道视觉母题(交通 = 路网节点,点击即点亮)
- 实现要点:CSS 变量 `--rot` 让同一条 keyframes 驱动两个倾角;排除边界/同屏 6 个上限/
  三重生命周期保障(animationend + 超时兜底 + 时间戳清扫 780ms)全部沿用
- 实现流程步骤说明已归档至用户桌面《点击效果实现流程.md》
- 校验:node --check + CSS 配平 + ripple 残留清零断言;浏览器实测生命周期
  (created=1 → rings=2 → alive=0)与冻结抓拍形态正常;ruff/pytest/check_release 全过

## 2026-11-01 · v2.2.0 Release 收尾:SDK wheel 重出 + GitHub Release 发布(任务 2 闭环)

- **wheel 重出**:`sdk/dist/` 入库的产物还停在 2.1.0 构建(10-07),与 2.2.0 脱节——直接
  附到 Release 会把旧产物挂在 2.2.0 上。`cd sdk && python -m build` 重出
  `transportation_harness_sdk-2.2.0` wheel + sdist 并替换入库;
  `scripts/check_release.py` PASS(版本四处一致 + OpenAPI 29 路径无漂移)
- **GitHub Release 发布**:本机无 gh CLI,经 GitHub API(本机 git 凭据)打 tag `v2.2.0`
  并创建 Release,上传 wheel/sdist 双附件;发布说明自 HISTORY v2.2.0 各条归纳
- TODO 任务 2 关闭,下一个转任务 3/4;目录名三 s 笔误(TH-03)仍单独立项不改

## 2026-11-02 · v2.3.0 前批:auth 行为缺陷修复(周报 TH-05/TH-07)

### Fixed(缺陷修复)

- **改密下限与部署口令统一为 8 位**(TH-05):经界面改密原本可用 6 位口令绕开
  ADMIN_PASSWORD 的 8 位强度要求。三处同步:`webapp/auth.py` `change_password`
  6~64 → 8~64、`webapp/settings.py` 的 ADMIN_PASSWORD 校验 6~64 → 8~64
  (钉住值测试同步)、看板改密弹窗标签「新密码(6~64 位)」→「(8~64 位)」
- **用户名字符白名单**(TH-07,防御性):用户名进入会话令牌载荷(「用户名.过期时间」
  以「.」分隔),创建期以 `^[A-Za-z0-9_-]{1,32}$` 白名单校验 ADMIN_USER,含点号等
  字符在 auth.json 落盘前即 SystemExit 拒绝,载荷格式从源头无歧义

### Tests(测试)

- +2 例:`test_change_password_minimum_is_eight`(7 拒 8 过边界)、
  `test_username_with_dot_rejected_at_creation`(点号拒绝且不落盘 + 合名照常创建),
  212 → 214;ruff/pytest/verify.py/check_release 四门禁全过

## 2026-11-02 · v2.3.0 前批:三栏外壳挤压韧性(周报 TH-04 前端评估衍生缺陷修复)

### Fixed(缺陷修复,浏览器实测驱动)

- **顶栏标题竖排折行**:任务区 + AI 面板同开时(1440px 视口中栏仅 ~445px),页面标题
  「评测看板」「Case 管理」被挤成一字一行。视口媒体查询看不见三栏外壳里顶栏的真实宽度,
  改用容器查询(侧栏同款思路):`.topbar` 声明 `container-type: inline-size`,
  ≤700px 先藏信息胶囊(同信息侧栏脚部仍在)、≤460px 再藏副标题与快捷键徽章;
  标题/副标题加 nowrap + ellipsis 兜底,永不逐字折行
- **侧栏品牌截断**:默认宽度下「Transportation Harness」显示为「Transportation Ha…」。
  内边距 18→14、logo 38→34、间距 11→9、字号 13.5→12.5px,实测 scrollWidth 144px =
  clientWidth 144px 完整显示(省略号兜底保留)
- **AI 面板挤压工作区**:1024~1200px 视口开 AI 面板时,工作区可被挤到 ~54px(实测)。
  AI 面板覆盖式抽屉的触发阈值从 960px 上提至 1200px(规则自 960 块迁出),该区间
  工作区保住可读宽度(实测 1024px 主栏 491px),右缘导轨唤回行为不变

### Changed(变更)

- SW shell 缓存 v8 → v9(按约定触发预缓存重建与刷新提示)
- 校验:1440/1024 双视口 × 明暗主题 × AI 开关 × 任务区开合全组合浏览器实测
  (标题完整、胶囊双向恢复、抽屉覆盖化、品牌不截断、DOM 度量零截断);
  node --check / ruff / pytest(test_pwa+test_webapp)全过

## 2026-11-02 · v2.3.0 前批:数字区 tabular-nums 清尾(周报研究一点名项收口)

- 研究一指出的「数字区补 tabular-nums」经全量清查,主体已在既往批次落地(KPI 大数字、
  表格数字列、报告列表分数/时间戳、轨迹芯片、差分值、对比条、欢迎页统计、AI 面板耗时
  等 12+ 处);本批补齐最后三处漏网:`.tl-head b`(进化时间线时间戳)、
  `.vcard .ver .vn span`(版本卡「13/15 条通过」)、`.kpi .k-foot`(KPI 脚注计数)
- 校验:浏览器 getComputedStyle 三处断言均为 tabular-nums;ruff/pytest 全过

## 2026-11-02 · v2.2.1 发布:看板韧性收口(版本同步)

### Changed(变更)

- 版本号 2.2.0 → 2.2.1(四处同步:根 pyproject / sdk pyproject / sdk `__init__` /
  FastAPI version 参数),`docs/openapi.json` 重导(info.version 随动,29 路径无漂移),
  test_sdk 版本钉子同步;SDK wheel/sdist 重出入库(`sdk/dist/`)
- 本版本为**补丁级**(修缺陷,无新增能力、无契约变化),内容见当日三条前批条目:
  auth 行为缺陷修复(周报 TH-05/TH-07)→ 三栏外壳挤压韧性(顶栏竖排折行/品牌截断/
  AI 面板挤压)→ 数字区 tabular-nums 清尾(周报研究一点名项)
- 体检卡遗留:TH-05(P2)/TH-07(P3)/TH-10(P3,build/dist 过期产物清理)随本版闭环;
  TH-03(仓库改名)维持单独立项;TH-04(单文件拆分)登记为任务 3 前置(见 TODO)

## 2026-11-02 · TH-04 无构建拆分 · 第一批:CSS 层拆分(设计令牌 / 组件样式)

- index.html(3915 行)的 `<style>` 块(1429 行)拆出:`tokens.css`(56 行,:root +
  dark 两张令牌表,设计事实源)与 `app.css`(1375 行,组件/弹层/动效/响应式);
  index.html 内联样式改为两个 `<link>`,零构建零依赖不变,暗色覆盖天然独立成表
- 拆分边界按既有分节注释逐行断言;两文件括号配平自检;SW shell v9 → v10,
  预缓存清单新增两个样式表(?v=1 起步)
- 校验:拆分前后计算样式逐项一致(body 色板/暗色 --bg/--ease-out/主按钮/侧栏渐变/
  顶栏 backdrop-filter);node --check / test_pwa / ruff 全过

## 2026-11-02 · TH-04 无构建拆分 · 第二批:JS 层拆分(三经典脚本,加载顺序显式化)

- 主脚本(2221 行,205 函数,单作用域)按既有 20 个分节注释切为三份经典脚本,零构建不变:
  `app-core.js`(760 行,基础设施:图标/工具/主题/视图分流与登录/健康检查/命令面板/
  点击轨道环/导航/面板拖拽/PWA)、`app-board.js`(782 行,评测主线:看板/版本对比/
  分析提交/进化回放/报告详情与快捷对比/全局快捷键)、`app-manage.js`(676 行,资产与
  辅助:Case 管理/设置/AI 助手右栏);index.html 3915 → 270 行纯 HTML
- 两处接线随拆分显式化:`TASK_RENDERERS`(看板/Case 任务页)与 `renderers`(对比/分析/
  设置)都依赖渲染函数,**必须最后加载**——原单文件里它们排在文件尾部,拆分首版把
  renderers 留在 core 导致加载期 TDZ(浏览器回归抓到:boot 半途而废、轨道环/导航
  监听静默未注册),已移入 app-manage.js;`REDUCED` 从进化回放分节上移至工具区
- SW shell v10 → v11,预缓存新增三个脚本;经典脚本(非 ES 模块)是有意选择:全站
  onclick 内联处理器依赖全局函数,模块化需要全量挂 window,风险大于收益
- 校验:node --check 三文件;浏览器回归 = 五页签渲染/cmdk/AI 面板/报告工作区
  (22 行明细)/主题切换/轨道环节点/导航委托/健康心跳逐项过,加载期注册行为
  全存活;ruff/pytest 全过

## 2026-11-02 · TH-04 无构建拆分 · 第三批:文档同步 + test_pwa 适配

- **test_pwa SW 注册断言随拆分调整**(拆分首版浏览器回归抓到 renderers TDZ 时连带发现):
  `/help` 仍内联注册;`/` 改为断言「index.html 加载 app-core.js 且该文件含
  `serviceWorker.register("/sw.js")`」——意图不变,两页最终都注册同一 SW
- **文档同步**:webapp/README.md(文件清单新增 5 个静态资源与加载顺序、`api()`/PWA 注册/
  渲染入口的文件归属改指新文件、规模核对 `5 11`→`10 11`、sw 缓存版本行改「vN 当前 v11」);
  ARCHITECTURE.md(仓库地图 webapp 行 / §7 前端策略 / 常见任务表);GET-START.md(看板词条)
- **拆分终态**:静态前端 1 文件 3915 行 → 9 文件(index 壳 270 + tokens.css 56 +
  app.css 1375 + app-core 759 + app-board 782 + app-manage 677 + help 1025 + sw 117 +
  manifest 35),零构建零依赖不变;近 12 提交 9 个在动的单文件问题(TH-04)关闭
