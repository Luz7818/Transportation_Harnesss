const { request } = require("../../utils/api.js");

Page({
  data: {
    versions: [],
    reports: [],
    evolutions: [],
    evolving: false,
    loading: false,
    loaded: false,
  },

  onShow() { this.refresh(); },

  refresh() {
    Promise.all([request("/api/versions"), request("/api/reports"), request("/api/evolutions")])
      .then(([versions, reports, evolutions]) => {
        const latest = {};
        reports.forEach(r => { if (!latest[r.version]) latest[r.version] = r; });
        versions.forEach(v => {
          v.latest = latest[v.version] || null;
          v.accText = v.latest ? (v.latest.accuracy * 100).toFixed(1) + "%" : "未评测";
          v.barWidth = v.latest ? Math.round(v.latest.accuracy * 100) : 0;
        });
        evolutions.forEach(e => {
          e.allPass = String(e.stop_reason || "").indexOf("全部通过") >= 0;
          e.traj = [`${e.baseline.version} ${(e.baseline.accuracy * 100).toFixed(1)}%`]
            .concat(e.rounds.map(r => `${r.version} ${(r.accuracy * 100).toFixed(1)}%`)).join(" → ");
        });
        this.setData({ versions, reports, evolutions, loaded: true });
      })
      .catch(() => this.setData({ loaded: true }));
  },

  runEval(e) {
    const version = e.currentTarget.dataset.version;
    this.setData({ loading: true });
    wx.showLoading({ title: "评测中…" });
    request("/api/eval/run", "POST", { version })
      .then(rep => {
        wx.hideLoading();
        wx.showToast({ title: `${version} ${rep.passed_count}/${rep.total}`, icon: "success" });
        this.refresh();
      })
      .catch(() => wx.hideLoading())
      .finally(() => this.setData({ loading: false }));
  },

  runEvolve() {
    if (this.data.evolving) return;
    this.setData({ evolving: true });
    wx.showLoading({ title: "自进化中(最多 2 轮)…" });
    request("/api/evolve/run", "POST")
      .then(s => {
        wx.hideLoading();
        const b = s.baseline;
        wx.showModal({
          title: `自进化完成:最佳 ${s.best.version}`,
          content: `${b.version} ${b.passed_count}/${b.total}(${(b.accuracy * 100).toFixed(1)}%)`
            + ` → ${s.best.version} ${s.best.passed_count}/${s.best.total}(${(s.best.accuracy * 100).toFixed(1)}%)`
            + `,迭代 ${s.iterations_used} 轮(${s.stop_reason})`,
          showCancel: false,
        });
        this.refresh();
      })
      .catch(() => wx.hideLoading())
      .finally(() => this.setData({ evolving: false }));
  },
});
