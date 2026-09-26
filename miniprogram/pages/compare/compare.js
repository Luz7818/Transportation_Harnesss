const { request } = require("../../utils/api.js");

const DIFF_TEXT = {
  fixed: "✅ 修复", regressed: "⚠️ 回归", changed: "数值变化",
  both_failed: "仍失败", added: "新增检查", removed: "移除检查",
};

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
        out.rows = out.rows.map(r => {
          const diffs = r.check_diffs || [];
          return {
            ...r,
            aText: r.a_passed === null || r.a_passed === undefined ? "—" : (r.a_passed ? "PASS" : "FAIL"),
            bText: r.b_passed === null || r.b_passed === undefined ? "—" : (r.b_passed ? "PASS" : "FAIL"),
            aScoreText: r.a_score == null ? "—" : Math.round(r.a_score * 100) + "%",
            bScoreText: r.b_score == null ? "—" : Math.round(r.b_score * 100) + "%",
            diffCount: diffs.length,
            expanded: false,
            diffs: diffs.map((d, i) => ({
              ...d,
              key: "k" + i,
              statusText: DIFF_TEXT[d.status] || d.status,
              expectedText: d.expected === null || d.expected === undefined ? "—" : String(d.expected),
            })),
          };
        });
        this.setData({ out });
      })
      .catch(() => wx.hideLoading())
      .finally(() => this.setData({ loading: false }));
  },

  toggleRow(e) {
    const idx = e.currentTarget.dataset.idx;
    this.setData({ [`out.rows[${idx}].expanded`]: !this.data.out.rows[idx].expanded });
  },
});
