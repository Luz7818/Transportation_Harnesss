const { request } = require("../../utils/api.js");

Page({
  data: { id: "", rep: null, labelStats: [], results: [], loading: true },

  onLoad(options) {
    const id = options.id || "";
    this.setData({ id });
    request("/api/reports/" + encodeURIComponent(id))
      .then(rep => {
        rep.accText = (rep.accuracy * 100).toFixed(1) + "%";
        rep.durationText = rep.duration_ms != null ? Math.round(rep.duration_ms) + " ms" : "—";
        const labelStats = Object.keys(rep.label_stats || {}).map(label => {
          const s = rep.label_stats[label];
          const rate = s.total ? s.passed / s.total : 0;
          return {
            label, passed: s.passed, total: s.total,
            rateText: (rate * 100).toFixed(0) + "%",
            cls: rate >= 0.99 ? "good" : (rate >= 0.5 ? "mid" : "bad"),
          };
        });
        const results = (rep.results || [])
          .map(r => ({
            case_id: r.case_id, title: r.title, label: r.label, passed: r.passed,
            scoreText: Math.round((r.score || 0) * 100) + "%",
          }))
          .sort((a, b) => (a.passed === b.passed
            ? a.case_id.localeCompare(b.case_id)
            : (a.passed ? 1 : -1)));   // 未通过的排前面,现场聚焦失败
        this.setData({ rep, labelStats, results, loading: false });
      })
      .catch(() => this.setData({ loading: false }));
  },
});
