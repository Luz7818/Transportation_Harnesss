const { request } = require("../../utils/api.js");

const LEVELS = ["畅通", "基本畅通", "缓行", "拥堵", "严重拥堵", "数据缺失"];

Page({
  data: {
    cases: [],
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

  refresh() {
    request("/api/cases").then(cases => this.setData({ cases }));
  },

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
