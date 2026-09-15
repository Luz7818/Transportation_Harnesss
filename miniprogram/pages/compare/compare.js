const { request } = require("../../utils/api.js");

Page({
  data: {
    reports: [],
    aIdx: 0,
    bIdx: 0,
    out: null,
    loading: false,
    ready: false,
  },

  onShow() {
    request("/api/reports").then(reports => {
      reports.forEach(r => { r.accText = (r.accuracy * 100).toFixed(1) + "%"; });
      this.setData({ reports, ready: true });
    });
  },

  onA(e) { this.setData({ aIdx: Number(e.detail.value) }); },
  onB(e) { this.setData({ bIdx: Number(e.detail.value) }); },
  swap() {
    this.setData({ aIdx: this.data.bIdx, bIdx: this.data.aIdx, out: null });
  },

  compare() {
    const a = this.data.reports[this.data.aIdx].report_id;
    const b = this.data.reports[this.data.bIdx].report_id;
    this.setData({ loading: true });
    wx.showLoading({ title: "对比中…" });
    request(`/api/compare?a=${a}&b=${b}`)
      .then(out => {
        wx.hideLoading();
        out.aDisp = (out.a.accuracy * 100).toFixed(1) + "%";
        out.bDisp = (out.b.accuracy * 100).toFixed(1) + "%";
        out.rows = out.rows.map(r => ({
          ...r,
          aText: r.a_passed === null || r.a_passed === undefined ? "—" : (r.a_passed ? "PASS" : "FAIL"),
          bText: r.b_passed === null || r.b_passed === undefined ? "—" : (r.b_passed ? "PASS" : "FAIL"),
        }));
        this.setData({ out });
      })
      .catch(() => wx.hideLoading())
      .finally(() => this.setData({ loading: false }));
  },
});
