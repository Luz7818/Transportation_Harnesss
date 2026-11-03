/* Transportation Harness · 看板应用脚本(manage · 资产与辅助)
   无构建拆分(TH-04 第二批):经典脚本共享全局作用域,加载顺序 app-core -> app-board -> app-manage。
   本文件职责:Case 管理/设置/AI 助手右栏/页签接线与启动 */
"use strict";
/* ============ Case 管理 ============ */
let caseFilter = "全部";
const caseSel = new Set();   // 批量操作选中的 case_id
/* ---- Case 页:任务区(case 列表,左)+ 工作区(详情 / 沉淀表单,中) ---- */
let caseWsMode = "form";      // form = 沉淀表单,detail = 选中 case 的详情
let selectedCaseId = null;
let caseSearch = "";

async function renderCases() {
  const [cases, datasets] = await Promise.all([api("/api/cases"), api("/api/datasets")]);
  window.__casesCache = cases;
  window.__caseDatasets = datasets;
  renderCaseTaskPanel(cases);
  renderCaseWorkspace(cases);
}
function renderCaseTaskPanel(cases) {
  const labels = ["全部", ...new Set(cases.map(c => c.label))];
  if (!labels.includes(caseFilter)) caseFilter = "全部";
  $("#tp-head-slot").innerHTML = `
    <div class="tp-head"><b>${icon("database", 14)} Case 库</b>
      <span class="chip2 plain num">${cases.length}</span>
      <button class="btn sm ${caseWsMode === "form" ? "" : "secondary"}" onclick="caseWsNew()">${icon("plus", 13)} 沉淀</button>
      <button class="icon-btn" style="width:24px;height:24px;flex:none" onclick="setTaskCollapsed(true)" title="收起任务区" aria-label="收起任务区">‹</button></div>`;
  $("#tp-list").innerHTML = `
    <div class="tp-tools"><div class="chips">${labels.map(l =>
      `<span class="chip2 ${l === caseFilter ? "" : "plain"} click" onclick="setFilter('${esc(l)}')">${esc(l)}</span>`).join("")}</div></div>
    <div class="tp-search"><input id="case-search" value="${esc(caseSearch)}" autocomplete="off"
      placeholder="搜索 case / 标题 / 标签…" oninput="setCaseSearch(this.value)"></div>
    <div id="tp-items"></div>`;
  renderCaseItems(cases);
  $("#tp-foot").style.display = "";
  $("#tp-foot").textContent = "cases/ 按失败标签分目录,一个 case 一个 JSON 文件,可直接纳入 git 管理。";
}
/* 搜索键入只重绘条目区,不重建输入框:焦点与输入法组合态不丢 */
function renderCaseItems(cases) {
  const box = $("#tp-items");
  if (!box) return;
  const kw = caseSearch.trim().toLowerCase();
  const shown = cases.filter(c => (caseFilter === "全部" || c.label === caseFilter)
    && (!kw || c.case_id.toLowerCase().includes(kw) || c.title.toLowerCase().includes(kw)
      || c.label.toLowerCase().includes(kw) || (c.dataset_name || "").toLowerCase().includes(kw)));
  box.innerHTML = shown.length ? shown.map(c => {
    const lv = (c.checks || []).find(k => k.type === "classify");
    return `<div class="tp-item ${selectedCaseId === c.case_id ? "sel" : ""}" onclick="selectCase('${esc(c.case_id)}')">
      <div class="ti-top"><span class="ti-id">${esc(c.case_id)}</span>
        <span class="ti-title" title="${esc(c.title)}">${esc(c.title)}</span></div>
      <div class="ti-meta">${lv && lv.expected ? lvPill(lv.expected) : ""}<span>${esc(c.label)}</span>
        <span style="opacity:.5">·</span>
        <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(c.dataset_name)}</span>
        <input type="checkbox" class="row-sel" title="加入批量选择" ${caseSel.has(c.case_id) ? "checked" : ""}
          onclick="event.stopPropagation()" onchange="toggleSel('${esc(c.case_id)}', this.checked)"></div>
    </div>`; }).join("")
    : `<div class="tp-empty">${kw ? `没有匹配「${esc(caseSearch.trim())}」的 case` : "该标签下暂无 case<br>切换标签,或点上方「沉淀」新建"}</div>`;
}
function setCaseSearch(v) { caseSearch = v; renderCaseItems(window.__casesCache || []); }
function selectCase(id) {
  caseWsMode = "detail"; selectedCaseId = id;
  renderCaseTaskPanel(window.__casesCache || []);
  renderCaseWorkspace(window.__casesCache || []);
}
function caseWsNew() {
  caseWsMode = "form"; selectedCaseId = null;
  renderCaseTaskPanel(window.__casesCache || []);
  renderCaseWorkspace(window.__casesCache || []);
}
function setFilter(label) { caseFilter = label; renderCaseTaskPanel(window.__casesCache || []); }
function refreshCasesIfVisible() {
  if (!views.app.classList.contains("hidden") && $("#tab-cases").classList.contains("active")) renderCases();
}

function renderCaseWorkspace(cases) {
  if (caseWsMode === "detail" && selectedCaseId) {
    const c = cases.find(x => x.case_id === selectedCaseId);
    if (c) { renderCaseDetail(c); return; }
    caseWsMode = "form"; selectedCaseId = null;  // case 已被删除等:回退到沉淀表单
    renderCaseTaskPanel(cases);
  }
  renderCaseForm();
}
function renderCaseForm() {
  const datasets = window.__caseDatasets || [];
  const labels = [...new Set((window.__casesCache || []).map(c => c.label))];
  $("#tab-cases").innerHTML = `
    <div id="case-batch"></div>
    <div class="card">
      <h3><span class="h-ico">${icon("plus", 16)}</span>沉淀新的 replaycase</h3>
      <p class="desc">闭环第 1-2 步:把线上反馈转化为可重放的评测用例 —— 输入 + 期望结论 + 判分规则,保存后自动加入当前评测集。</p>
      <div class="row3">
        <div><label>标题</label><input id="c-title" maxlength="80" placeholder="例:学府路应判为拥堵而非严重拥堵"></div>
        <div><label>失败标签</label><input id="c-label" list="label-list" maxlength="20" placeholder="选择或输入新标签">
          <datalist id="label-list">${labels.map(l => `<option value="${esc(l)}">`).join("")}</datalist></div>
        <div><label>数据集</label><select id="c-dataset" onchange="onFormDatasetChange()">
          ${datasets.map(d => `<option value="${esc(d.name)}">${esc(d.name)}</option>`).join("")}</select></div>
      </div>
      <div class="row3">
        <div><label>路段</label><select id="c-segment" onchange="onFormSegmentChange()"></select></div>
        <div><label>期望拥堵等级</label><select id="c-level">${LEVELS.map(l => `<option>${l}</option>`).join("")}</select></div>
        <div><label>期望饱和度(可选)</label><input id="c-sat" type="number" step="0.01" min="0" max="3" placeholder="留空则只校验等级"></div>
      </div>
      <label>备注(反馈原文 / 复现步骤)</label>
      <input id="c-notes" maxlength="200" placeholder="例:用户点踩,该路段 V/C 已超 0.9…">
      <div id="c-ref"></div>
      <div id="c-err"></div>
      <p style="margin:16px 0 0"><button class="btn" onclick="createCase(this)">${icon("database", 15)} 沉淀为 replaycase 并加入评测集</button></p>
    </div>`;
  renderBatchBar();
  onFormDatasetChange();
}
function renderCaseDetail(c) {
  const checks = c.checks || [];
  const lv = checks.find(k => k.type === "classify");
  const rows = checks.map(k => {
    const target = k.segment || k.field
      || (k.type === "no_crash" || k.type.startsWith("conclusion") ? "summary" : "—");
    const expect = k.type === "conclusion_keyword" ? (k.keywords || []).join(" / ")
      : k.type === "conclusion_quality" ? `≥ ${k.min_score}` : (k.expected ?? "—");
    return `<tr><td class="num">${esc(k.type)}</td><td>${esc(target)}</td>
      <td>${esc(String(expect))}</td><td class="muted">${k.tol ? `容差 ±${k.tol}` : ""}</td></tr>`;
  }).join("");
  $("#tab-cases").innerHTML = `
    <div id="case-batch"></div>
    <div class="card">
      <h3><span class="h-ico">${icon("database", 16)}</span>${esc(c.title)}
        <span class="chip2 plain num" style="margin-left:4px">${esc(c.case_id)}</span></h3>
      <p class="desc">标签 ${esc(c.label)} · 来源:${esc(c.source)} · 沉淀于 ${esc(c.created_at || "—")}</p>
      <div class="chips">
        ${lv && lv.expected ? lvPill(lv.expected) : ""}
        <span class="chip2 plain">数据集:${esc(c.dataset_name)}</span>
        <span class="chip2 plain num">${checks.length} 条判分规则</span>
      </div>
      ${c.notes ? `<div class="hint">${icon("bulb", 15)}<span>${esc(c.notes)}</span></div>` : ""}
      <p style="margin:14px 0 6px;font-weight:700;font-size:13px">判分规则</p>
      <div class="table-wrap"><table>
        <thead><tr><th>类型</th><th>目标</th><th>期望</th><th>说明</th></tr></thead>
        <tbody>${rows || `<tr><td colspan="4" class="muted">无</td></tr>`}</tbody></table></div>
      <p style="display:flex;gap:10px;margin:16px 0 0;flex-wrap:wrap">
        <button class="btn secondary" onclick="caseWsNew()">${icon("plus", 14)} 再沉淀一条</button>
        <button class="btn secondary" onclick="copyCaseJson()" title="把该 case 的完整 JSON 复制到剪贴板">${icon("filetext", 14)} 复制 JSON</button>
        <button class="btn danger" onclick="deleteCase('${esc(c.case_id)}')">${icon("trash", 14)} 删除该 case</button>
      </p>
    </div>`;
  renderBatchBar();
}
async function copyCaseJson() {
  const c = (window.__casesCache || []).find(x => x.case_id === selectedCaseId);
  if (!c) return;
  const ok = await copyText(JSON.stringify(c, null, 2));
  toast(ok ? `已复制 ${c.case_id} 的完整 JSON` : "复制失败:浏览器限制了剪贴板访问", !ok);
}


/* ---- Case 批量操作 ---- */
function toggleSel(id, on) { on ? caseSel.add(id) : caseSel.delete(id); renderBatchBar(); }
function renderBatchBar() {
  const box = $("#case-batch");
  if (!box) return;
  const had = !!box.firstElementChild, want = caseSel.size > 0;
  box.innerHTML = want ? `
    <div class="batch-bar">
      <span>已选 <b class="num">${caseSel.size}</b> 条</span>
      <button class="btn sm secondary" onclick="exportSelected()">${icon("filetext", 13)} 导出 JSON</button>
      <button class="btn sm danger" onclick="batchDelete()">${icon("trash", 13)} 删除所选</button>
      <span class="spacer"></span>
      <button class="linklike" onclick="caseSel.clear();renderCases()">取消选择</button>
    </div>` : "";
  if (want && !had) box.firstElementChild.classList.add("pop-rise");   // 仅首次出现浮起,勾选更新不重播
}
async function batchDelete() {
  const ids = [...caseSel];
  if (!ids.length) return;
  if (!await askConfirm(`删除所选 ${ids.length} 条 case?`,
    "将同时从所有评测集清单移除,已归档报告不受影响。")) return;
  try {
    const out = await api("/api/cases/batch-delete", { ids });
    toast(`已删除 ${out.deleted.length} 条${out.missing.length ? `,${out.missing.length} 条不存在` : ""}`);
    caseSel.clear();
    await renderCases(); loadHealth();
  } catch (e) { toast(e.message, true); }
}
function exportSelected() {
  const picked = (window.__casesCache || []).filter(c => caseSel.has(c.case_id));
  if (!picked.length) return;
  downloadJson(`replaycases_${new Date().toISOString().slice(0, 10)}.json`, picked);
  toast(`已导出 ${picked.length} 条 case`);
}

async function onFormDatasetChange() {
  const ds = $("#c-dataset").value;
  const { segments } = await api("/api/segments/" + ds);
  $("#c-segment").innerHTML = segments.map(s =>
    `<option value="${esc(s.segment_id)}">${esc(s.segment_id)} · ${esc(s.name)}</option>`).join("");
  onFormSegmentChange();
}
async function onFormSegmentChange() {
  const ds = $("#c-dataset").value, seg = $("#c-segment").value;
  if (!seg) { $("#c-ref").innerHTML = ""; return; }
  try {
    const out = await api("/api/analyze", { version: "v2", dataset_name: ds });
    const row = out.segments.find(r => r.segment_id === seg);
    if (!row) { $("#c-ref").innerHTML = ""; return; }
    const sat = row.saturation === null || row.saturation === undefined ? "—" : row.saturation;
    $("#c-ref").innerHTML = `<div class="hint">${icon("bulb", 15)}<span>参考:当前 v2 对 ${esc(seg)} 的判定为 ${lvPill(row.classification)}
      ,饱和度 <b class="num">${sat}</b>
      <button class="btn sm secondary" style="height:24px;padding:0 10px;font-size:11.5px" onclick="adoptRef('${esc(row.classification)}', ${row.saturation ?? "null"})">沿用该判定</button>
      (也可按人工结论修改)</span></div>`;
  } catch { $("#c-ref").innerHTML = ""; }
}
/* 一键把参考判定填进期望等级/期望饱和度,减少重复键入 */
function adoptRef(level, sat) {
  const lv = $("#c-level");
  if (lv && [...lv.options].some(o => o.value === level)) lv.value = level;
  if (sat !== null && sat !== undefined) {
    const satEl = $("#c-sat");
    if (satEl) satEl.value = sat;
  }
  toast(`已沿用参考判定:${level}${sat !== null && sat !== undefined ? ` · 饱和度 ${sat}` : ""}`);
}
/* 校验失败标记:边框标红 + 摇晃;任意输入即摘除标记 */
function flagInvalid(el) {
  if (!el) return;
  el.classList.add("invalid");
  el.classList.remove("shake"); void el.offsetWidth; el.classList.add("shake");
}
document.addEventListener("input", e => { if (e.target.classList) e.target.classList.remove("invalid"); });

async function createCase(btn) {
  const title = $("#c-title").value.trim(), seg = $("#c-segment").value;
  const missing = [];
  if (!title) { flagInvalid($("#c-title")); missing.push("标题"); }
  if (!seg) { flagInvalid($("#c-segment")); missing.push("路段"); }
  if (missing.length) {
    $("#c-err").innerHTML = `<div class="hint warn">${icon("alert", 15)}<span>请先补全:${missing.join("、")} —— 用例没有输入就无法重放。</span></div>`;
    return;
  }
  $("#c-err").innerHTML = "";
  await withBusy(btn, async () => {
    const body = {
      title, label: $("#c-label").value || "未分类",
      dataset_name: $("#c-dataset").value,
      segment: seg,
      expected_level: $("#c-level").value,
      expected_saturation: $("#c-sat").value === "" ? null : parseFloat($("#c-sat").value),
      notes: $("#c-notes").value,
    };
    const out = await api("/api/cases", body);
    toast(`已沉淀 ${out.case.case_id}${out.added_to_evalset ? " 并加入评测集" : ""}`);
    await renderCases(); loadHealth();
  });
}
async function deleteCase(caseId) {
  if (!await askConfirm(`删除 ${caseId}?`,
    "该 case 会同时从所有评测集清单中移除,已归档的报告不受影响。")) return;
  try {
    await api("/api/cases/" + encodeURIComponent(caseId), null, "DELETE");
    toast(`已删除 ${caseId}`);
    await renderCases(); loadHealth();
  } catch (e) { toast(e.message, true); }
}
/* ============ 设置(运行时配置托管 /api/settings) ============ */
/* 界面完全由服务端 snapshot() 的字段驱动,不做任何本地推断:
   快照: { env_file, env_file_exists, secrets_masked, hot_reloaded[], requires_restart[],
            restart_pending_keys[], note }
   每项: { key, set, value, secret, restart_required, source, default, example, description }
   —— secret 项的 value 由服务端掩码(前 2 字符***(长度)),前端永远拿不到明文,故输入框不回填。
   保存响应: { ok, updated[], removed[], hot_reloaded[], requires_restart[], snapshot }
   —— 「已热生效 / 需重启」只按响应里的分区判定,不在前端硬编码哪些键热生效。 */
let settingsSnap = null;

const SOURCE_LABEL = { env: "进程环境变量", file: ".env 文件", default: "内置默认值" };
const settingItems = snap => [...(snap.hot_reloaded || []), ...(snap.requires_restart || [])];

function statusBadge(e) {
  if (e.source === "env" || e.source === "file")
    return `<span class="tag ok">${icon("check", 12)}已配置 · ${SOURCE_LABEL[e.source]}</span>`;
  if (e.set)
    return `<span class="tag">${icon("layers", 12)}未显式配置 · 取内置默认值</span>`;
  return `<span class="tag warn">${icon("alert", 12)}未配置 · 该项能力自动降级</span>`;
}
function applyBadge(e) {
  return e.restart_required
    ? `<span class="st-warn">${icon("clock", 11)}保存后需重启</span>`
    : `<span class="tag ok">${icon("cycle", 12)}保存即热生效</span>`;
}
function settingItemHtml(e) {
  const ph = e.secret ? "填入新值后保存(当前值只回掩码,不回填)" : "留空并保存即清除该项";
  const clearDisabled = e.source === "default" ? " disabled" : "";   // 文件与环境变量里都没有:无项可清
  return `
  <div class="st-item" id="st-${e.key}">
    <div class="st-top">
      <span class="st-key">${esc(e.key)}</span>${statusBadge(e)}${applyBadge(e)}
    </div>
    <p class="st-desc">${esc(e.description)}</p>
    <div class="st-meta">
      <span>${icon("gauge", 13)}当前值:<b class="st-mono">${e.set ? esc(e.value) : "—"}</b>
        ${e.secret && e.set ? `<span class="st-warn">密钥掩码</span>` : ""}</span>
      <span>${icon("shield", 13)}留空回落到:<b>${
        e.default ? `<span class="st-mono">${esc(e.default)}</span>` : "不启用该项,相关链路自动降级"}</b></span>
      ${e.example ? `<span>${icon("bulb", 13)}填写示例:<b class="st-mono">${esc(e.example)}</b></span>` : ""}
    </div>
    <div class="st-edit">
      <input id="in-${e.key}" type="${e.secret ? "password" : "text"}"
        autocomplete="${e.secret ? "new-password" : "off"}" spellcheck="false" placeholder="${ph}">
      <button class="btn sm" onclick="saveSetting('${e.key}', this)">保存</button>
      <button class="btn sm secondary" onclick="clearSetting('${e.key}', this)"${clearDisabled}
        title="从 .env 中删除该行并回落默认行为">清空</button>
    </div>
    <div class="st-err" id="err-${e.key}"></div>
  </div>`;
}
function settingsSummaryHtml(snap) {
  const items = settingItems(snap);
  const explicit = items.filter(e => e.source !== "default");
  const pending = snap.restart_pending_keys || [];
  const onDefault = items.filter(e => e.source === "default");
  const chips = [
    `<span class="chip2 ${explicit.length ? "good" : "plain"}">${icon("check", 12)} 已显式配置 ${explicit.length} / ${items.length} 项</span>`,
    `<span class="chip2 plain">${icon("cycle", 12)} 热生效 ${(snap.hot_reloaded || []).length} 项</span>`,
    `<span class="chip2 plain">${icon("clock", 12)} 需重启 ${(snap.requires_restart || []).length} 项</span>`,
    `<span class="chip2 plain num" title="${esc(snap.env_file || "")}">${icon("database", 12)} ${
      snap.env_file_exists ? esc(snap.env_file) : esc(snap.env_file) + "(尚不存在)"}</span>`,
  ].join("");
  const pendingHint = pending.length
    ? `<div class="hint warn">${icon("alert", 15)}<span><b>${pending.join(" / ")}</b> 已写入 <code>.env</code>,但当前进程仍在用旧值 ——
        重启服务(<code>python webapp/app.py</code> 或容器重启)后才会读到。本页只写文件,不能替正在跑的进程热替换这些键。</span></div>` : "";
  const defaultHint = onDefault.length
    ? `<div class="hint">${icon("bulb", 15)}<span><b>${onDefault.length} 项尚未显式配置</b>(
        ${onDefault.map(e => esc(e.key)).join(" / ")}),现在取的是内置默认值或保持降级状态。
        接入真实端点请按下面的「填写示例」逐项填入并保存 —— 不填也能正常演示。</span></div>` : "";
  return `
    <h3><span class="h-ico">${icon("shield", 16)}</span>配置就绪态</h3>
    <p class="desc">这一页托管服务器运行时配置(<code>.env</code>):改完即写盘,热生效项免重启。</p>
    <div class="chips">${chips}</div>
    <div class="hint ok">${icon("check", 15)}<span><b>所有配置项全部留空,系统依然可以完整离线演示。</b>
      评测闭环、多情景数据集、版本对比、报告归档都不依赖任何外部密钥;未配置 <code>LLM_API_KEY</code> 时,
      整条 LLM 链路自动降级为离线确定性 Mock(结果可复现、零成本)。这里的凭据只决定「智能层走真实模型还是走 Mock」。</span></div>
    ${pendingHint}${defaultHint}
    <p class="muted" style="margin:12px 0 0">${esc(snap.note || "")}</p>`;
}
function settingsDeniedCard(e) {
  const denied = e.status === 403;
  return `
  <div class="card">
    <h3><span class="h-ico">${icon("lock", 16)}</span>设置暂不可用</h3>
    <p class="desc">这一页直接读写服务器本地的 <code>.env</code>(含密钥),因此默认不开放。下面是接口返回的原文。</p>
    <div class="hint warn">${icon("alert", 15)}<span><b>${denied ? "服务端" : "错误"}:</b>${esc(e.message)}</span></div>
    ${denied ? `
    <div class="st-guide">
      <p><span class="g-ico">${icon("settings", 14)}</span><span><b>开关未开(最常见)</b>:在服务启动环境里设
        <code>SETTINGS_ENABLED=1</code> 后重启服务。该开关只在启动时读一次,所以无法通过本接口给自己开权限;
        把 <code>HOST</code> 绑到公网也不会顺带打开它。</span></p>
      <p><span class="g-ico">${icon("shield", 14)}</span><span><b>不被认作本机</b>:二选一 —— 在服务器本机的浏览器里打开看板
        (TCP 对端须是 127.0.0.1 / ::1 回环地址);或先登录,再携带会话凭据访问(网页靠 <code>harness_session</code> Cookie,
        脚本用 <code>Authorization: Bearer &lt;会话令牌&gt;</code>)。<code>X-API-Token</code> 是与小程序共用的机器令牌,
        不足以通过这道门;带 <code>X-Forwarded-For</code> 等转发头(经反向代理)的请求一律不算本机。</span></p>
      <p><span class="g-ico">${icon("book", 14)}</span><span>部署与申请方式见
        <a class="linklike" href="/help" target="_blank" rel="noopener">文档中心</a>(部署章节)。</span></p>
    </div>` : ""}
    <p style="margin:16px 0 0"><button class="btn sm secondary" onclick="renderSettings()">${icon("cycle", 14)} 重新读取</button></p>
  </div>`;
}
async function renderSettings() {
  const box = $("#tab-settings");
  box.innerHTML = `<div class="skeleton" style="height:112px"></div>
    <div class="skeleton" style="height:150px"></div><div class="skeleton" style="height:150px"></div>
    <div class="skeleton" style="height:150px"></div>`;
  let snap;
  try {
    snap = await api("/api/settings");
  } catch (e) {
    settingsSnap = null;
    box.innerHTML = settingsDeniedCard(e);
    return;
  }
  settingsSnap = snap;
  const groups = [
    ["hot_reloaded", "热生效项", "cycle", "保存后立即生效,无需重启(当前为 LLM 智能层相关配置)"],
    ["requires_restart", "启动期项", "clock", "只在服务启动时读取:已写入 .env,仍需重启进程才生效"],
  ];
  box.innerHTML = `
    <div class="card st-sum" id="st-summary"></div>
    <div class="card">
      <h3><span class="h-ico">${icon("settings", 16)}</span>配置项清单</h3>
      <p class="desc">按生效时机分两组;每一项的当前值、来源与回落行为都由服务端快照给出。</p>
      ${groups.map(([field, title, ico, sub]) => {
        const list = snap[field] || [];
        return `<div class="st-group">
          <div class="st-group-head">${icon(ico, 14)}${title}
            <span class="chip2 plain num">${list.length}</span>
            <span class="muted" style="font-weight:400">· ${sub}</span></div>
          ${list.length ? list.map(settingItemHtml).join("")
            : `<div class="muted" style="margin-top:8px">这一组没有配置项。</div>`}
        </div>`;
      }).join("")}
      <div class="st-group">
        <div class="st-group-head">${icon("bulb", 14)}去哪申请、怎么填</div>
        <p class="st-desc" style="margin-top:6px">
          <code>LLM_BASE_URL</code> / <code>LLM_API_KEY</code> / <code>LLM_MODEL</code> 取自你选定的模型服务商控制台
          (任意 OpenAI 兼容端点均可,填这三项即接入真实模型;不填则保持离线 Mock);
          <code>AUTH_TOKEN</code> 是给小程序 / 脚本共用的自建随机串,自行生成后两端填同一个值。
          接口没有下发「申请入口」字段,所以这里不放任何外链 —— 每一项的「填写示例」就是权威格式。
          部署与申请步骤见 <a class="linklike" href="/help" target="_blank" rel="noopener">文档中心</a>。
        </p>
      </div>
    </div>`;
  repaintSummary();
}
function repaintSummary() {
  const box = $("#st-summary");
  if (box && settingsSnap) box.innerHTML = settingsSummaryHtml(settingsSnap);
}
function repaintSetting(key) {
  const row = $(`#st-${key}`);
  const entry = settingsSnap && settingItems(settingsSnap).find(e => e.key === key);
  if (!row || !entry) { renderSettings(); return; }   // 快照里找不到该项:整页兜底重绘
  row.outerHTML = settingItemHtml(entry);
  const next = $(`#st-${key}`);
  if (!next) return;
  next.classList.add("flash");
  setTimeout(() => next.classList.remove("flash"), 1200);
}
function savedHint(key, out) {
  // 生效时机只看服务端返回的分区,前端不猜哪些键热生效
  const verb = (out.removed || []).includes(key) ? "已清除" : "已保存";
  if ((out.hot_reloaded || []).includes(key)) return `${key} ${verb} · 已热生效,无需重启`;
  if ((out.requires_restart || []).includes(key)) return `${key} ${verb} · 已写入 .env,需重启服务后生效`;
  return `${key} ${verb} · 服务端未标注生效时机,以本页重新读取的状态为准`;
}
/* 拒绝原因必须原样保留服务端 detail,再补一句怎么放开 —— 400 的校验原文同理 */
function writeErrorHtml(e) {
  const detail = esc(e.message);
  if (e.status !== 403) return detail;
  return `${detail}<br>写入被拒只有两种原因:① 服务启动环境未设 <code>SETTINGS_ENABLED=1</code>
    (设完须重启服务,该开关本身不能通过接口打开);② 请求既非服务器本机直连、也未携带已登录会话
    —— 在服务器本机打开看板,或登录后由浏览器自动带上 <code>harness_session</code> Cookie 即可。`;
}
async function putSetting(key, value, btn) {
  const errBox = $(`#err-${key}`);
  if (errBox) errBox.innerHTML = "";
  const old = btn.innerHTML;
  btn.disabled = true;
  let out;
  try {
    out = await api("/api/settings", { values: { [key]: value } }, "PUT");
  } catch (e) {
    if (errBox) errBox.innerHTML = writeErrorHtml(e);   // 输入框保留原文,便于改后重试
    else toast(e.message, true);
    return false;
  } finally {
    btn.disabled = false;
    btn.innerHTML = old;
  }
  if (!out || !out.snapshot) return false;
  settingsSnap = out.snapshot;
  repaintSetting(key);   // 就地刷新该行(输入框随该行重建,不会残留刚提交的值)
  repaintSummary();
  toast(savedHint(key, out));
  return true;
}
function saveSetting(key, btn) {
  const raw = $(`#in-${key}`).value.trim();
  const errBox = $(`#err-${key}`);
  if (!raw) {   // 空值走「清空」语义,避免误以为点了保存就删了配置
    if (errBox) errBox.innerHTML = "请输入要写入的值;若要删除该项并回落默认行为,请点「清空」。";
    return Promise.resolve(false);
  }
  return putSetting(key, raw, btn);
}
function clearSetting(key, btn) { return putSetting(key, "", btn); }
/* ============ AI 常驻右栏(智能助手:LLM 层,原独立页并入) ============ */
let asstDatasets = [];
let asstDraft = null;

function setAiOpen(open) {
  const panel = $("#aipanel");
  const willOpen = open === undefined ? !panel.classList.contains("open") : !!open;
  panel.classList.toggle("open", willOpen);
  $("#ai-rail").classList.toggle("on", willOpen);
  $("#app").classList.toggle("ai-open", willOpen);   // 控制 AI 拖拽柄显隐
  const bt = $("#back-top");   // 面板展开时主区让位,浮动钮会压在面板上:一并隐藏
  if (bt) bt.style.display = willOpen ? "none" : "";
  const nav = $("#nav-assistant");
  if (nav) nav.classList.toggle("active", willOpen);
  try { localStorage.setItem("harness_ai_open", willOpen ? "1" : "0"); } catch {}
}
function setSideCollapsed(collapsed) {
  // 收起 = 列宽切到 64px 图标轨;内容形态由容器查询按实际宽度自适应
  const willCollapse = collapsed === undefined ? panePx("side") > 100 : !!collapsed;
  setPaneWidth("side", willCollapse ? 64 : 248);
  // 滑动期间淡出文字类内容,宽度到位后随档位淡回,避免中途跳变
  const sb = document.querySelector(".sidebar");
  sb.classList.add("side-fading");
  clearTimeout(setSideCollapsed._t);
  setSideCollapsed._t = setTimeout(() => sb.classList.remove("side-fading"), 300);
}
function setTaskCollapsed(collapsed) {
  const app = $("#app");
  const willCollapse = collapsed === undefined ? !app.classList.contains("task-collapsed") : !!collapsed;
  app.classList.toggle("task-collapsed", willCollapse);
  try { localStorage.setItem("harness_task_collapsed", willCollapse ? "1" : "0"); } catch {}
}
(function initPaneCollapse() {
  let task = "0";
  try { task = localStorage.getItem("harness_task_collapsed") || "0"; } catch {}
  if (task === "1") setTaskCollapsed(true);
})();
function initAiPanel() {
  let pref = null;
  try { pref = localStorage.getItem("harness_ai_open"); } catch {}
  setAiOpen(pref === null ? window.innerWidth >= 1440 : pref === "1");
  renderAiPanel();
}
async function renderAiPanel() {
  $("#ai-body").innerHTML = `<div class="skeleton" style="height:96px"></div>
    <div class="skeleton" style="height:230px"></div><div class="skeleton" style="height:170px"></div>`;
  let status, versions, datasets;
  try {
    [status, versions, datasets] = await Promise.all([
      api("/api/llm/status"), api("/api/versions"), api("/api/datasets")]);
  } catch (e) {
    $("#ai-body").innerHTML = `<div class="ai-sec">${emptyBox("alert", "智能助手加载失败", esc(e.message))}</div>`;
    return;
  }
  asstDatasets = datasets;
  const evalsetOpts = evalsetOptions.length ? evalsetOptions
    : [{ evalset_id: "evalset_v1", case_count: "—" }];
  $("#ai-mode-chip").textContent = status.configured ? "真实端点" : "离线 Mock";
  const prov = status.configured
    ? `<span class="chip2 good">${icon("check", 12)} 已接入真实端点</span>`
    : `<span class="chip2 plain">离线 Mock(未配置 LLM_API_KEY,零成本可复现)</span>`;
  $("#ai-body").innerHTML = `
    <div class="ai-sec">
      <h4>${icon("activity", 14)} Runtime 状态</h4>
      <p class="desc">统一模型访问层:任意 OpenAI 兼容端点 · 结构化输出 · 响应缓存 · 调用审计 · 离线降级。</p>
      <div class="chips">
        ${prov}
        <span class="chip2 plain">模型:${esc(status.model)}</span>
        <span class="chip2 plain num">缓存 ${status.cache_count} 条</span>
      </div>
      ${status.recent_runs.length ? `<div class="ai-runs">${status.recent_runs.slice(0, 6).map(r => `
        <div class="ai-run"><span class="rp-purpose" title="${esc(r.purpose)}">${esc(r.purpose)}</span>
          <span class="muted num">${r.elapsed_ms}ms</span>
          <span class="muted num">${r.cache_hit ? "缓存" : "—"}</span>
          <span class="muted num">${(r.usage && (r.usage.total_tokens || r.usage.estimated_prompt_tokens)) || "—"}</span>
        </div>`).join("")}</div>`
      : `<div class="muted">还没有调用记录 —— 生成一个草稿或跑一次诊断试试。</div>`}
    </div>
    <div class="ai-sec">
      <h4>${icon("plus", 14)} 坏例沉淀助手</h4>
      <p class="desc">反馈原文 → LLM 结合数据集起草 replaycase 草稿;人工确认后才入库(Human-in-the-loop)。</p>
      <label>反馈原文</label>
      <textarea id="asst-complaint" rows="3" maxlength="500"
        placeholder="例:用户点踩:学府路在雨天早高峰被误判,该路段 V/C 已达 0.91,应判为拥堵而不是缓行…"></textarea>
      <label>数据集</label>
      <select id="asst-dataset" onchange="onAsstDatasetChange()">
        ${datasets.map(d => `<option value="${esc(d.name)}">${esc(d.name)}</option>`).join("")}</select>
      <label>指定路段(可选)</label>
      <select id="asst-segment"></select>
      <p style="margin:11px 0 0"><button class="btn" style="width:100%" onclick="llmDraft(this)">${icon("spark", 14)} 生成草稿</button></p>
      <div id="asst-editor"></div>
      <div id="asst-drafts"></div>
    </div>
    <div class="ai-sec">
      <h4>${icon("tool", 14)} 失败诊断(分析者 + 评审者)</h4>
      <p class="desc">对指定版本重放评测并按失败标签归因;结论仅供参考,不自动改动任何资产。</p>
      <label>管线版本</label>
      <select id="asst-dg-version">
        ${versions.map(v => `<option value="${esc(v.version)}"${v.version === "v2" ? " selected" : ""}>${esc(v.version)} · ${esc(v.name)}</option>`).join("")}</select>
      <label>评测集</label>
      <select id="asst-dg-evalset">
        ${evalsetOpts.map(e => `<option value="${esc(e.evalset_id)}">${esc(e.evalset_id)}${e.case_count !== "—" ? ` · ${e.case_count} 条` : ""}</option>`).join("")}</select>
      <p style="margin:11px 0 0"><button class="btn" style="width:100%" onclick="llmDiagnose(this)">${icon("tool", 14)} 生成诊断</button></p>
      <div id="asst-diagnosis"></div>
    </div>`;
  await onAsstDatasetChange();
  await renderAsstDrafts();
}
function showAsstEditor(d) {
  asstDraft = d;
  $("#asst-editor").innerHTML = `
    <div class="ai-draft">
      <div style="font-size:12px;font-weight:700">${icon("spark", 13)} 草稿 ${esc(d.draft_id)}
        <span class="muted" style="font-weight:400"> · ${esc(d.llm.model)} 生成</span></div>
      <div class="muted" style="margin-top:2px;font-size:11.5px">${esc(d.rationale)}</div>
      <label>标题</label><input id="asst-t" maxlength="80" value="${esc(d.title)}">
      <label>失败标签</label><input id="asst-l" maxlength="20" value="${esc(d.label)}">
      <label>期望等级</label><select id="asst-lv">
        ${LEVELS.map(l => `<option${l === d.expected_level ? " selected" : ""}>${l}</option>`).join("")}</select>
      <p style="display:flex;gap:8px;margin:11px 0 0">
        <button class="btn" style="flex:1" onclick="llmConfirmDraft(this)">${icon("check", 14)} 确认沉淀为 replaycase</button>
        <button class="btn secondary" onclick="llmDiscardDraft('${esc(d.draft_id)}')" title="丢弃草稿">${icon("trash", 14)}</button>
      </p>
    </div>`;
}
async function renderAsstDrafts() {
  const box = $("#asst-drafts");
  if (!box) return;
  const drafts = await api("/api/llm/drafts").catch(() => []);
  box.innerHTML = drafts.length ? `
    <p class="muted" style="margin:12px 0 2px;font-weight:700;font-size:11.5px">草稿记录(drafts/)</p>
    ${drafts.map(d => `<div class="ai-run">
      <span class="pill ${d.status === "confirmed" ? "pass" : d.status === "pending" ? "na" : "fail"}">${esc(d.status)}</span>
      <span class="rp-purpose" title="${esc(d.title)} · 期望 ${esc(d.expected_level)}">${esc(d.title)}</span>
      ${d.status === "pending"
        ? `<button class="linklike" onclick="llmLoadDraft('${esc(d.draft_id)}')">编辑</button>`
        : `<span class="muted num">${esc(d.confirmed_case_id || "")}</span>`}
      <button class="icon-btn danger" style="width:24px;height:24px" title="删除草稿" onclick="llmDiscardDraft('${esc(d.draft_id)}')">${icon("trash", 13)}</button>
    </div>`).join("")}` : "";
}
async function onAsstDatasetChange() {
  const ds = $("#asst-dataset").value;
  const { segments } = await api("/api/segments/" + ds);
  $("#asst-segment").innerHTML = `<option value="">让助手自动定位</option>` +
    segments.map(s => `<option value="${esc(s.segment_id)}">${esc(s.segment_id)} · ${esc(s.name)}</option>`).join("");
}
async function llmDraft(btn) {
  await withBusy(btn, async () => {
    const complaint = $("#asst-complaint").value.trim();
    if (complaint.length < 5) { toast("请先填写反馈原文(至少 5 个字)", true); return; }
    const d = await api("/api/llm/drafts", {
      complaint, dataset_name: $("#asst-dataset").value,
      segment_id: $("#asst-segment").value || null });
    showAsstEditor(d); await renderAsstDrafts();
    toast(`草稿 ${d.draft_id} 已生成,请人工确认后入库`);
  });
}
async function llmLoadDraft(id) {
  const d = (await api("/api/llm/drafts")).find(x => x.draft_id === id);
  if (d) showAsstEditor(d);
}
async function llmConfirmDraft(btn) {
  if (!asstDraft) return;
  await withBusy(btn, async () => {
    const out = await api(`/api/llm/drafts/${encodeURIComponent(asstDraft.draft_id)}/confirm`, {
      title: $("#asst-t").value, label: $("#asst-l").value, expected_level: $("#asst-lv").value });
    toast(`已沉淀 ${out.case.case_id} 并加入评测集`);
    $("#asst-editor").innerHTML = `<div class="hint ok">${icon("check", 15)}<span>
      草稿已确认为 <b>${esc(out.case.case_id)}</b>,已加入评测集 —— 可回评测看板重跑自进化验证效果。</span></div>`;
    asstDraft = null; await renderAsstDrafts(); refreshCasesIfVisible(); loadHealth();
  });
}
async function llmDiscardDraft(id) {
  if (!await askConfirm(`删除草稿 ${id}?`, "草稿删除后不可恢复;已确认入库的 case 不受影响。")) return;
  try { await api("/api/llm/drafts/" + encodeURIComponent(id), null, "DELETE"); }
  catch (e) { toast(e.message, true); return; }
  if (asstDraft && asstDraft.draft_id === id) { asstDraft = null; $("#asst-editor").innerHTML = ""; }
  await renderAsstDrafts();
}
async function llmDiagnose(btn) {
  await withBusy(btn, async () => {
    const out = await api("/api/llm/diagnose", {
      version: $("#asst-dg-version").value, evalset: $("#asst-dg-evalset").value });
    if (!out.items.length) {
      $("#asst-diagnosis").innerHTML = `<div class="hint ok">${icon("check", 15)}<span>${esc(out.reviewer_notes || "全部通过,无需诊断")}</span></div>`;
      return;
    }
    $("#asst-diagnosis").innerHTML = `
      ${out.reviewer_notes ? `<div class="hint">${icon("shield", 15)}<span><b>评审意见:</b>${esc(out.reviewer_notes)}</span></div>` : ""}
      ${out.items.map(it => `<div class="round">
        <div class="head"><b>${esc(it.label)}</b><span class="chip2 plain num">${it.affected_cases.length} 条失败</span></div>
        <div class="muted" style="margin-top:6px"><b>根因:</b>${esc(it.root_cause)}</div>
        <ul style="margin:8px 0 0;padding-left:18px;font-size:12.5px;color:var(--t3)">
          ${it.suggestions.map(s => `<li>${esc(s)}</li>`).join("")}</ul>
        <div class="chips" style="margin-bottom:2px">${it.affected_cases.map(c => `<span class="chip2 plain num">${esc(c)}</span>`).join("")}</div>
      </div>`).join("")}
      <div class="muted" style="margin-top:8px">模型:${esc(out.meta.model)} · 本次评测得分 ${pct(out.meta.accuracy)}(${out.meta.passed}/${out.meta.total})</div>`;
  });
}

/* 页签 -> 渲染器接线:switchTab(app-core)运行时读取;本文件最后加载,两份渲染器已就位 */
const renderers = { compare: renderCompare, analyze: renderAnalyze, settings: renderSettings };
const TASK_RENDERERS = { dashboard: renderDashboard, cases: renderCases };  // 需要「任务区(左) + 工作区(中)」协作的页面

boot();
