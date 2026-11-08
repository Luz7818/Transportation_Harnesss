/* Transportation Harness · 看板应用脚本(board · 评测主线)
   无构建拆分(TH-04 第二批):经典脚本共享全局作用域,加载顺序 app-core -> app-board -> app-manage。
   本文件职责:评测看板/版本对比/分析提交/进化回放/报告详情与快捷对比渲染/全局快捷键 */
"use strict";
/* ============ 评测看板 ============ */
let evalsetOptions = [];
let currentEvalset = "evalset_v1";
let currentBaseline = "v0";
let dashMode = "overview";       // overview = 总览工作区,report = 选中报告详情
let selectedReportId = null;
let dashReportFilter = "全部";
let reportSeq = 0;               // 详情请求序号:防快速连点导致乱序覆盖

const verBadge = v => `b${parseInt(String(v).replace(/\D/g, ""), 10) % 4 || 0}`;

/* 版本卡片迷你趋势线:该版本历次评测得分轨迹(≥2 次才画,单点无线可言) */
function sparkline(hist) {
  if (!hist || hist.length < 2) return "";
  const W = 200, H = 30, pad = 3.5;
  const accs = hist.map(r => r.accuracy);
  const lo = Math.max(0, Math.min(...accs) - 0.06), hi = Math.min(1, Math.max(...accs) + 0.06);
  const rng = hi - lo || 1;
  const px = i => pad + i * (W - pad * 2) / (hist.length - 1);
  const py = a => H - pad - (a - lo) / rng * (H - pad * 2);
  const pts = hist.map((r, i) => `${px(i).toFixed(1)},${py(r.accuracy).toFixed(1)}`).join(" ");
  const color = VER_COLOR[hist[0].version] || "#4f46e5";
  return `<div class="spark" title="该版本最近 ${hist.length} 次评测得分轨迹">
    <svg viewBox="0 0 ${W} ${H}" aria-hidden="true">
      <polyline class="sp-line" points="${pts}" stroke="${color}" opacity=".85"/>
      ${hist.map((r, i) => `<circle class="sp-dot" cx="${px(i).toFixed(1)}" cy="${py(r.accuracy).toFixed(1)}" r="2.2" fill="${color}"/>`).join("")}
    </svg></div>`;
}

async function renderDashboard() {
  closeSheet();  // 看板重渲染(如评测完成)时,避免弹层内容与数据脱节
  $("#tab-dashboard").innerHTML =
    `<div class="skeleton" style="height:96px"></div><div class="skeleton" style="height:190px"></div>
     <div class="skeleton" style="height:220px"></div><div class="skeleton" style="height:130px"></div>`;
  let versions, reports, evolutions, health, evalsets, activity;
  try {
    [versions, reports, evolutions, health, evalsets, activity] = await Promise.all([
      api("/api/versions"), api("/api/reports"), api("/api/evolutions"), api("/api/health"),
      api("/api/evalsets"), api("/api/activity?limit=10")]);
  } catch (e) {
    $("#tab-dashboard").innerHTML = `<div class="card">${emptyBox("alert", "加载失败", esc(e.message))}</div>`;
    return;
  }
  evalsetOptions = evalsets;
  if (!evalsets.some(e => e.evalset_id === currentEvalset)) currentEvalset = evalsets[0]?.evalset_id || "evalset_v1";
  window.__dashData = { versions, reports, evolutions, health, activity };
  renderDashTaskPanel(reports);
  renderDashWorkspace();
}

/* ---- 任务区:评测报告列表(按版本筛选 + 文本搜索),点选进工作区详情 ---- */
let dashSearch = "";
function renderDashTaskPanel(reports) {
  const filters = ["全部", ...new Set(reports.map(r => r.version))];
  if (!filters.includes(dashReportFilter)) dashReportFilter = "全部";
  $("#tp-head-slot").innerHTML = `
    <div class="tp-head"><b>${icon("layers", 14)} 评测报告</b>
      <span class="chip2 plain num">${reports.length}</span>
      ${dashMode === "report" ? `<button class="btn sm secondary" onclick="dashOverview()">${icon("dashboard", 13)} 总览</button>` : ""}
      <button class="icon-btn" style="width:24px;height:24px;flex:none" onclick="setTaskCollapsed(true)" title="收起任务区" aria-label="收起任务区">‹</button></div>`;
  $("#tp-list").innerHTML = `
    <div class="tp-tools"><div class="chips">${filters.map(f =>
      `<span class="chip2 ${f === dashReportFilter ? "" : "plain"} click" onclick="setDashFilter('${esc(f)}')">${esc(f)}</span>`).join("")}</div></div>
    <div class="tp-search"><input id="dash-search" value="${esc(dashSearch)}" autocomplete="off"
      placeholder="搜索报告 ID / 版本…" oninput="setDashSearch(this.value)"></div>
    <div id="tp-items"></div>`;
  renderDashReportItems(reports);
  $("#tp-foot").style.display = "";
  $("#tp-foot").textContent = "报告按版本 × 评测时间归档;点选任意报告,在工作区查看分标签通过率与逐 case 明细。";
}
/* 搜索键入只重绘条目区,不重建输入框:焦点与输入法组合态不丢 */
function renderDashReportItems(reports) {
  const box = $("#tp-items");
  if (!box) return;
  const kw = dashSearch.trim().toLowerCase();
  const shown = reports.filter(r => (dashReportFilter === "全部" || r.version === dashReportFilter)
    && (!kw || r.report_id.toLowerCase().includes(kw) || r.version.toLowerCase().includes(kw)));
  box.innerHTML = shown.length ? shown.map(r => `
      <div class="tp-item ${selectedReportId === r.report_id ? "sel" : ""}" onclick="selectReport('${esc(r.report_id)}')">
        <div class="ti-top"><span class="ver-badge ${verBadge(r.version)}" style="font-size:10.5px;padding:1.5px 7px">${esc(r.version)}</span>
          <span class="ti-title num" title="${esc(r.report_id)}">${esc(r.report_id)}</span></div>
        <div class="ti-meta"><span class="num" style="font-weight:700;color:${r.accuracy === 1 ? "var(--ok)" : "var(--t1)"}">${pct(r.accuracy)}</span>
          <span class="num">${r.passed_count}/${r.total}</span><span style="opacity:.5">·</span><span class="num">${esc(fmtTs(r.timestamp))}</span></div>
      </div>`).join("")
    : `<div class="tp-empty">${kw ? `没有匹配「${esc(dashSearch.trim())}」的报告` : "该版本暂无报告<br>在总览页运行评测即可生成"}</div>`;
}
function setDashSearch(v) { dashSearch = v; renderDashReportItems((window.__dashData || {}).reports || []); }
function setDashFilter(f) { dashReportFilter = f; renderDashTaskPanel((window.__dashData || {}).reports || []); }
async function selectReport(id) {
  dashMode = "report"; selectedReportId = id;
  if (!window.__dashData) {
    try { window.__dashData = { reports: await api("/api/reports") }; }
    catch (e) { toast(e.message, true); return; }
  }
  renderDashTaskPanel(window.__dashData.reports);
  renderDashWorkspace();
}
function dashOverview() {
  dashMode = "overview"; selectedReportId = null;
  const reports = (window.__dashData || {}).reports;
  if (reports) renderDashTaskPanel(reports);
  renderDashWorkspace();
}

/* ---- 工作区分发:总览 / 报告详情 ---- */
function renderDashWorkspace() {
  const d = window.__dashData;
  if (!d) return;
  if (dashMode === "report" && selectedReportId) { renderReportWorkspace(selectedReportId); return; }
  renderDashOverview(d);
}

async function renderReportWorkspace(reportId) {
  const seq = ++reportSeq;
  $("#tab-dashboard").innerHTML =
    `<div class="skeleton" style="height:130px"></div><div class="skeleton" style="height:260px"></div>`;
  let rep;
  try { rep = await api("/api/reports/" + encodeURIComponent(reportId)); }
  catch (e) { if (seq === reportSeq) { toast(e.message, true); dashOverview(); } return; }
  if (seq !== reportSeq) return;   // 已切换到别的报告/视图,丢弃本次结果
  $("#tab-dashboard").innerHTML = `
    <div class="card">
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
        <button class="btn sm secondary" onclick="dashOverview()">${icon("dashboard", 13)} 返回总览</button>
        <b style="flex:1;min-width:0;font-size:15px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(rep.report_id)}</b>
      </div>
      <p class="desc" style="margin-top:6px">评测集 ${esc(rep.evalset_id || "—")} · 归档于 ${esc(fmtTs(rep.timestamp || ""))}</p>
      ${reportDetailHtml(rep)}
    </div>`;
}

function renderDashOverview(d) {
  const { versions, reports, evolutions, health, activity } = d;
  const evalsetSelect = `<select id="evalset-pick" style="width:100%" onchange="onEvalsetChange()">
    ${evalsetOptions.map(e => `<option value="${esc(e.evalset_id)}" ${e.evalset_id === currentEvalset ? "selected" : ""}>${esc(e.evalset_id)} · ${e.case_count} 条</option>`).join("")}
  </select>`;
  const baselineSelect = `<select id="baseline-pick" style="width:100%" onchange="onBaselineChange()">
    ${versions.map(v => `<option value="${esc(v.version)}" ${v.version === currentBaseline ? "selected" : ""}>${esc(v.version)} · ${esc(v.name)}</option>`).join("")}
  </select>`;

  /* --- KPI --- */
  const lastEvo = evolutions[0] || null;
  const kpis = `
    <div class="kpis">
      <div class="kpi"><div class="k-top"><span class="k-label">当前最佳版本</span><span class="k-ico">${icon("target", 16)}</span></div>
        <div class="k-value grad">${lastEvo ? `${esc(lastEvo.best.version)} <small>${pct(lastEvo.best.accuracy)}</small>` : "—"}</div>
        <div class="k-foot">${lastEvo ? `最近 ${lastEvo.best.passed_count}/${lastEvo.best.total} 通过` : "尚未运行自进化"}</div></div>
      <div class="kpi"><div class="k-top"><span class="k-label">评测集规模</span><span class="k-ico">${icon("database", 16)}</span></div>
        <div class="k-value num" data-countup="${health.case_count}">0</div>
        <div class="k-foot">${lastEvo ? `覆盖 ${lastEvo.total_cases} 条` : "在 Case 管理页沉淀"}</div></div>
      <div class="kpi"><div class="k-top"><span class="k-label">自进化运行</span><span class="k-ico">${icon("cycle", 16)}</span></div>
        <div class="k-value num" data-countup="${evolutions.length}">0</div>
        <div class="k-foot">${lastEvo ? stopTag(lastEvo.stop_reason) : "闭环流程见下方"}</div></div>
      <div class="kpi"><div class="k-top"><span class="k-label">评测报告</span><span class="k-ico">${icon("filetext", 16)}</span></div>
        <div class="k-value num" data-countup="${reports.length}">0</div>
        <div class="k-foot">点左侧列表看明细</div></div>
    </div>`;

  /* --- 自进化闭环图 --- */
  const steps = [
    ["inbox", "收集反馈", "线上点踩 / 人工抽检", "cases"],
    ["database", "沉淀用例", "输入 + 期望 + 判分规则", "cases"],
    ["flask", "运行评测", "重放全部 case 并判分", ""],
    ["gauge", "定位失败", "按标签聚类失败原因", ""],
    ["tool", "迭代管线", "每轮只改一类,最多 2 轮", ""],
    ["shield", "回归验证", "提升且无回归才合入", ""],
  ];
  const loop = `
    <div class="card">
      <h3><span class="h-ico">${icon("cycle", 16)}</span>自进化运行闭环</h3>
      <p class="desc">新 badcase 持续回流 → 评测集增长 → 管线一次次被推向更高得分。</p>
      <div class="loop">${steps.map(([ico, t, sub, tab], i) =>
        `<div class="step ${tab ? "click" : ""}" ${tab ? `onclick="switchTab('${tab}')"` : ""}>
           <div class="s-ico">${icon(ico, 19)}</div>
           <div class="s-title">${t}</div><div class="s-sub">${sub}</div></div>`
      ).join(`<div class="s-arrow">${icon("chevR", 16)}</div>`)}</div>
      <div class="loopback"><div class="lb-head"></div>
        <div class="lb-label">${icon("cycle", 13)}新 badcase 回流 → 评测集增长 → 下一轮进化</div><div class="lb-dot"></div></div>
    </div>`;

  /* --- 进化时间线 --- */
  const timeline = `
    <div class="card">
      <h3><span class="h-ico">${icon("activity", 16)}</span>进化时间线</h3>
      <p class="desc">得分逐轮爬升,每轮验证「提升且无回归」,达标即收束。</p>
      ${evolutions.length ? `<div class="tl">${evolutions.map(e => {
        const chips = [`<span class="traj-chip"><span class="tv">${esc(e.baseline.version)}</span><b>${pct(e.baseline.accuracy)}</b></span>`];
        let prevAcc = e.baseline.accuracy;
        for (const r of e.rounds) {
          chips.push(`<span class="traj-arrow">${icon("arrowR", 13)}</span>`);
          chips.push(`<span class="traj-chip ${r.version === e.best.version ? "best" : ""}"><span class="tv">${esc(r.version)}</span><b>${pct(r.accuracy)}</b>${deltaTag(r.accuracy - prevAcc)}</span>`);
          prevAcc = r.accuracy;
        }
        return `<div class="tl-item">
          <div class="tl-head"><b>${esc(fmtTs(e.timestamp))}</b>
            <span class="tag">${esc(e.evalset_id)} · ${e.total_cases} 条</span>
            ${stopTag(e.stop_reason)}
            <button class="btn sm secondary" style="margin-left:auto" onclick="replayEvolution('${esc(e.evolution_id)}')">${icon("play", 12)} 回放</button></div>
          <div class="tl-traj">${chips.join("")}</div>
          ${e.rounds.map(r => `<details class="changes"><summary>第 ${r.round} 轮「${esc(r.version_name)}」:新通过 ${r.newly_passed.length},回归 ${r.regressed.length}</summary>
            <ul>${r.changes.map(c => `<li>${esc(c)}</li>`).join("")}</ul>
            <button class="btn sm secondary" style="margin-top:8px" onclick="quickCompareVersion('${esc(r.version)}')">${icon("scale", 13)} 与上一版本对比</button></details>`).join("")}
        </div>`;
      }).join("")}</div>`
        : emptyBox("activity", "还没有进化记录", "在右侧「评测与自进化」运行完整循环")}
    </div>`;

  /* --- 版本卡片 --- */
  /* 版本卡片钉在卡片底部:双栏等高拉伸时填充视觉,不留空洞 */
  const latest = {};
  for (const r of reports) if (!latest[r.version]) latest[r.version] = r;
  const cards = `<div class="grid" style="margin-top:auto;padding-top:14px">${versions.map(v => {
    const rep = latest[v.version], acc = rep ? rep.accuracy : null;
    return `<div class="vcard">
      <div class="ver">
        <span class="ver-badge ${verBadge(v.version)}">${esc(v.version)}</span>
        <div class="vn"><b>${esc(v.name)}</b><span>${rep ? `${rep.passed_count}/${rep.total} 条通过` : "点击下方按钮首次评测"}</span></div>
        <div class="score ${rep ? "" : "dim"}">${rep ? pct(acc) : "未评测"}</div>
      </div>
      <div class="bar"><div style="width:0%" data-w="${acc !== null ? (acc * 100).toFixed(1) : 0}"></div></div>
      ${sparkline(reports.filter(r => r.version === v.version).slice(0, 8).reverse())}
      ${v.changes.length ? `<details class="changes"><summary>本轮优化内容(${v.changes.length})</summary>
        <ul>${v.changes.map(c => `<li>${esc(c)}</li>`).join("")}</ul></details>` : ""}
      <div class="act">
        ${rep ? `<button class="btn sm secondary" onclick="quickCompareVersion('${esc(v.version)}')" title="与上一版本逐 case 差分">${icon("scale", 13)} 对比</button>` : ""}
        <button class="btn sm secondary" onclick="runEval(this,'${esc(v.version)}')">${icon("play", 13)} 运行评测</button>
      </div>
    </div>`;
  }).join("")}</div>`;

  const evalCard = `
    <div class="card" style="padding-bottom:16px">
      <h3><span class="h-ico">${icon("play", 16)}</span>评测与自进化</h3>
      <p class="desc">单版本可快速重跑;完整循环按「逐版本验证 + 收益递减」自动收束。</p>
      <label style="margin-top:0">评测范围</label>
      ${evalsetSelect}
      <label>基线版本(增量验证新版本时选当前最佳)</label>
      ${baselineSelect}
      <p style="margin:14px 0 0"><button class="btn" style="width:100%" onclick="runEvolve(this)">${icon("cycle", 16)} 运行完整自进化循环</button></p>
      <div id="evolve-out"></div>
      ${cards}
    </div>`;

  /* --- 入口磁贴:得分趋势 / 最近动态(点击弹层查看) --- */
  const latestRep = reports[0] || null;
  const trendSub = reports.length >= 2
    ? `${reports.length} 份报告 · 最新 ${esc(latestRep.version)} ${pct(latestRep.accuracy)}`
    : "报告不足两份,先运行评测生成趋势";
  const actSub = activity.length ? `最新:${esc(activity[0].title)}` : "暂无动态";
  const entries = `
    <div class="entry-row">
      <button class="entry-card" onclick="openSheet('trend')">
        <span class="e-ico">${icon("trend", 18)}</span>
        <span class="e-body"><b>评测得分趋势</b><small>${trendSub}</small></span>
        <span class="e-arrow">${icon("chevR", 16)}</span>
      </button>
      <button class="entry-card" onclick="openSheet('act')">
        <span class="e-ico">${icon("activity", 18)}</span>
        <span class="e-body"><b>最近动态</b><small>${actSub}</small></span>
        <span class="e-arrow">${icon("chevR", 16)}</span>
      </button>
    </div>`;
  $("#tab-dashboard").innerHTML = `
    ${kpis}
    ${entries}
    ${loop}
    <div class="dash-grid">
      <div class="dash-col">${timeline}</div>
      <div class="dash-col">${evalCard}</div>
    </div>`;
  runCountUps($("#tab-dashboard"));
  animateBars($("#tab-dashboard"));
}

/* ---- 看板弹层:得分趋势 / 最近动态 ---- */
const KIND_ICON = { case: "database", eval: "flask", evolve: "cycle", draft: "spark" };
function activityFeedHtml(activity) {
  return `<div class="act-feed">${activity.map(a => `
    <div class="act-item">
      <span class="act-ico k-${esc(a.kind)}">${icon(KIND_ICON[a.kind] || "activity", 14)}</span>
      <div class="act-body">
        <div class="act-t">${esc(a.title)}${a.tag ? ` <span class="chip2 plain" style="padding:1px 9px;font-size:11px">${esc(a.tag)}</span>` : ""}</div>
        <div class="act-d">${esc(a.detail)}</div>
      </div>
      <span class="act-time num">${esc(fmtTs(a.ts))}</span>
    </div>`).join("") || `<div class="muted">暂无动态</div>`}</div>`;
}
function openSheet(kind) {
  const d = window.__dashData || {};
  if (kind === "trend") {
    const reports = d.reports || [];
    $("#sheet-ico-slot").innerHTML = icon("trend", 16);
    $("#sheet-title").textContent = "评测得分趋势";
    $("#sheet-body").innerHTML = reports.length >= 2
      ? `<p class="desc" style="margin:0 0 10px">连线即管线成长曲线:迭代后应单调上升,回落即为回归信号。</p>${areaChart(reports)}`
      : emptyBox("trend", "报告不足两份,暂无趋势", "先在「评测与自进化」运行评测");
  } else {
    $("#sheet-ico-slot").innerHTML = icon("activity", 16);
    $("#sheet-title").textContent = "最近动态";
    $("#sheet-body").innerHTML = `<p class="desc" style="margin:0 0 10px">沉淀、评测、自进化与 LLM 草稿的统一时间流。</p>${activityFeedHtml(d.activity || [])}`;
  }
  $("#sheet-mask").classList.remove("hidden");
}
function closeSheet() { animateHide($("#sheet-mask")); }
$("#sheet-mask").addEventListener("click", e => { if (e.target === $("#sheet-mask")) closeSheet(); });

function onEvalsetChange() { currentEvalset = $("#evalset-pick").value; }
function onBaselineChange() { currentBaseline = $("#baseline-pick").value; }

/* 图表几何常量(构建与悬停计算共用) */
const CHART = { W: 780, H: 230, L: 46, R: 18, T: 16, B: 32 };
let chartData = [];   // 当前看板趋势图的数据(单图表假设)

function areaChart(reports) {
  const data = [...reports].reverse();  // 旧 → 新
  chartData = data;
  const { W, H, L, R, T, B } = CHART;
  const iw = W - L - R, ih = H - T - B;
  const px = i => L + (data.length === 1 ? iw / 2 : i * iw / (data.length - 1));
  const py = a => T + (1 - a) * ih;
  const gridY = [0, .25, .5, .75, 1].map(a =>
    `<line x1="${L}" y1="${py(a)}" x2="${W - R}" y2="${py(a)}" stroke="var(--chart-grid)" stroke-width="1"/>
     <text x="${L - 8}" y="${py(a) + 4}" font-size="10.5" fill="var(--t4)" text-anchor="end">${a * 100}%</text>`).join("");
  const pts = data.map((r, i) => `${px(i).toFixed(1)},${py(r.accuracy).toFixed(1)}`);
  const line = pts.join(" ");
  const area = `M ${px(0).toFixed(1)},${py(0)} L ${line.replace(/ /g, " L ")} L ${px(data.length - 1).toFixed(1)},${py(0)} Z`;
  const dots = data.map((r, i) => {
    const last = i === data.length - 1;
    return `<circle class="cg-dot" data-i="${i}" cx="${px(i).toFixed(1)}" cy="${py(r.accuracy).toFixed(1)}" r="${last ? 5.5 : 4.5}"
      fill="${VER_COLOR[r.version] || "#4f46e5"}" stroke="var(--surface)" stroke-width="${last ? 2.5 : 1.5}"
      style="animation-delay:${(0.1 + i * 0.09).toFixed(2)}s"/>`;
  }).join("");
  const labels = data.map((r, i) =>
    `<text x="${px(i)}" y="${H - 10}" font-size="10.5" fill="var(--t4)" text-anchor="middle">${esc(r.version)}</text>`).join("");
  return `<div class="chart-wrap">
    <svg class="chart-svg" viewBox="0 0 ${W} ${H}">
      <defs><linearGradient id="area-g" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#4f46e5" stop-opacity=".2"/><stop offset="1" stop-color="#4f46e5" stop-opacity="0"/>
      </linearGradient></defs>
      ${gridY}
      <path d="${area}" fill="url(#area-g)" style="animation:fadeIn .8s ease .2s both"/>
      <polyline class="trend-line" points="${line}" fill="none" stroke="var(--primary)" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>
      <line class="cg-guide" x1="0" x2="0" y1="${T}" y2="${H - B}" stroke="var(--t4)" stroke-dasharray="3 3" style="opacity:0"/>
      ${dots}${labels}</svg>
    <div class="chart-tip" aria-hidden="true"></div>
    <div class="chart-note">横轴为时间(旧 → 新),纵轴为评测通过率;悬停查看每份报告详情。</div>
  </div>`;
}

/* 图表悬停:参考线 + 浮动提示(事件委托,图表重渲染无需重绑) */
document.addEventListener("mousemove", (e) => {
  const wrap = e.target && e.target.closest ? e.target.closest(".chart-wrap") : null;
  const tip = document.querySelector(".chart-tip.show");
  const guide = document.querySelector(".cg-guide");
  if (!wrap || !chartData.length) {
    if (tip) tip.classList.remove("show");
    if (guide) guide.style.opacity = 0;
    return;
  }
  const svg = wrap.querySelector("svg");
  const rect = svg.getBoundingClientRect();
  const fx = Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 1);
  const n = chartData.length;
  const i = Math.round(fx * (n - 1));
  const r = chartData[i];
  const { W, L, R, T, B } = CHART;
  const vx = L + (n === 1 ? (W - L - R) / 2 : i * (W - L - R) / (n - 1));
  const cssX = vx / W * rect.width;
  guide.setAttribute("x1", vx); guide.setAttribute("x2", vx);
  guide.style.opacity = .8;
  const tipEl = wrap.querySelector(".chart-tip");
  tipEl.innerHTML = `<b>${esc(r.version)}</b> <span class="num">${pct(r.accuracy)}</span>
    <em>${esc(r.report_id)}</em><em>${esc(fmtTs(r.timestamp))} · ${r.passed_count}/${r.total} 通过</em>`;
  tipEl.classList.add("show");
  const wrapRect = wrap.getBoundingClientRect();
  const left = Math.min(Math.max(cssX + 12, 4), wrapRect.width - 230);
  tipEl.style.left = left + "px";
  tipEl.style.top = Math.max((e.clientY - wrapRect.top) - 30, 4) + "px";
});

/* 闭环「车流虚线 + 光点巡航」开关:贴 withBusy 生命周期 —— 发起挂 .running,resolve 摘除刹停
   (withBusy 吞错不抛,await 后必达,成功失败同路);纯类切换,动画全在 CSS,不加轮询 */
function loopRunning(on) {
  $$(".loopback").forEach(el => el.classList.toggle("running", on));
}

async function runEval(btn, version) {
  loopRunning(true);
  await withBusy(btn, async () => {
    const rep = await api("/api/eval/run", { version, evalset: currentEvalset });
    toast(`${version} 在 ${currentEvalset} 上评测完成:${rep.passed_count}/${rep.total}(${pct(rep.accuracy)})`);
    await renderDashboard();
  });
  loopRunning(false);
}

async function runEvolve(btn) {
  loopRunning(true);
  await withBusy(btn, async () => {
    const s = await api("/api/evolve/run", { evalset: currentEvalset, baseline: currentBaseline });
    const b = s.baseline;
    const rounds = s.rounds.map(r => `
      <div class="round">
        <div class="head"><b>第 ${r.round} 轮 · ${esc(r.version)}(${esc(r.version_name)})</b>
          <span class="chip2 plain num">${r.passed_count}/${r.total} · ${pct(r.accuracy)}</span></div>
        <div class="muted">优化:${r.changes.map(esc).join(";")}</div>
        <div class="chips">
          <span class="chip2 plain num">较上轮 ${pct(r.improvement)}</span>
          <span class="chip2 good">新通过 ${r.newly_passed.length}</span>
          <span class="chip2 ${r.regressed.length ? "warn" : "good"}">回归 ${r.regressed.length}</span>
        </div>
        ${Object.keys(r.remaining_failures).length
          ? `<div class="muted">剩余失败:${Object.entries(r.remaining_failures).map(([l, items]) => `${l}×${items.length}`).join("、")}</div>` : ""}
      </div>`).join("");
    const pending = (s.pending_versions || []).length
      ? `<div class="hint warn">${icon("alert", 15)}<span>因单轮上限未验证:${s.pending_versions.map(esc).join("、")}
         —— 把基线切到 <b>${esc(s.best.version)}</b> 再运行一轮即可继续验证。</span></div>` : "";
    $("#evolve-out").innerHTML = `
      <div class="hint ok">${icon("check", 15)}<span>循环结束:基线 ${esc(b.version)} ${b.passed_count}/${b.total}(${pct(b.accuracy)})
        → 最佳 <b>${esc(s.best.version)}</b> ${pct(s.best.accuracy)}
        (迭代 ${s.iterations_used} 轮,${esc(s.stop_reason)});报告已归档 <b>${esc(s.md_report)}</b></span></div>
      <p style="display:flex;gap:8px;margin:10px 0 0">
        <button class="btn sm" onclick="replayEvolution('${esc(s.evolution_id)}')">${icon("play", 13)} 回放本次进化</button>
        <button class="btn sm secondary" onclick="quickCompareVersion('${esc(s.best.version)}')">${icon("scale", 13)} 与上一版本对比</button>
      </p>
      ${pending}${rounds}`;
    toast(`自进化完成:最佳 ${s.best.version} ${pct(s.best.accuracy)}`);
    loadHealth();
  });
  loopRunning(false);
}
/* ============ 版本对比 ============ */
function filterCompareB() {
  /* A 的评测集联动过滤 B 的选项:跨评测集组合从源头不可选,/api/compare 的 400 仅作 API 层兜底。 */
  const sa = $("#cmp-a"), sb = $("#cmp-b");
  if (!sa || !sb) return;
  const evalset = sa.selectedOptions[0]?.dataset.evalset ?? "";
  let firstUsable = null;
  for (const o of sb.options) {
    const usable = o.dataset.evalset === evalset;
    o.hidden = !usable;
    o.disabled = !usable;
    if (usable && !firstUsable) firstUsable = o;
  }
  if (firstUsable && sb.selectedOptions[0]?.hidden) sb.value = firstUsable.value;
}
async function renderCompare() {
  const reports = await api("/api/reports");
  const options = reports.map(r =>
    `<option value="${esc(r.report_id)}" data-evalset="${esc(r.evalset_id || "")}">${esc(r.report_id)}(${esc(r.version)} ${pct(r.accuracy)})</option>`).join("");
  $("#tab-compare").innerHTML = `
    <div class="card">
      <h3><span class="h-ico">${icon("scale", 16)}</span>报告对比</h3>
      <p class="desc">闭环第 6 步:迭代是否合格,取决于「目标案例提升 + 历史案例不回归」,这里做逐 case 差分。仅支持同一评测集内的报告对比。</p>
      ${reports.length < 2 ? emptyBox("scale", "至少需要两份报告才能对比", "先在评测看板运行评测生成报告")
        : `<div class="row">
            <div><label>报告 A(基线)</label><select id="cmp-a" onchange="filterCompareB()">${options}</select></div>
            <div><label>报告 B(对比)</label><select id="cmp-b">${options}</select></div>
          </div>
          <p style="display:flex;gap:10px;margin:16px 0 0">
            <button class="btn" id="cmp-go" onclick="doCompare(this)">${icon("scale", 15)} 对比</button>
            <button class="btn secondary" onclick="const a=$('#cmp-a'),b=$('#cmp-b');[a.value,b.value]=[b.value,a.value];filterCompareB()">${icon("swap", 15)} 交换</button>
          </p>
          <div id="cmp-out"></div>`}
    </div>`;
  filterCompareB();              // 初始按 A 默认选中项过滤 B
  await doCompareFromPreset();   // 快捷对比入口先把 preset 写入 sessionStorage,这里渲染完即消费(无竞态)
}
const DIFF_BADGE = { fixed: "修复", regressed: "回归", changed: "数值变化",
                     both_failed: "仍失败", added: "新增检查", removed: "移除检查" };
function diffDetailHtml(r) {
  if (!r.check_diffs || !r.check_diffs.length) return "";
  const items = r.check_diffs.map(d => `
    <div class="diff-item">
      <span class="diff-badge ${d.status}">${DIFF_BADGE[d.status] || d.status}</span>
      <div class="diff-flow"><em>${esc(d.type)}${d.target && d.target !== "summary" ? " · " + esc(d.target) : ""}</em>
        <span class="old">${esc(d.a_detail || "—")}</span><span class="arrow">→</span>${esc(d.b_detail || "—")}</div>
    </div>`).join("");
  return `<tr class="diff-row" data-for="${esc(r.case_id)}"><td colspan="7">${items}</td></tr>`;
}
let cmpRows = [];
async function doCompare(btn) {
  await withBusy(btn, async () => {
    const out = await api(`/api/compare?a=${$("#cmp-a").value}&b=${$("#cmp-b").value}`);
    cmpRows = out.rows;
    const rows = out.rows.map(r => {
      const changed = (r.a_passed !== r.b_passed) || (r.check_diffs && r.check_diffs.length > 0);
      return `<tr>
        <td class="num">${esc(r.case_id)}</td><td>${esc(r.label)}</td><td>${esc(r.title)}</td>
        <td>${pill(r.a_passed)}</td><td>${pill(r.b_passed)}</td>
        <td class="num" style="white-space:nowrap">${r.a_score ?? "—"} → ${r.b_score ?? "—"}${changed
          ? ` <button class="diff-toggle" onclick="toggleDiffRow('${esc(r.case_id)}')">${icon("activity", 12)} ${r.check_diffs.length} 项变化</button>` : ""}</td></tr>${changed ? diffDetailHtml(r) : ""}`;
    }).join("");
    const nFixed = out.rows.reduce((s, r) => s + (r.check_diffs || []).filter(d => d.status === "fixed").length, 0);
    const nReg = out.rows.reduce((s, r) => s + (r.check_diffs || []).filter(d => d.status === "regressed").length, 0);
    const nDiffRows = out.rows.filter(r => r.check_diffs && r.check_diffs.length).length;
    const barRow = (tag, rep) => `<div class="cmp-bar-row">
      <span class="cb-tag" title="${esc(rep.report_id)}">${tag} · ${esc(rep.version)}</span>
      <span class="cb-track"><i style="background:${VER_COLOR[rep.version] || "var(--primary)"}" data-w="${(rep.accuracy * 100).toFixed(1)}"></i></span>
      <span class="cb-val">${pct(rep.accuracy)}</span></div>`;
    $("#cmp-out").innerHTML = `
      <div class="cmp-bars">${barRow("A 基线", out.a)}${barRow("B 对比", out.b)}</div>
      <div class="chips">
        <span class="chip2 plain">A:${esc(out.a.version)} ${pct(out.a.accuracy)}</span>
        <span class="chip2 plain">B:${esc(out.b.version)} ${pct(out.b.accuracy)}</span>
        <span class="chip2 good">新通过 ${out.newly_passed.length} 条</span>
        <span class="chip2 ${out.regressed.length ? "warn" : "good"}">回归 ${out.regressed.length} 条</span>
        ${nFixed ? `<span class="chip2 good">判分修复 ${nFixed} 项</span>` : ""}
        ${nReg ? `<span class="chip2 warn">判分回归 ${nReg} 项</span>` : ""}
        ${nDiffRows ? `<button class="btn sm secondary" style="margin-left:auto" id="cmp-expand" onclick="toggleAllDiffs(this)">${icon("activity", 13)} 展开全部 ${nDiffRows} 行差分</button>` : ""}
      </div>
      <div class="table-wrap scroll-tbl"><table>
        <thead><tr><th>Case</th><th>标签</th><th>标题</th><th>A</th><th>B</th><th class="num">得分变化</th></tr></thead>
        <tbody>${rows}</tbody></table></div>`;
    animateBars($("#cmp-out"));   // A/B 得分条从 0 滑向目标值
  });
}
/* 一键展开/收起全部差分行(逐行点太碎;按当前是否有展开行决定方向) */
function toggleAllDiffs(btn) {
  const rows = $$("#cmp-out tr.diff-row");
  if (!rows.length) return;
  const anyOpen = rows.some(r => r.classList.contains("open"));
  rows.forEach(r => r.classList.toggle("open", !anyOpen));
  btn.innerHTML = `${icon("activity", 13)} ${anyOpen ? "展开" : "收起"}全部 ${rows.length} 行差分`;
}
function toggleDiffRow(caseId) {
  const row = document.querySelector(`tr.diff-row[data-for="${CSS.escape(caseId)}"]`);
  if (!row) return;
  row.classList.toggle("open");   // .open 驱动展开动画;CSS 默认 display:none
}
/* ============ 分析提交 ============ */
let cachedDatasets = [];
async function renderAnalyze() {
  const [versions, datasets] = await Promise.all([api("/api/versions"), api("/api/datasets")]);
  cachedDatasets = datasets;
  $("#tab-analyze").innerHTML = `
    <div class="card">
      <h3><span class="h-ico">${icon("flask", 16)}</span>发起一次交通分析</h3>
      <p class="desc">用任意版本的管线分析任意情景数据集 —— 情景建模在数据参数里,管线零改动即可被场景检验。</p>
      <div class="row">
        <div><label>管线版本</label><select id="an-version">
          ${versions.map(v => `<option value="${esc(v.version)}">${esc(v.version)} · ${esc(v.name)}</option>`).join("")}</select></div>
        <div><label>情景数据集</label><select id="an-dataset" onchange="onAnalyzeDatasetChange()">
          ${datasets.map(d => `<option value="${esc(d.name)}">${esc(d.name)} · ${esc((d.scenario && d.scenario.tag) || "")}</option>`).join("")}</select></div>
      </div>
      <div id="an-scenario"></div>
      <p style="margin:16px 0 0"><button class="btn" onclick="doAnalyze(this)">${icon("play", 15)} 分析</button></p>
      <div id="an-out"></div>
    </div>`;
  onAnalyzeDatasetChange();
}
function onAnalyzeDatasetChange() {
  const ds = cachedDatasets.find(d => d.name === $("#an-dataset").value);
  $("#an-scenario").innerHTML = ds && ds.scenario
    ? `<div class="hint">${icon("bulb", 15)}<span><b>${esc(ds.scenario.tag)}</b> — ${esc(ds.scenario.insight)}</span></div>` : "";
}
/* 饱和度内联微条:>0.8 拥堵区红、>0.6 缓行区橙,一眼读出拥挤程度 */
const satBar = s => {
  if (s === null || s === undefined) return "";
  const v = Math.min(Number(s), 1.2) / 1.2 * 100;
  const tone = s >= 0.8 ? "hot" : s >= 0.6 ? "warm" : "";
  return `<span class="mini-bar ${tone}"><i style="width:0%" data-w="${v.toFixed(1)}"></i></span>`;
};
async function doAnalyze(btn) {
  await withBusy(btn, async () => {
    const out = await api("/api/analyze", {
      version: $("#an-version").value, dataset_name: $("#an-dataset").value,
    });
    const rows = out.segments.map(s => `<tr>
      <td class="num">${esc(s.segment_id)}</td><td>${esc(s.name)}</td>
      <td>${lvPill(s.classification)}</td>
      <td class="num" style="white-space:nowrap">${s.saturation ?? "—"}${satBar(s.saturation)}</td>
      <td class="num">${s.delay_index ?? "—"}</td>
      <td class="num">${s.speed_ratio ?? "—"}</td><td>${esc(s.status)}</td></tr>`).join("");
    const recs = (out.recommendations || []).map(r =>
      `<li style="display:flex;gap:8px;margin-bottom:6px"><span style="color:var(--warn);margin-top:2px">${icon("tool", 14)}</span><span>${esc(r.text)}</span></li>`).join("");
    $("#an-out").innerHTML = `
      <div class="hint ok">${icon("check", 15)}<span><b>${esc(out.summary)}</b></span></div>
      ${rows ? `<div class="table-wrap" style="margin-top:12px"><table>
        <thead><tr><th>路段</th><th>名称</th><th>等级</th><th class="num">饱和度</th><th class="num">延误指数</th><th class="num">速度比</th><th>状态</th></tr></thead>
        <tbody>${rows}</tbody></table></div>`
        : emptyBox("inbox", "该数据集没有路段", "优雅降级为空结果,管线不崩溃")}
      ${recs ? `<p style="margin:14px 0 6px;font-weight:700;font-size:13px">处置建议</p><ul style="margin:0;padding-left:4px;list-style:none;font-size:13px">${recs}</ul>` : ""}`;
    animateBars($("#an-out"));   // 饱和度微条从 0 滑向目标值
  });
}
/* ============ 进化回放动画 ============ */
let replayTimers = [], replaySteps = [], replayIdx = 0, replayEvo = null, replayPaused = false;

async function replayEvolution(evoId) {
  try { replayEvo = await api("/api/evolutions/" + encodeURIComponent(evoId)); }
  catch (e) { toast(e.message, true); return; }
  const b = replayEvo.baseline;
  replaySteps = [{ version: b.version, accuracy: b.accuracy,
                   passed: b.passed_count, total: b.total, label: "基线" }];
  for (const r of replayEvo.rounds) {
    replaySteps.push({ version: r.version, accuracy: r.accuracy,
                       passed: r.passed_count, total: r.total,
                       label: `第 ${r.round} 轮 · ${r.version_name}`,
                       changes: r.changes, newly: r.newly_passed.length,
                       regressed: r.regressed.length });
  }
  $("#rp-tag").textContent = replayEvo.evalset_id;
  $("#rp-sub").textContent =
    `${replayEvo.total_cases} 条 replaycase · ${replaySteps.length - 1} 轮迭代 · 停止:${replayEvo.stop_reason}`;
  $("#replay-mask").classList.remove("hidden");
  replayStart();
}
/* 从第 startIdx 步起排片:firstDelay 后播首步,此后每步隔 stepDelay;末尾补结束旁白 */
function replayScheduleFrom(startIdx, firstDelay, stepDelay) {
  for (let i = startIdx; i < replaySteps.length; i++) {
    replayTimers.push(setTimeout(() => replayShowStep(i), firstDelay + (i - startIdx) * stepDelay));
  }
  replayTimers.push(setTimeout(() => {
    $("#rp-step").innerHTML = `<b>回放结束</b>最佳版本 ${esc(replayEvo.best.version)} ${pct(replayEvo.best.accuracy)}(总提升 ${pct(replayEvo.best.accuracy - replayEvo.baseline.accuracy)})`;
  }, firstDelay + replaySteps.length * stepDelay + 300));
}
function replayStart(replay = false) {
  replayTimers.forEach(clearTimeout);
  replayTimers = [];
  replayIdx = 0; replayPaused = false;
  syncPauseBtn();
  $("#rp-chips").innerHTML = "";
  $("#rp-step").innerHTML = "";
  $("#rp-bar").style.width = "0%";
  if (REDUCED) {  // 减弱动态:直接呈现最终状态(暂停无意义,藏起按钮)
    $("#rp-pause").style.display = "none";
    for (let i = 0; i < replaySteps.length; i++) replayShowStep(i, true);
    return;
  }
  $("#rp-pause").style.display = "";
  replayScheduleFrom(0, replay ? 500 : 600, replay ? 500 : 1500);
}
function syncPauseBtn() {
  const btn = $("#rp-pause");
  if (btn) btn.innerHTML = replayPaused ? `${icon("play", 13)} 继续` : `${icon("pause", 13)} 暂停`;
}
/* 暂停:清掉未播的定时器;继续:从下一步起以更紧凑的节奏续播 */
function replayTogglePause() {
  if (!replaySteps.length || REDUCED) return;
  if (!replayPaused) {
    replayTimers.forEach(clearTimeout);
    replayTimers = [];
    replayPaused = true;
    syncPauseBtn();
    $("#rp-step").innerHTML = `<b>已暂停</b>点「继续」从下一步接着看,或「重新播放」从头来。`;
    $("#rp-step").classList.remove("swap"); void $("#rp-step").offsetWidth; $("#rp-step").classList.add("swap");
    return;
  }
  replayPaused = false;
  syncPauseBtn();
  replayScheduleFrom(replayIdx + 1, 150, 1100);
}
function replayShowStep(i, instant = false) {
  replayIdx = i;   // 暂停/继续以此为进度游标
  const s = replaySteps[i];
  const prev = i === 0 ? 0 : replaySteps[i - 1].accuracy;
  // 芯片
  const delta = i === 0 ? "" :
    `<span class="delta ${s.accuracy > prev ? "up" : s.accuracy < prev ? "down" : "zero"}">${s.accuracy > prev ? "▲" : s.accuracy < prev ? "▼" : ""} ${pct(Math.abs(s.accuracy - prev))}</span>`;
  $("#rp-chips").insertAdjacentHTML("beforeend",
    `${i ? '<span class="traj-arrow">' + icon("arrowR", 13) + "</span>" : ""}
     <span class="traj-chip ${s.version === replayEvo.best.version ? "best" : ""}"><span class="tv">${esc(s.version)}</span><b>${pct(s.accuracy)}</b>${delta}</span>`);
  // 得分计数(基线从 0 起展示步进感)
  replayCountTo(s.accuracy, instant);
  $("#rp-meta").textContent = `${s.passed}/${s.total} 通过 · ${s.label}`;
  $("#rp-bar").style.width = (s.accuracy * 100).toFixed(1) + "%";
  // 旁白
  const step = $("#rp-step");
  if (i === 0) {
    step.innerHTML = `<b>基线测量(${esc(s.version)})</b>得分 ${s.passed}/${s.total} —— 没有基线的提升是不可证伪的。`;
  } else {
    step.innerHTML = `<b>${esc(s.label)}</b>
      ${s.changes.slice(0, 2).map(esc).join(";")}${s.changes.length > 2 ? "…" : ""}<br>
      新通过 <b class="num">${s.newly}</b> 条${s.regressed ? `<span class="warn"> · 回归 ${s.regressed} 条(应回退本轮改动)</span>` : " · 无回归"}`;
  }
  step.classList.remove("swap"); void step.offsetWidth; step.classList.add("swap");
}
function replayCountTo(target, instant) {
  const el = $("#rp-score");
  if (instant || REDUCED) { el.textContent = pct(target); return; }
  const from = parseFloat(el.dataset.v || "0");
  el.dataset.v = target;
  const t0 = performance.now(), dur = 800;
  const tick = t => {
    const p = Math.min((t - t0) / dur, 1), e = 1 - Math.pow(1 - p, 3);
    el.textContent = pct(from + (target - from) * e);
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}
function closeReplay() {
  replayTimers.forEach(clearTimeout);
  replayTimers = [];
  replayPaused = false;
  $("#rp-score").dataset.v = "0";
  animateHide($("#replay-mask"));
}
$("#replay-mask").addEventListener("click", e => { if (e.target === $("#replay-mask")) closeReplay(); });

/* ============ 报告详情:看板工作区 / 抽屉共用渲染 ============ */
function reportDetailHtml(rep) {
  window.__lastReport = rep;   // 导出按钮取用(onclick 属性传不了对象)
  const labels = Object.entries(rep.label_stats).map(([label, st]) => `
    <tr><td>${esc(label)}</td><td class="num">${st.passed}/${st.total}</td><td class="num">${pct(st.passed / st.total)}</td></tr>`).join("");
  const perCase = rep.results.map(r => `
    <tr><td class="num">${esc(r.case_id)}</td><td>${esc(r.label)}</td><td>${pill(r.passed)}</td>
    <td class="num">${r.score.toFixed(2)}</td></tr>`).join("");
  return `
    <div class="chips" style="margin-top:0">
      <span class="chip2 plain">版本 ${esc(rep.version)}</span>
      <span class="chip2 ${rep.accuracy === 1 ? "good" : ""} num">得分 ${pct(rep.accuracy)}</span>
      <span class="chip2 plain num">${rep.passed_count}/${rep.total} 通过</span>
      <span class="chip2 plain num">耗时 ${rep.duration_ms} ms</span>
    </div>
    ${rep.changes && rep.changes.length ? `<p style="margin:12px 0 4px;font-weight:700;font-size:13px">优化内容</p>
      <ul style="margin:0;padding-left:18px;font-size:12.5px;color:var(--t3)">${rep.changes.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    <p style="margin:12px 0 4px;font-weight:700;font-size:13px">分标签通过率</p>
    <div class="table-wrap"><table>
      <thead><tr><th>标签</th><th class="num">通过/总数</th><th class="num">通过率</th></tr></thead>
      <tbody>${labels}</tbody></table></div>
    <p style="margin:12px 0 4px;font-weight:700;font-size:13px">逐 case 结果</p>
    <div class="table-wrap"><table>
      <thead><tr><th>Case</th><th>标签</th><th>结果</th><th class="num">得分</th></tr></thead>
      <tbody>${perCase}</tbody></table></div>
    <p style="margin:14px 0 0;display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn sm secondary" onclick="quickCompare('${esc(rep.report_id)}')">${icon("scale", 13)} 与最新版本对比</button>
      <button class="btn sm secondary" onclick="exportReportJson()">${icon("filetext", 13)} 导出 JSON</button></p>`;
}
function exportReportJson() {
  const rep = window.__lastReport;
  if (!rep) return;
  downloadJson(`${rep.report_id}.json`, rep);
  toast(`已导出 ${rep.report_id}.json`);
}
async function showReport(reportId) {
  // 看板页:直接进工作区详情(不打断三栏布局);其他页面沿用抽屉
  if (!views.app.classList.contains("hidden") && $("#tab-dashboard").classList.contains("active")) {
    selectReport(reportId);
    return;
  }
  let rep;
  try { rep = await api("/api/reports/" + reportId); }
  catch (e) { toast(e.message, true); return; }
  $("#drawer-title").textContent = reportId;
  $("#drawer-body").innerHTML = reportDetailHtml(rep);
  $("#drawer-mask").classList.remove("hidden");
  $("#drawer").classList.remove("hidden");
}
function closeDrawer() {
  const mask = $("#drawer-mask"), drawer = $("#drawer");
  mask.classList.add("closing");
  drawer.classList.add("closing");   // 抽屉本体滑右淡出,遮罩同步淡出
  setTimeout(() => {
    for (const el of [mask, drawer]) { el.classList.add("hidden"); el.classList.remove("closing"); }
  }, 250);
}
$("#drawer-mask").addEventListener("click", closeDrawer);
/* ============ 快捷对比:任一报告 vs 同版本最新报告 ============ */
async function quickCompare(reportId) {
  const target = cmdkReports.length ? cmdkReports : await api("/api/reports").catch(() => []);
  const rep = target.find(r => r.report_id === reportId);
  if (!rep) { toast("未找到该报告", true); return; }
  const latest = target.find(r => r.version === rep.version);  // reports 列表本身时间倒序
  closeDrawer();
  if (!latest || latest.report_id === reportId) { toast("没有更新的同版本报告可对比(先重跑一次评测)"); return; }
  sessionStorage.setItem("harness_cmp", JSON.stringify({ a: latest.report_id, b: reportId }));
  switchTab("compare");   // renderCompare 渲染完成后自会消费 preset,无需定时器猜时机
}
async function quickCompareVersion(version) {
  const reports = cmdkReports.length ? cmdkReports : await api("/api/reports").catch(() => []);
  const latestOf = v => reports.find(r => r.version === v);
  const cur = latestOf(version);
  if (!cur) { toast(`版本 ${version} 还没有报告(先运行评测)`, true); return; }
  const order = ["v0", "v1", "v2", "v3", "v4", "v5"];
  const prevV = order[order.indexOf(version) - 1];
  const prev = prevV && latestOf(prevV);
  if (!prev) { toast(`没有 ${prevV || "上一版本"} 的报告可对比`, true); return; }
  sessionStorage.setItem("harness_cmp", JSON.stringify({ a: prev.report_id, b: cur.report_id }));
  switchTab("compare");
}
async function doCompareFromPreset() {
  const preset = sessionStorage.getItem("harness_cmp");
  if (!preset) return;
  sessionStorage.removeItem("harness_cmp");
  const { a, b } = JSON.parse(preset);
  const sa = $("#cmp-a"), sb = $("#cmp-b"), go = $("#cmp-go");
  if (!sa || !sb || !go) return;
  sa.value = a;
  filterCompareB();   // A 变更联动过滤 B;跨评测集的 preset 值仍在选项里,由 /api/compare 的 400 兜底提示
  sb.value = b;
  await doCompare(go);
}
/* ============ 全局快捷键 ============ */
document.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    $("#cmdk-mask").classList.contains("hidden") ? openCmdk() : closeCmdk();
  } else if (e.key === "Escape") {
    if (!$("#cmdk-mask").classList.contains("hidden")) closeCmdk();
    if (!$("#sheet-mask").classList.contains("hidden")) closeSheet();
    if (!$("#drawer").classList.contains("hidden")) closeDrawer();
    if (!$("#replay-mask").classList.contains("hidden")) closeReplay();
  }
});
