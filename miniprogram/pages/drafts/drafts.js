const { request } = require("../../utils/api.js");

const LEVELS = ["畅通", "基本畅通", "缓行", "拥堵", "严重拥堵", "数据缺失"];

Page({
  data: {
    llm: null,
    datasets: [], datasetIdx: 0,
    segments: [], segmentIdx: 0,
    drafts: [],
    complaint: "",
    levels: LEVELS,
    versions: [], versionIdx: 0,
    evalsets: [], evalsetIdx: 0,
    diag: null,
    generating: false,
    diagnosing: false,
    loaded: false,
  },

  onShow() { this.boot(); },

  boot() {
    Promise.all([
      request("/api/llm/status"),
      request("/api/llm/drafts"),
      request("/api/datasets"),
      request("/api/versions"),
      request("/api/evalsets"),
    ])
      .then(([llm, drafts, datasets, versions, evalsets]) => {
        datasets.forEach(d => {
          d.displayName = d.name + (d.scenario && d.scenario.tag ? ` · ${d.scenario.tag}` : "");
        });
        drafts.forEach((d, i) => {
          d.key = "d" + i;
          d.levelIdx = Math.max(0, LEVELS.indexOf(d.expected_level));
          d.editTitle = d.title;
          d.editLabel = d.label;
        });
        let versionIdx = versions.findIndex(v => v.version === "v2");
        if (versionIdx < 0) versionIdx = 0;
        let evalsetIdx = evalsets.findIndex(s => s.evalset_id === "evalset_v1");
        if (evalsetIdx < 0) evalsetIdx = 0;
        this.setData({ llm, drafts, datasets, versions, evalsets, versionIdx, evalsetIdx, loaded: true },
          () => this.loadSegments());
      })
      .catch(() => this.setData({ loaded: true }));
  },

  loadSegments() {
    const ds = this.data.datasets[this.data.datasetIdx];
    if (!ds) { this.setData({ segments: [] }); return; }
    request("/api/segments/" + ds.name)
      .then(out => {
        const segments = [{ segment_id: "", name: "自动选择(LLM 判定)" }]
          .concat(out.segments.map(s => ({ segment_id: s.segment_id, name: `${s.segment_id} · ${s.name}` })));
        this.setData({ segments, segmentIdx: 0 });
      })
      .catch(() => this.setData({ segments: [] }));
  },

  onDataset(e) { this.setData({ datasetIdx: Number(e.detail.value) }, () => this.loadSegments()); },
  onSegment(e) { this.setData({ segmentIdx: Number(e.detail.value) }); },
  onVersion(e) { this.setData({ versionIdx: Number(e.detail.value) }); },
  onEvalset(e) { this.setData({ evalsetIdx: Number(e.detail.value) }); },
  onComplaint(e) { this.setData({ complaint: e.detail.value }); },

  onDraftField(e) {
    const { id, field } = e.currentTarget.dataset;
    this.setData({
      drafts: this.data.drafts.map(d => (d.draft_id === id ? { ...d, [field]: e.detail.value } : d)),
    });
  },
  onDraftLevel(e) {
    const { id } = e.currentTarget.dataset;
    const v = Number(e.detail.value);
    this.setData({
      drafts: this.data.drafts.map(d => (d.draft_id === id ? { ...d, levelIdx: v } : d)),
    });
  },

  generate() {
    const text = (this.data.complaint || "").trim();
    if (text.length < 5) { wx.showToast({ title: "反馈原文至少 5 个字", icon: "none" }); return; }
    const ds = this.data.datasets[this.data.datasetIdx];
    const seg = this.data.segments[this.data.segmentIdx];
    this.setData({ generating: true });
    wx.showLoading({ title: "AI 生成草稿中…" });
    request("/api/llm/drafts", "POST", {
      complaint: text,
      dataset_name: ds ? ds.name : "",
      segment_id: seg && seg.segment_id ? seg.segment_id : null,
    })
      .then(() => {
        wx.hideLoading();
        wx.showToast({ title: "草稿已生成,请确认", icon: "success" });
        this.setData({ complaint: "" });
        this.boot();
      })
      .catch(() => wx.hideLoading())
      .finally(() => this.setData({ generating: false }));
  },

  confirmDraft(e) {
    const id = e.currentTarget.dataset.id;
    const d = this.data.drafts.find(x => x.draft_id === id);
    if (!d) return;
    wx.showLoading({ title: "入库中…" });
    request(`/api/llm/drafts/${encodeURIComponent(id)}/confirm`, "POST", {
      title: d.editTitle,
      label: d.editLabel,
      expected_level: LEVELS[d.levelIdx],
    })
      .then(out => {
        wx.hideLoading();
        wx.showModal({
          title: "已入库",
          content: `草稿已确认为 ${out.case.case_id} 并加入评测集。可回看板重新评测验证。`,
          showCancel: false,
        });
        this.boot();
      })
      .catch(() => wx.hideLoading());
  },

  delDraft(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: "丢弃草稿",
      content: `确定删除草稿 ${id}?`,
      confirmText: "删除",
      confirmColor: "#dc2626",
      success: res => {
        if (!res.confirm) return;
        request(`/api/llm/drafts/${encodeURIComponent(id)}`, "DELETE")
          .then(() => this.boot())
          .catch(() => {});
      },
    });
  },

  diagnose() {
    const version = (this.data.versions[this.data.versionIdx] || {}).version;
    const evalset = (this.data.evalsets[this.data.evalsetIdx] || {}).evalset_id;
    this.setData({ diagnosing: true });
    wx.showLoading({ title: "诊断中(重放 + LLM)…" });
    request("/api/llm/diagnose", "POST", { version, evalset })
      .then(diag => {
        wx.hideLoading();
        diag.accText = diag.meta ? (diag.meta.accuracy * 100).toFixed(1) + "%" : "";
        diag.items = (diag.items || []).map((it, i) => ({
          ...it,
          key: "i" + i,
          suggestions: it.suggestions || [],
          affected: (it.affected_cases || []).join("、"),
        }));
        this.setData({ diag });
      })
      .catch(() => wx.hideLoading())
      .finally(() => this.setData({ diagnosing: false }));
  },
});
