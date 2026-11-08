/* Transportation Harness · 看板应用脚本(core · 基础设施层)
   无构建拆分(TH-04 第二批):经典脚本共享全局作用域,加载顺序 app-core -> app-board -> app-manage。
   本文件职责:图标库/工具/主题/视图分流与登录/健康检查/命令面板/点击轨道环/导航/面板拖拽/PWA */
"use strict";
/* ============ SVG 图标库(Lucide 风格,统一 24 viewBox 线性图标) ============ */
const ICONS = {
  /* —— 核心语义图标(定制:信号灯 · 车道虚线 · 循环节点母题)—— */
  dashboard: '<rect x="3.5" y="4" width="17" height="16" rx="3"/><circle cx="8" cy="8" r="1.3" fill="currentColor" stroke="none"/><circle cx="8" cy="12" r="1.3" fill="currentColor" stroke="none" opacity=".55"/><circle cx="8" cy="16" r="1.3" fill="currentColor" stroke="none" opacity=".3"/><path d="M13 16v-4.5"/><path d="M16.5 16v-7"/>',
  database: '<path d="m12 3 9 4.5-9 4.5L3 7.5 12 3Z"/><path d="m3 12 9 4.5 9-4.5"/><path d="m3 16.5 9 4.5 9-4.5"/><path d="M9.5 7.5h5" stroke-dasharray="1.6 1.8"/>',
  scale: '<rect x="3.5" y="4.5" width="7" height="12" rx="2.2"/><rect x="13.5" y="4.5" width="7" height="12" rx="2.2"/><circle cx="7" cy="8.5" r="1.1" fill="currentColor" stroke="none"/><circle cx="7" cy="12.5" r="1.1"/><circle cx="17" cy="8.5" r="1.1"/><circle cx="17" cy="12.5" r="1.1" fill="currentColor" stroke="none"/><path d="M7 16.5v2M17 16.5v2"/><path d="M4.5 21h5"/><path d="M14.5 21h5"/>',
  flask: '<path d="M9.5 3h5"/><path d="M10.5 3v5.2L5.6 17.5A2 2 0 0 0 7.4 20.5h9.2a2 2 0 0 0 1.8-3L13.5 8.2V3"/><path d="M8 15h8" stroke-dasharray="2 2.2"/>',
  rocket: '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/><circle cx="14.5" cy="9.5" r="1.4"/>',
  filetext: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
  play: '<polygon points="6 3 20 12 6 21 6 3"/>',
  pause: '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
  cycle: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/><circle cx="12" cy="12" r="1.3" fill="currentColor" stroke="none"/>',
  plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
  trash: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  trend: '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
  clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><circle cx="12" cy="10.8" r="1.6" fill="currentColor" stroke="none"/>',
  lock: '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  unlock: '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>',
  target: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
  branch: '<line x1="6" x2="6" y1="3" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/>',
  swap: '<path d="M8 3 4 7l4 4"/><path d="M4 7h16"/><path d="m16 21 4-4-4-4"/><path d="M20 17H4"/>',
  inbox: '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
  activity: '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/><circle cx="2" cy="12" r="1.2" fill="currentColor" stroke="none"/><circle cx="22" cy="12" r="1.2" fill="currentColor" stroke="none"/>',
  layers: '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
  chevR: '<path d="m9 18 6-6-6-6"/>',
  panelLeft: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/>',
  arrowR: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
  bulb: '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
  tool: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
  gauge: '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
  key: '<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/>',
  settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
  spark: '<path d="M12 3l1.9 5.7a1 1 0 0 0 .63.63L20.2 11.2a.57.57 0 0 1 0 1.08l-5.7 1.9a1 1 0 0 0-.63.63L12 20.4a.57.57 0 0 1-1.08 0l-1.9-5.7a1 1 0 0 0-.63-.63l-5.7-1.9a.57.57 0 0 1 0-1.08l5.7-1.9a1 1 0 0 0 .63-.63L11 3a.57.57 0 0 1 1 0z"/><circle cx="11.7" cy="11.9" r="1.1" fill="currentColor" stroke="none"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  book: '<path d="M12 7v14" stroke-dasharray="2.2 2.4"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
};
const icon = (name, size = 18) =>
  `<svg class="ico-svg" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ""}</svg>`;
/* ============ 通用工具 ============ */
const LEVELS = ["畅通", "基本畅通", "缓行", "拥堵", "严重拥堵", "数据缺失"];
const LV_KEY = { "畅通": "a", "基本畅通": "b", "缓行": "c", "拥堵": "d", "严重拥堵": "e", "数据缺失": "x" };
const VER_COLOR = { v0: "#95a0b8", v1: "#64748b", v2: "#079455", v3: "#f79009" };
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = x => (x * 100).toFixed(1) + "%";
const fmtTs = s => {
  if (!s) return "—";
  const d = String(s).replace(/\D/g, "");
  if (d.length < 8) return String(s);
  const y = d.slice(0, 4), mo = d.slice(4, 6), da = d.slice(6, 8);
  const hm = d.length >= 12 ? ` ${d.slice(8, 10)}:${d.slice(10, 12)}` : "";
  return (y === String(new Date().getFullYear()) ? `${mo}-${da}` : `${y}-${mo}-${da}`) + hm;
};
const lvPill = lv => `<span class="lv lv-${LV_KEY[lv] || "x"}"><i></i>${esc(lv)}</span>`;
const pill = p => p === null || p === undefined ? `<span class="pill na">—</span>`
  : (p ? `<span class="pill pass">${icon("check", 12)}PASS</span>` : `<span class="pill fail">${icon("x", 12)}FAIL</span>`);
const deltaTag = d => d > 0.0005 ? `<span class="delta up">▲ ${pct(d)}</span>`
  : (d < -0.0005 ? `<span class="delta down">▼ ${pct(-d)}</span>` : `<span class="delta zero">持平</span>`);
const stopTag = reason => /全部通过/.test(reason) ? `<span class="tag ok">${icon("check", 12)}${esc(reason)}</span>`
  : /收益/.test(reason) ? `<span class="tag">${icon("clock", 12)}${esc(reason)}</span>` : `<span class="tag warn">${icon("alert", 12)}${esc(reason)}</span>`;
const emptyBox = (ico, title, sub, action = "") =>
  `<div class="empty"><div class="e-ico">${icon(ico, 26)}</div><div class="e-t">${title}</div><div class="e-s">${sub}</div>${action}</div>`;

/* 全局 API 加载条:请求在途时顶缘滑块可见,全部结束(含小延迟防闪烁)后隐藏。
   quiet=true 的调用(如 30s 健康心跳)不点亮进度条,保持界面安静 */
let _inflight = 0;
function apiBusy(delta) {
  _inflight = Math.max(0, _inflight + delta);
  clearTimeout(apiBusy._t);
  if (_inflight > 0) $("#api-progress").classList.add("on");
  else apiBusy._t = setTimeout(() => $("#api-progress").classList.remove("on"), 260);
}
async function api(url, body, method, quiet) {
  const m = method || (body ? "POST" : "GET");
  const opt = body || m !== "GET"
    ? { method: m, headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined } : {};
  let res;
  if (!quiet) apiBusy(1);
  try { res = await fetch(url, opt); }
  catch (e) { throw new Error("无法连接服务器,请确认服务已启动"); }
  finally { if (!quiet) apiBusy(-1); }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const e = new Error(err.detail || `请求失败(${res.status})`);
    e.status = res.status;   // 调用方按状态码分支(如 403 需给放开指引),detail 原文不丢
    throw e;
  }
  return res.json();
}
function toast(msg, isErr = false) {
  const el = $("#toast");
  el.innerHTML = `${icon(isErr ? "alert" : "check", 16)}<span>${esc(msg)}</span>`;
  el.classList.toggle("err", isErr); el.classList.add("show");
  clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove("show"), 3400);
}
/* 下载 / 复制:导出报告、导出 case、命令面板共用 */
function downloadJson(name, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}
async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; }
  catch {   // 非安全上下文回退:隐藏 textarea + execCommand
    const ta = document.createElement("textarea");
    ta.value = text; ta.style.cssText = "position:fixed;opacity:0";
    document.body.appendChild(ta); ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch {}
    ta.remove();
    return ok;
  }
}
/* 弹层退场:先播 .closing 动画,播完再真正隐藏(怎么进来就怎么出去) */
function animateHide(mask, after) {
  if (mask.classList.contains("closing") || mask.classList.contains("hidden")) return;
  mask.classList.add("closing");
  clearTimeout(mask._hideT);   // 计时器挂在元素上:退场途中被重新激活时可在 showView 里精确取消
  mask._hideT = setTimeout(() => {
    mask.classList.add("hidden");
    mask.classList.remove("closing");
    if (after) after();
  }, 190);
}
async function withBusy(btn, fn) {
  if (!btn) return fn();
  const old = btn.innerHTML; btn.disabled = true; btn.innerHTML = `${icon("cycle", 15)} 运行中…`;
  try { return await fn(); }
  catch (e) { toast(e.message, true); }
  finally { btn.disabled = false; btn.innerHTML = old; }
}
/* 样式化确认弹窗(替代原生 confirm):返回 Promise,await 后拿布尔 */
let _confirmResolve = null;
function askConfirm(title, text, opts = {}) {
  if (_confirmResolve) settleConfirm(false);   // 前一次未结算:按取消收场,防悬挂
  $("#confirm-title").textContent = title;
  $("#confirm-text").textContent = text;
  $("#confirm-ico").innerHTML = icon(opts.icon || "trash", 16);
  const yes = $("#confirm-yes");
  yes.className = "btn" + (opts.danger === false ? "" : " danger");
  yes.textContent = opts.yes || "确认删除";
  $("#confirm-no").textContent = opts.no || "取消";
  $("#confirm-mask").classList.remove("hidden");
  setTimeout(() => yes.focus(), 80);
  return new Promise(res => { _confirmResolve = res; });
}
function settleConfirm(v) {
  const res = _confirmResolve; _confirmResolve = null;
  animateHide($("#confirm-mask"));
  if (res) res(v);
}
/* 等待 async 渲染产物就绪后执行(渲染含多次取数,固定延时必竞态);超时静默放弃 */
function whenReady(get, cb, timeout = 6000) {
  const t0 = performance.now();
  (function tick() {
    const v = get();
    if (v) return cb(v);
    if (performance.now() - t0 > timeout) return;
    setTimeout(tick, 70);
  })();
}
/* KPI 数字滚动(尊重系统减弱动态;后台页签 rAF 暂停,直接落终值,不允许停在 0) */
function runCountUps(scope = document) {
  const els = [...scope.querySelectorAll("[data-countup]")];
  const finish = () => els.forEach(el => { el.textContent = Math.round(parseFloat(el.dataset.countup) || 0); });
  const reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced || document.hidden) { finish(); return; }
  els.forEach(el => {
    const target = parseFloat(el.dataset.countup);
    if (isNaN(target)) return;
    const t0 = performance.now(), dur = 650;
    const tick = t => {
      const p = Math.min((t - t0) / dur, 1), e = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(target * e);
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}
/* 进度条从 0 滑向目标值:渲染时先置 0 宽 + data-w,双 rAF 确保初始态提交后再赋终值,
   令宽度过渡真正播放;后台页签 rAF 不走针 → 立即落地,另挂兜底定时(幂等)防渲染帧被抑制 */
function animateBars(scope = document) {
  const apply = () => scope.querySelectorAll("[data-w]").forEach(el => { el.style.width = el.dataset.w + "%"; });
  if (document.hidden) { apply(); return; }
  requestAnimationFrame(() => requestAnimationFrame(apply));
  setTimeout(apply, 450);
}

function switchTab(tab) {
  try { sessionStorage.setItem("harness_tab", tab); } catch {}  // 刷新工作台后恢复所在页签
  /* 导航高亮与标题即时反馈,不随内容动画等待 */
  $$(".nav-item[data-tab]").forEach(b => b.classList.toggle("active", b.dataset.tab === tab));
  const [t, sub] = TITLES[tab];
  $("#page-title").textContent = t; $("#page-sub").textContent = sub;
  for (const el of [$("#page-title"), $("#page-sub")]) {   // 标题随内容轻浮起,而非瞬间换字
    el.classList.remove("swap"); void el.offsetWidth; el.classList.add("swap");
  }

  /* 方向感:沿导航向下切换 → 新内容自下方滑入、旧页向上让位;向上切换反之 */
  const TAB_ORDER = ["dashboard", "cases", "compare", "analyze", "settings"];
  const current = document.querySelector("main section.page.active");
  const goingDown = !current
    || TAB_ORDER.indexOf(tab) >= TAB_ORDER.indexOf(current.id.replace("tab-", ""));
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

  const applySwap = () => {
    const [t, sub] = TITLES[tab];
    $("#page-title").textContent = t; $("#page-sub").textContent = sub;
    for (const el of [$("#page-title"), $("#page-sub")]) {   // 回退路径:标题轻浮起(VT 路径由快照融合接管)
      el.classList.remove("swap"); void el.offsetWidth; el.classList.add("swap");
    }
    /* 覆盖层交叉淡化(仅无 View Transitions 的回退路径);连点防竞态 */
    $$("main section.leaving").forEach(s => {
      clearTimeout(s._leaveT);
      s.classList.remove("leaving", "leaving-up", "leaving-down");
    });
    $$("main section").forEach(s => {
      s.classList.remove("enter-up", "enter-down");
      if (s.id === "tab-" + tab) {
        void s.offsetWidth;   // 同页签重进时入场动画也能重放
        s.classList.add(goingDown ? "enter-up" : "enter-down");
      }
      s.classList.toggle("active", s.id === "tab-" + tab);
    });
    if (!canViewTransition() && current && current.id !== "tab-" + tab && current.childElementCount > 0 && !reduced) {
      current.classList.add(goingDown ? "leaving-up" : "leaving-down");
      clearTimeout(current._leaveT);
      current._leaveT = setTimeout(() =>
        current.classList.remove("leaving", "leaving-up", "leaving-down"), 280);
    }
    $("#scroll-area").scrollTo({ top: 0 });
    const hasTask = !!TASK_RENDERERS[tab];
    $("#app").classList.toggle("has-task", hasTask);
    if (hasTask) {
      TASK_RENDERERS[tab]();   // 任务页:同时渲染左栏列表与中栏工作区
      const tp = $("#taskpanel");   // 任务区随页签整块浮入;播完摘除,选中/筛选重绘不重播
      tp.classList.remove("tp-enter"); void tp.offsetWidth; tp.classList.add("tp-enter");
      clearTimeout(switchTab._tpT);
      switchTab._tpT = setTimeout(() => tp.classList.remove("tp-enter"), 700);
    } else renderers[tab]();
  };

  /* 主路径:View Transitions 快照形变(旧页没入景深 / 新页抵达对焦);
     回退路径:无该 API 的浏览器走覆盖层交叉淡化 */
  if (canViewTransition()) {
    document.documentElement.dataset.navDir = goingDown ? "down" : "up";
    withViewTransition(applySwap);
  } else applySwap();
}

/* 减弱动态开关:动效注入/回放直出/轨道环共用(原在进化回放分节,拆分时上移至基础层) */
const REDUCED = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
/* ============ 主题(明/暗) ============ */
/* opts.instant:VT 圆形揭示路径跳过 340ms 颜色过渡 —— 快照会定格中间色,揭示完成后二次微变;
   回退路径(命令面板/键盘/reduced-motion/无 VT)不传 instant,保留 theme-anim */
function applyTheme(theme, opts = {}) {
  document.documentElement.dataset.theme = theme;
  if (opts.instant) {
    clearTimeout(applyTheme._t);
    document.documentElement.classList.remove("theme-anim");
  } else {
    document.documentElement.classList.add("theme-anim");   // 切换瞬间全要素颜色过渡
    clearTimeout(applyTheme._t);
    applyTheme._t = setTimeout(() => document.documentElement.classList.remove("theme-anim"), 340);
  }
  try { localStorage.setItem("harness_theme", theme); } catch {}
  $$("[data-theme-toggle]").forEach(btn => { btn.innerHTML = icon(theme === "dark" ? "sun" : "moon", 14); });
  document.querySelector('meta[name="theme-color"]')   // 移动端状态栏/标题栏随主题联动
    ?.setAttribute("content", theme === "dark" ? "#0e111c" : "#f4f5f8");
  applyHeroTheme();   // 欢迎页/登录页与工作台共用同一主题,不再各存一份
}
$$("[data-theme-toggle]").forEach(btn =>
  btn.addEventListener("click", e => toggleTheme(e.clientX, e.clientY)));
applyTheme(document.documentElement.dataset.theme || "light");

/* 欢迎页/登录页主题:与工作台同步(同一 data-theme,两处按钮等效) */
function applyHeroTheme() {
  const light = document.documentElement.dataset.theme === "light";
  $("#view-welcome").classList.toggle("hero-light", light);
  $("#view-login").classList.toggle("hero-light", light);
  $$("[data-hero-toggle]").forEach(btn => { btn.innerHTML = icon(light ? "moon" : "sun", 14); });
}
$$("[data-hero-toggle]").forEach(btn =>
  btn.addEventListener("click", e => toggleTheme(e.clientX, e.clientY)));
/* ============ 视图分流与登录 ============ */
const views = { welcome: $("#view-welcome"), login: $("#view-login"), app: $("#app") };
/* 支持 View Transitions 的浏览器:视图/页签切换走快照形变,并抑制 .hidden 摘除自带的入场动画。
   文档不可见(遮挡/后台)时跳过过渡 —— 快照形变依赖渲染帧,不可见时回调会被无限推迟 */
const canViewTransition = () =>
  typeof document.startViewTransition === "function"
  && !document.hidden
  && !matchMedia("(prefers-reduced-motion: reduce)").matches;
if (typeof document.startViewTransition === "function") document.documentElement.classList.add("vt-run");

/* 快照形变封装:DOM 更新放进 VT 回调;回调若因渲染暂停被无限推迟(遮挡/后台),
   350ms 兜底直接落地,视图交换绝不挂起 —— 之后渲染恢复时形变仍会补播 */
function withViewTransition(applySwap) {
  if (!canViewTransition()) { applySwap(); return undefined; }
  let ran = false;
  const once = () => { if (ran) return; ran = true; applySwap(); };
  const bail = setTimeout(once, 350);
  const vt = document.startViewTransition(() => { clearTimeout(bail); once(); });
  return vt;
}

/* 主题切换统一入口:点击链带坐标走 VT 圆形揭示(圆心=点击点,--r=Math.hypot 到最远角),
   揭示期间 data-vt="theme" 兼任颜色过渡压制(快照须直落终色,见 app.css 揭示块注释);
   命令面板/键盘触发无坐标、reduced-motion、无 VT —— 自然回落 applyTheme 的 340ms 颜色过渡。
   data-vt 的设置与摘除复用 showView 的 dataset.vt + vt.finished.finally 守卫清理模式:
   同一属性两种取值(theme/in/out),不引入第二个状态机与第二个摘除定时器 */
function toggleTheme(clickX, clickY) {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  const root = document.documentElement;
  const hasPoint = Number.isFinite(clickX) && Number.isFinite(clickY) && (clickX || clickY);
  if (!hasPoint || !canViewTransition()) { applyTheme(next); return; }
  root.style.setProperty("--tx", `${clickX}px`);
  root.style.setProperty("--ty", `${clickY}px`);
  root.style.setProperty("--r",
    `${Math.hypot(Math.max(clickX, innerWidth - clickX), Math.max(clickY, innerHeight - clickY))}px`);
  root.dataset.vt = "theme";
  const vt = withViewTransition(() => applyTheme(next, { instant: true }));
  if (vt) {
    toggleTheme._vt = vt;
    vt.finished.finally(() => {   // 只清理自己那次的标记;属性可能已被视图切换改写成 in/out
      if (toggleTheme._vt === vt) {
        if (root.dataset.vt === "theme") delete root.dataset.vt;
        toggleTheme._vt = null;
      }
    });
  } else toggleTheme._vt = null;
}

/* 视图切换(开始页 ↔ 登录 ↔ 工作台):纵深推进 —— 按视图层级定方向 */
const VIEW_DEPTH = { welcome: 0, login: 1, app: 2 };
function showView(name) {
  const prev = Object.keys(views).find(k => !views[k].classList.contains("hidden"));
  const applySwap = () => {
    for (const [k, el] of Object.entries(views)) {
      if (k === name) {
        clearTimeout(el._hideT);   // 取消尚未完成的退场,防止把当前视图藏掉
        el.classList.remove("closing", "hidden");
      } else if (!el.classList.contains("hidden")) {
        if (canViewTransition()) {  // VT:退场交给快照,直接归位
          clearTimeout(el._hideT);
          el.classList.remove("closing");
          el.classList.add("hidden");
        } else animateHide(el);     // 回退:旧视图淡出,与新视图入场交叠为交叉淡化
      }
    }
    try { sessionStorage.setItem("harness_view", name); } catch {}  // 供刷新后就地恢复
  };

  if (prev && prev !== name && canViewTransition()) {
    delete document.documentElement.dataset.navDir;   // 页签形变标记不带入视图形变
    document.documentElement.dataset.vt = VIEW_DEPTH[name] > VIEW_DEPTH[prev] ? "in" : "out";
    const vt = withViewTransition(applySwap);
    if (vt) {
      showView._vt = vt;
      vt.finished.finally(() => {   // 只清理自己那次的标记,避免误删后一次切换的
        if (showView._vt === vt) {
          // 主题揭示(data-vt="theme")与视图切换共用本属性:只摘自己的取值
          if (document.documentElement.dataset.vt === "in" || document.documentElement.dataset.vt === "out")
            delete document.documentElement.dataset.vt;
          showView._vt = null;
        }
      });
    } else showView._vt = null;
  } else {
    applySwap();
    showView._vt = null;
  }
}
function showWelcome() { showView("welcome"); }
function showLogin() { $("#login-err").innerHTML = ""; showView("login"); $("#login-user").focus(); }
function showApp(username) {
  $("#user-name").textContent = username;
  $("#user-avatar").textContent = (username[0] || "A").toUpperCase();
  $("#user-row").style.display = "";
  showView("app");
  let tab = null;
  try { tab = sessionStorage.getItem("harness_tab"); } catch {}
  let went = false;
  const go = () => { if (went) return; went = true; switchTab(TASK_RENDERERS[tab] || renderers[tab] ? tab : "dashboard"); };
  if (showView._vt) {
    showView._vt.finished.finally(go).catch(() => {});   // 两拍衔接:链在 finished( promise )上
    setTimeout(go, 900);                                 // 渲染暂停时兜底触发
  } else go();
  loadHealth(); initAiPanel();
}
async function enterApp() {
  try { showApp((await api("/api/auth/me")).username); }
  catch { showLogin(); }
}
async function boot() {
  loadHealth();
  const who = async () => { try { return (await api("/api/auth/me")).username; } catch { return null; } };
  // 刷新(同标签页重载):停在离开时的视图;全新打开:已登录 → 欢迎页,未登录 → 登录页
  let navType = "navigate";
  try { navType = (performance.getEntriesByType("navigation")[0] || {}).type || "navigate"; } catch {}
  if (navType === "reload") {
    let v = null;
    try { v = sessionStorage.getItem("harness_view"); } catch {}
    if (v === "welcome") return;
    if (v === "login") return showLogin();
    if (v === "app") { const u = await who(); if (u) return showApp(u); return showLogin(); }
  }
  const u = await who();
  /* 等待鉴权期间用户可能已自行导航(弱网/慢回包):已进入工作台则不再落回壳视图 */
  if (views.app.classList.contains("hidden") === false) return;
  if (u) showWelcome(); else showLogin();
}
async function doLogin(btn) {
  const old = btn.textContent; btn.disabled = true; btn.textContent = "登录中…";
  $("#login-err").innerHTML = "";
  try {
    const out = await api("/api/auth/login", {
      username: $("#login-user").value.trim(), password: $("#login-pass").value,
    });
    showWelcome(); toast(`欢迎回来,${out.username}`);
    // 初始口令未改时业务接口是 403 门禁状态:立刻引导改密,而不是让用户逐页撞 403
    const h = await api("/api/health");
    if (h.default_credentials) {
      openPasswordModal();
      $("#pw-err").innerHTML = `<div class="hint warn">${icon("alert", 15)}
        <span>初始口令尚未修改:改掉口令之前,业务接口一律 403,看板各页暂无数据。请设置新口令。</span></div>`;
    }
  } catch (e) {
    $("#login-err").innerHTML = `<div id="login-hint" style="display:block;background:rgba(240,68,56,.12);border-color:rgba(240,68,56,.4);color:#fda29b">${esc(e.message)}</div>`;
  } finally { btn.disabled = false; btn.textContent = old; }
}
async function doLogout() {
  try { await api("/api/auth/logout", {}); } catch {}
  toast("已退出登录");
  showLogin();
}
function openPasswordModal() {
  $("#pw-old").value = ""; $("#pw-new").value = ""; $("#pw-new2").value = ""; $("#pw-err").innerHTML = "";
  $("#modal-mask").classList.remove("hidden");
}
function closeModal() { animateHide($("#modal-mask")); }
async function doChangePassword(btn) {
  const nw = $("#pw-new").value, nw2 = $("#pw-new2").value;
  $("#pw-err").innerHTML = "";
  if (nw !== nw2) { $("#pw-err").innerHTML = `<div class="hint warn">${icon("alert", 15)}<span>两次输入的新密码不一致</span></div>`; return; }
  const old = btn.textContent; btn.disabled = true; btn.textContent = "保存中…";
  try {
    await api("/api/auth/password", { old_password: $("#pw-old").value, new_password: nw });
    closeModal(); toast("密码已修改,业务接口已开放");
    loadHealth();  // 刷新 default_credentials 状态(登录页提示随之消失)
  } catch (e) {
    $("#pw-err").innerHTML = `<div class="hint warn">${icon("alert", 15)}<span>${esc(e.message)}</span></div>`;
  } finally { btn.disabled = false; btn.textContent = old; }
}
$("#modal-mask").addEventListener("click", e => { if (e.target === $("#modal-mask")) closeModal(); });
$("#confirm-mask").addEventListener("click", e => { if (e.target === $("#confirm-mask")) settleConfirm(false); });
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && !$("#confirm-mask").classList.contains("hidden")) settleConfirm(false);
  else if (e.key === "Escape" && !$("#modal-mask").classList.contains("hidden")) closeModal();
});
/* ============ 健康检查 ============ */
let _healthFails = 0;
async function loadHealth(silent = false) {
  try {
    const [h, llm] = await Promise.all([
      api("/api/health", null, "GET", true), api("/api/llm/status", null, "GET", true).catch(() => null)]);
    _healthFails = 0;
    $("#side-ver").textContent = "v" + (h.app_version || "1.5.0");
    $("#side-llm").textContent = llm ? (llm.configured ? `LLM:${llm.model}` : "LLM:Mock") : "LLM:—";
    $("#health-dot").classList.remove("off");
    $("#health-text").textContent = `服务在线 · ${h.case_count} cases`;
    $("#health-chip").innerHTML = `${icon("database", 13)} ${h.case_count} cases · ${h.report_count} 报告`;
    $("#auth-chip").innerHTML = h.auth_mode === "open"
      ? `${icon("unlock", 13)} 演示模式` : `${icon("lock", 13)} 登录模式`;
    $("#login-hint").style.display = h.default_credentials ? "block" : "none";
    const ws = $("#welcome-stats");
    if (ws && !silent) {   // 心跳静默模式不重绘欢迎页数字,避免计数动画周期性重播
      ws.innerHTML = `
      <div class="hstat"><b>${icon("database", 18)}<span class="num" data-countup="${h.case_count}">0</span></b>replaycase 用例</div>
      <div class="hstat"><b>${icon("filetext", 18)}<span class="num" data-countup="${h.report_count}">0</span></b>评测报告归档</div>
      <div class="hstat"><b>${icon("branch", 18)}<span class="num" data-countup="${h.versions.length}">0</span></b>管线版本</div>`;
      runCountUps(ws);   // 首屏数字滚动,与级联入场同步
    }
  } catch {
    _healthFails++;
    if (_healthFails >= 2) {   // 连续两次失败才判离线:心跳对瞬时抖动容错
      $("#health-dot").classList.add("off");
      $("#health-text").textContent = "服务离线";
    }
  }
}
/* 健康心跳:工作台可见期间每 30s 静默刷新;后台页签跳过,回到前台立即补一次 */
setInterval(() => {
  if (!document.hidden && views.app && !views.app.classList.contains("hidden")) loadHealth(true);
}, 30000);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && views.app && !views.app.classList.contains("hidden")) loadHealth(true);
});
/* ============ 命令面板(Ctrl/⌘+K) ============ */
let cmdkItems = [], cmdkSel = 0, cmdkReports = [];

async function cmdkActions() {
  const nav = [
    ["dashboard", "评测看板", "dashboard", "页面"],
    ["cases", "Case 管理", "database", "页面"],
    ["compare", "版本对比", "scale", "页面"],
    ["analyze", "分析提交", "flask", "页面"],
    ["settings", "设置", "settings", "页面"],
  ].map(([tab, name, ico, cat]) => ({
    ico, label: name, cat,
    run: () => { if (views.app.classList.contains("hidden")) enterApp().then(() => switchTab(tab)); else switchTab(tab); },
  }));
  nav.push({ ico: "spark", label: "智能助手", cat: "页面",
    run: () => { if (views.app.classList.contains("hidden")) enterApp().then(() => setAiOpen(true)); else setAiOpen(true); } });
  const cmds = [
    { ico: "cycle", label: "运行完整自进化循环", cat: "命令",
      run: () => { switchTab("dashboard");
        whenReady(() => [...$$("#tab-dashboard button")].find(x => x.textContent.includes("运行完整自进化循环")),
          b => runEvolve(b)); } },
    { ico: "play", label: "回放最近一次自进化", cat: "命令",
      run: async () => {
        if (views.app.classList.contains("hidden")) await enterApp();
        const evos = await api("/api/evolutions").catch(() => []);
        if (!evos.length) { toast("还没有进化记录 —— 先运行一次完整自进化", true); return; }
        replayEvolution(evos[0].evolution_id);
      } },
    { ico: "database", label: "导出全部 case JSON", cat: "命令",
      run: async () => {
        const all = await api("/api/cases").catch(() => []);
        if (!all.length) { toast("case 库为空,无可导出", true); return; }
        downloadJson(`replaycases_${new Date().toISOString().slice(0, 10)}.json`, all);
        toast(`已导出 ${all.length} 条 case`);
      } },
    { ico: "panelLeft", label: "展开 / 收起任务区", cat: "命令", run: () => setTaskCollapsed() },
    { ico: "chevR", label: "展开 / 收起侧栏", cat: "命令", run: () => setSideCollapsed() },
    { ico: "sun", label: "切换明暗主题", cat: "命令",
      run: () => toggleTheme() },   // 无坐标:自然回退 340ms 颜色过渡,不走揭示
    { ico: "book", label: "打开文档中心", cat: "命令", run: () => window.open("/help", "_blank") },
    { ico: "logout", label: "退出登录", cat: "命令", run: () => doLogout() },
  ];
  const reports = await api("/api/reports").catch(() => []);
  cmdkReports = reports;
  const repItems = reports.slice(0, 12).map(r => ({
    ico: "filetext", label: `${r.report_id}(${r.version} ${pct(r.accuracy)})`, cat: "报告",
    run: () => {
      if (views.app.classList.contains("hidden")) enterApp();
      setTimeout(() => showReport(r.report_id), 250);  // 直接开抽屉,无需切 Tab
    },
  }));
  return [...nav, ...cmds, ...repItems];
}

function renderCmdk(q = "") {
  const kw = q.trim().toLowerCase();
  cmdkItems = cmdkAll.filter(it => !kw
    || it.label.toLowerCase().includes(kw) || it.cat.toLowerCase().includes(kw));
  cmdkSel = 0;
  $("#cmdk-list").innerHTML = cmdkItems.length ? cmdkItems.map((it, i) => `
    <div class="cmdk-item ${i === cmdkSel ? "sel" : ""}" data-i="${i}" onclick="runCmdkItem(${i})">
      <span class="ck-ico">${icon(it.ico, 14)}</span>${esc(it.label)}<small>${esc(it.cat)}</small>
    </div>`).join("") : `<div class="cmdk-empty">没有匹配项</div>`;
}
function runCmdkItem(i) {
  const it = cmdkItems[i];
  if (!it) return;
  cmdkItems = []; cmdkAll = [];   // 一次性消费,防重入
  closeCmdk();
  try { it.run(); } catch (e) { toast(e.message || String(e), true); }
}
let cmdkAll = [];
async function openCmdk() {
  if (cmdkAll.length === 0) cmdkAll = await cmdkActions();
  $("#cmdk-mask").classList.remove("hidden");
  const input = $("#cmdk-input");
  input.value = ""; renderCmdk();
  setTimeout(() => input.focus(), 30);
}
function closeCmdk() { animateHide($("#cmdk-mask")); }
$("#cmdk-mask").addEventListener("click", e => { if (e.target === $("#cmdk-mask")) closeCmdk(); });
$("#cmdk-input").addEventListener("input", e => renderCmdk(e.target.value));
$("#cmdk-input").addEventListener("keydown", e => {
  if (e.key === "ArrowDown") { e.preventDefault(); cmdkSel = Math.min(cmdkSel + 1, cmdkItems.length - 1); }
  else if (e.key === "ArrowUp") { e.preventDefault(); cmdkSel = Math.max(cmdkSel - 1, 0); }
  else if (e.key === "Enter") {
    e.preventDefault();
    const el = $$("#cmdk-list .cmdk-item")[cmdkSel];
    if (el) runCmdkItem(parseInt(el.dataset.i, 10));
    return;
  }
  else return;
  $$("#cmdk-list .cmdk-item").forEach((el, i) => el.classList.toggle("sel", i === cmdkSel));
  $$("#cmdk-list .cmdk-item")[cmdkSel]?.scrollIntoView({ block: "nearest" });
});
/* ============ 点击空白:轨道环节点 ============ */
/* 空白处点击点亮一颗「路网节点」:中心弹现 + 双椭圆轨道环错峰扩散。
   排除边界/同屏上限/三重生命周期保障与涟漪版一致,仅换皮 */
document.addEventListener("pointerdown", e => {
  if (REDUCED || e.button !== 0) return;
  if (document.querySelectorAll(".click-node").length >= 6) return;
  const t = e.target;
  if (!(t instanceof Element)) return;
  if (t.closest("button, a, input, select, textarea, label, summary, [onclick], [role='button'],"
    + ".nav-item, .tp-item, .entry-card, .chip2, .step, .cmdk-item, .row-sel, .diff-toggle,"
    + "table, tr, .chart-wrap, .toast, .modal, .drawer, .sheet, .cmdk")) return;
  // 兜底清扫:后台页签定时器被节流时,animationend/超时都可能迟到 —— 新点击时按时间戳清扫残影
  document.querySelectorAll(".click-node").forEach(el => {
    if (performance.now() - (el._t0 || 0) > 780) el.remove();
  });
  const r = document.createElement("span");
  r.className = "click-node";
  r._t0 = performance.now();
  r.style.left = e.clientX + "px";
  r.style.top = e.clientY + "px";
  r.innerHTML = '<span class="cn-dot"></span><span class="cn-ring"></span><span class="cn-ring r2"></span>';
  document.body.appendChild(r);
  r.addEventListener("animationend", () => r.remove(), { once: true });
  setTimeout(() => r.remove(), 820);   // 兜底:动画被全局规则停用等极端情况下也不残留
}, { passive: true });
/* ============ 卡片「探照灯」跟随悬停 ============ */
/* document 级单一 pointermove 委托 + rAF 节流:把光斑坐标(卡片局部系)写进最近 .card/.vcard
   的 --mx/--my,渐变与淡入淡出全在 CSS(app.css 探照灯块)。REDUCED 载入快照为真不注册;
   触屏由 @media (hover:none) 整组不渲染;无 JS 时仅损失光斑,底色 hover 与带色阴影不受影响 */
if (!REDUCED) {
  let spotRaf = 0, spotCard = null, spotX = 0, spotY = 0;
  document.addEventListener("pointermove", (e) => {
    spotCard = e.target.closest ? e.target.closest(".card, .vcard") : null;
    if (!spotCard) return;
    spotX = e.clientX; spotY = e.clientY;
    if (spotRaf) return;
    spotRaf = requestAnimationFrame(() => {
      spotRaf = 0;
      const r = spotCard.getBoundingClientRect();
      spotCard.style.setProperty("--mx", `${Math.round(spotX - r.left)}px`);
      spotCard.style.setProperty("--my", `${Math.round(spotY - r.top)}px`);
    });
  }, { passive: true });
}
/* ============ 导航 ============ */
const TITLES = {
  dashboard: ["评测看板", "评测驱动迭代:基线 → 最多 2 轮 → 验证无回归 → 归档报告"],
  cases: ["Case 管理", "闭环第 1-2 步:把线上反馈沉淀为可重放的评测用例"],
  compare: ["版本对比", "闭环第 6 步:守护每一次迭代不引入回归"],
  analyze: ["分析提交", "用任意版本的管线分析任意数据集"],
  settings: ["设置", "运行时配置托管:看板直接读写服务器 .env,热生效项免重启"],
};
// 图标注入(HTML 里用 data-ico 占位,避免重复书写长 SVG)
$$("[data-ico]").forEach(el => { el.innerHTML = icon(el.dataset.ico, el.dataset.icoSize || 18); });
document.querySelector(".nav-scroll").addEventListener("click", e => {
  const btn = e.target.closest("button[data-tab]");
  if (btn) switchTab(btn.dataset.tab);
});
// AI 右栏侧轨:任何页面都可展开 / 收起智能助手
$("#ai-rail").addEventListener("click", () => setAiOpen());
/* ============ 面板宽度拖拽(导航 / 任务区 / AI 面板,宽度记忆于 localStorage) ============ */
const PANE_DEFS = {
  side: { min: 64, max: 280, base: 248, delta: 1 },     // 拖左收窄至图标轨;拖右至 280 恰好容下完整内容
  task: { min: 208, max: 400, base: 272, delta: 1 },
  ai:   { min: 300, max: 560, base: 396, delta: -1 },   // 面板在右侧:拖左加宽
};
const PANE_STORE = "harness_pane_w";
const WORKSPACE_MIN = 560;   // 中栏工作区保底宽度;再窄由容器查询转为纵向堆叠
const FIXED_CHROME = 51;     // 三个拖拽柄 15px + AI 侧轨 36px,不随拖拽变化

function panePx(name) {
  // 宽度真值源 = CSS 变量;不读 getBoundingClientRect,避免展开动画未结束时取到中间值
  const v = parseFloat(document.documentElement.style.getPropertyValue(`--pane-${name}`));
  return Number.isNaN(v) ? PANE_DEFS[name].base : v;
}
function setPaneWidth(name, px, persist = true) {
  const def = PANE_DEFS[name];
  const aiOpen = $("#aipanel").classList.contains("open");
  const others = Object.keys(PANE_DEFS)
    .filter(n => n !== name && (n !== "ai" || aiOpen))
    .reduce((sum, n) => sum + panePx(n), 0);
  const max = Math.min(def.max, innerWidth - others - WORKSPACE_MIN - FIXED_CHROME);
  const w = Math.round(Math.min(Math.max(px, def.min), Math.max(def.min, max)));
  document.documentElement.style.setProperty(`--pane-${name}`, w + "px");
  if (persist) {
    const all = paneWidths(); all[name] = w;
    try { localStorage.setItem(PANE_STORE, JSON.stringify(all)); } catch {}
  }
}
function paneWidths() {
  try { return JSON.parse(localStorage.getItem(PANE_STORE)) || {}; } catch { return {}; }
}
(function initPaneResize() {
  const saved = paneWidths();
  for (const name of Object.keys(PANE_DEFS)) {
    if (typeof saved[name] === "number") setPaneWidth(name, saved[name], false);
  }
  $$(".pane-resizer").forEach(handle => {
    const name = handle.dataset.resize;
    let startX = 0, startW = 0;
    handle.addEventListener("pointerdown", e => {
      if (name === "ai" && !$("#aipanel").classList.contains("open")) return;
      startX = e.clientX;
      startW = panePx(name);
      try { handle.setPointerCapture(e.pointerId); } catch {}  // 某些合成/触控环境会抛,不阻塞拖拽
      handle.classList.add("dragging");
      document.body.classList.add("col-resizing");
    });
    handle.addEventListener("pointermove", e => {
      if (!handle.classList.contains("dragging")) return;
      setPaneWidth(name, startW + (e.clientX - startX) * PANE_DEFS[name].delta);
    });
    const stop = () => {
      handle.classList.remove("dragging");
      document.body.classList.remove("col-resizing");
    };
    handle.addEventListener("pointerup", stop);
    handle.addEventListener("pointercancel", stop);
    handle.addEventListener("dblclick", () => {   // 双击恢复默认宽度
      const all = paneWidths(); delete all[name];
      try { localStorage.setItem(PANE_STORE, JSON.stringify(all)); } catch {}
      document.documentElement.style.removeProperty(`--pane-${name}`);
    });
  });
  // 窗口缩放后重新钳制:面板按已存宽度收敛,工作区不会被挤到显示不全
  let resizeRaf = 0;
  window.addEventListener("resize", () => {
    cancelAnimationFrame(resizeRaf);
    resizeRaf = requestAnimationFrame(() => {
      const saved = paneWidths();
      for (const name of Object.keys(PANE_DEFS)) {
        if (typeof saved[name] === "number") setPaneWidth(name, saved[name], false);
      }
    });
  });
})();
// 登录框回车提交
$("#view-login").addEventListener("keydown", e => {
  if (e.key === "Enter" && document.activeElement && document.activeElement.tagName === "INPUT") {
    const btn = $("#view-login .btn"); if (btn && !btn.disabled) doLogin(btn);
  }
});
// 长页面回到顶部;顶栏离开顶部后落影,增强滚动层次
const scrollArea = $("#scroll-area");
$("#back-top").addEventListener("click", () => scrollArea.scrollTo({ top: 0, behavior: "smooth" }));
scrollArea.addEventListener("scroll", () => {
  $("#back-top").classList.toggle("show", scrollArea.scrollTop > 420);
  $(".topbar").classList.toggle("scrolled", scrollArea.scrollTop > 8);
}, { passive: true });
/* 控制台小彩蛋:给看控制台的工程师一句话 */
try { console.log(
  "%c Transportation Harness %c 评测驱动 / 回归守护 / 持续进化 ",
  "background:#4f46e5;color:#fff;padding:3px 8px;border-radius:4px 0 0 4px;font:700 12px/1.7 'Segoe UI',sans-serif",
  "background:#eef1ff;color:#4338ca;padding:3px 8px;border-radius:0 4px 4px 0;font:600 12px/1.7 'Segoe UI',sans-serif",
  "\nCtrl/\u2318+K 命令面板 \u00b7 Web / \u5c0f\u7a0b\u5e8f / CLI 三端同一套 API \u00b7 \u4e00\u5207\u7686 JSON",
); } catch (e) {}
/* ============ PWA:Service Worker / 安装 / 离线提示 ============ */
// beforeinstallprompt 可能在脚本执行早期触发,监听需最先挂上
let _pwaInstallEvent = null;
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  _pwaInstallEvent = e;
  const btn = $("#pwa-install");
  if (btn) btn.style.display = "";
});
window.addEventListener("appinstalled", () => {
  const btn = $("#pwa-install");
  if (btn) btn.style.display = "none";
  toast("已安装到设备,可从桌面 / 主屏幕打开");
});
(function setupPwa() {
  const btn = $("#pwa-install");
  if (btn) btn.addEventListener("click", async () => {
    if (!_pwaInstallEvent) return;
    _pwaInstallEvent.prompt();
    const choice = await _pwaInstallEvent.userChoice;
    if (choice.outcome === "accepted") btn.style.display = "none";
    _pwaInstallEvent = null;
  });
  if (!("serviceWorker" in navigator)) return;
  if (!window.isSecureContext) {
    // 公网 http IP 属非安全上下文:浏览器禁用 SW,优雅降级,功能不受影响
    console.info("[PWA] 非安全上下文(需 localhost / HTTPS),Service Worker 未注册。");
    return;
  }
  window.addEventListener("load", async () => {
    try {
      const reg = await navigator.serviceWorker.register("/sw.js");
      reg.addEventListener("updatefound", () => {
        const sw = reg.installing;
        if (!sw) return;
        sw.addEventListener("statechange", () => {
          if (sw.state === "installed" && navigator.serviceWorker.controller) {
            toast("新版本已就绪,刷新页面即可生效");
          }
        });
      });
    } catch (err) {
      console.info("[PWA] Service Worker 注册失败(不影响使用):", err);
    }
  });
  window.addEventListener("offline", () => toast("网络已断开,展示的是离线缓存数据", true));
  window.addEventListener("online", () => toast("网络已恢复"));
})();
boot();
