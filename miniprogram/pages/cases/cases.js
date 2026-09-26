const { request } = require("../../utils/api.js");

const LEVELS = ["畅通", "基本畅通", "缓行", "拥堵", "严重拥堵", "数据缺失"];

Page({
  data: {
    cases: [],
    filtered: [],
    labels: [],
    labelFilter: "全部",
    selectMode: false,
    selected: {},
    selectedKeys: [],
    datasets: [],
    datasetIdx: 0,
    segments: [],
    segmentIdx: 0,
    levels: LEVELS,
    levelIdx: 3,
    form: { title: "", label: "", saturation: "", notes: "" },
    submitting: false,
  },

  onShow() {
    this.refresh();
    request("/api/datasets").then(datasets => {
      this.setData({ datasets });
      this.loadSegments();
    });
  },

  onPullDownRefresh() { this.refresh(() => wx.stopPullDownRefresh()); },

  refresh(done) {
    request("/api/cases")
      .then(cases => {
        const labels = ["全部"].concat([...new Set(cases.map(c => c.label || "未分类"))]);
        this.setData({
          cases,
          labels,
          filtered: this.applyFilter(cases, this.data.labelFilter),
        });
      })
      .finally(() => { if (done) done(); });
  },

  applyFilter(cases, label) {
    return label === "全部" ? cases : cases.filter(c => (c.label || "未分类") === label);
  },

  onFilter(e) {
    const label = e.currentTarget.dataset.label;
    this.setData({ labelFilter: label, filtered: this.applyFilter(this.data.cases, label) });
  },

  onCaseTap(e) {
    const id = e.currentTarget.dataset.id;
    if (this.data.selectMode) { this.toggleSelect(id); return; }
    wx.navigateTo({ url: "/pages/case-detail/case-detail?id=" + id });
  },

  onCaseLongPress(e) {
    const id = e.currentTarget.dataset.id;
    if (!this.data.selectMode) this.setData({ selectMode: true, selected: {} });
    this.toggleSelect(id);
  },

  toggleSelect(id) {
    const selected = { ...this.data.selected };
    if (selected[id]) delete selected[id];
    else selected[id] = true;
    this.setData({ selected, selectedKeys: Object.keys(selected) });
  },

  selectAll() {
    const selected = {};
    this.data.filtered.forEach(c => { selected[c.case_id] = true; });
    this.setData({ selected, selectedKeys: Object.keys(selected) });
  },

  clearSelect() { this.setData({ selected: {}, selectedKeys: [] }); },
  exitSelect() { this.setData({ selectMode: false, selected: {}, selectedKeys: [] }); },

  batchDelete() {
    const ids = Object.keys(this.data.selected);
    if (!ids.length) { wx.showToast({ title: "先长按选择要删除的 case", icon: "none" }); return; }
    wx.showModal({
      title: "批量删除",
      content: `确定删除选中的 ${ids.length} 条 case?将同时从评测集清单移除,报告归档不受影响。`,
      confirmText: "删除",
      confirmColor: "#dc2626",
      success: res => {
        if (!res.confirm) return;
        wx.showLoading({ title: "删除中…" });
        request("/api/cases/batch-delete", "POST", { ids })
          .then(out => {
            wx.hideLoading();
            const miss = out.missing.length ? `(另有 ${out.missing.length} 条不存在)` : "";
            wx.showToast({ title: `已删除 ${out.deleted.length} 条${miss}`, icon: "none" });
            this.exitSelect();
            this.refresh();
          })
          .catch(() => wx.hideLoading());
      },
    });
  },

  goDrafts() { wx.navigateTo({ url: "/pages/drafts/drafts" }); },

  loadSegments() {
    const ds = this.data.datasets[this.data.datasetIdx];
    if (!ds) return;
    request("/api/segments/" + ds.name).then(out =>
      this.setData({
        segments: out.segments.map(s => ({ ...s, display: `${s.segment_id} · ${s.name}` })),
        segmentIdx: 0,
      }));
  },

  onDataset(e) { this.setData({ datasetIdx: Number(e.detail.value) }, () => this.loadSegments()); },
  onSegment(e) { this.setData({ segmentIdx: Number(e.detail.value) }); },
  onLevel(e) { this.setData({ levelIdx: Number(e.detail.value) }); },
  onInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`form.${field}`]: e.detail.value });
  },

  submit() {
    const f = this.data.form;
    const ds = this.data.datasets[this.data.datasetIdx];
    const seg = this.data.segments[this.data.segmentIdx];
    if (!f.title.trim()) { wx.showToast({ title: "请填写标题", icon: "none" }); return; }
    if (!seg) { wx.showToast({ title: "请选择路段", icon: "none" }); return; }
    this.setData({ submitting: true });
    wx.showLoading({ title: "沉淀中…" });
    request("/api/cases", "POST", {
      title: f.title,
      label: f.label || "未分类",
      dataset_name: ds.name,
      segment: seg.segment_id,
      expected_level: this.data.levels[this.data.levelIdx],
      expected_saturation: f.saturation === "" ? null : parseFloat(f.saturation),
      notes: f.notes,
    }).then(out => {
      wx.hideLoading();
      wx.showToast({ title: `已沉淀 ${out.case.case_id}`, icon: "success" });
      this.setData({ form: { title: "", label: "", saturation: "", notes: "" } });
      this.refresh();
    }).catch(() => wx.hideLoading())
      .finally(() => this.setData({ submitting: false }));
  },
});
