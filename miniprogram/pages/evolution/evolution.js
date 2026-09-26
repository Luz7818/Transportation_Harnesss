const { request } = require("../../utils/api.js");

Page({
  data: { id: "", evo: null, rounds: [], pending: false, loading: true },

  onLoad(options) {
    const id = options.id || "";
    this.setData({ id });
    request("/api/evolutions/" + encodeURIComponent(id))
      .then(evo => {
        const b = evo.baseline || {};
        evo.baseAcc = typeof b.accuracy === "number" ? (b.accuracy * 100).toFixed(1) + "%" : "—";
        evo.bestAcc = evo.best && typeof evo.best.accuracy === "number"
          ? (evo.best.accuracy * 100).toFixed(1) + "%" : "—";
        const rounds = (evo.rounds || []).map(r => ({
          ...r,
          accText: (r.accuracy * 100).toFixed(1) + "%",
          deltaText: (r.improvement >= 0 ? "+" : "") + (r.improvement * 100).toFixed(1) + "pp",
          up: r.improvement >= 0,
          newly: r.newly_passed || [],
          regressed: r.regressed || [],
          remaining: Object.keys(r.remaining_failures || {})
            .map(label => ({ label, items: r.remaining_failures[label] })),
        }));
        const pending = String(evo.stop_reason || "").indexOf("待验证") >= 0;
        this.setData({ evo, rounds, pending, loading: false });
      })
      .catch(() => this.setData({ loading: false }));
  },

  goCompare() { wx.switchTab({ url: "/pages/compare/compare" }); },
});
