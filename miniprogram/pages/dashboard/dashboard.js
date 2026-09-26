const { request } = require("../../utils/api.js");

const KIND_ICON = { case: "📥", eval: "🧪", evolve: "🧬", draft: "🤖" };

Page({
  data: {
    health: null,
    llm: null,
    versions: [],
    reports: [],
    evolutions: [],
    evalsets: [],
    evalsetIdx: 0,
    baselineIdx: 0,
    activity: [],
    evolving: false,
    loading: false,
    loaded: false,
    offline: false,
  },

  onShow() { this.refresh(); },
  onPullDownRefresh() { this.refresh(() => wx.stopPullDownRefresh()); },

  refresh(done) {
    Promise.all([
      request("/api/health"),
      request("/api/llm/status"),
      request("/api/versions"),
      request("/api/reports"),
      request("/api/evolutions"),
      request("/api/evalsets"),
      request("/api/activity?limit=10"),
    ])
      .then(([health, llm, versions, reports, evolutions, evalsets, activity]) => {
        const latest = {};
        reports.forEach(r => { if (!latest[r.version]) latest[r.version] = r; });
        versions.forEach(v => {
          v.latest = latest[v.version] || null;
          v.accText = v.latest ? (v.latest.accuracy * 100).toFixed(1) + "%" : "未评测";
          v.barWidth = v.latest ? Math.round(v.latest.accuracy * 100) : 0;
        });
        reports.forEach(r => { r.accText = (r.accuracy * 100).toFixed(1) + "%"; });
        evolutions.forEach(e => {
          const b = e.baseline || {};
          const bAcc = typeof b.accuracy === "number" ? (b.accuracy * 100).toFixed(1) + "%" : "—";
          e.traj = [`${b.version || "v0"} ${bAcc}`]
            .concat((e.rounds || []).map(r => `${r.version} ${(r.accuracy * 100).toFixed(1)}%`))
            .join(" → ");
          e.allPass = String(e.stop_reason || "").indexOf("全部通过") >= 0;
        });
        activity.forEach((a, i) => {
          a.icon = KIND_ICON[a.kind] || "•";
          a.key = `${a.kind}-${a.ref || a.ts || i}`;
        });
        let evalsetIdx = evalsets.findIndex(s => s.evalset_id === "evalset_v1");
        if (evalsetIdx < 0) evalsetIdx = 0;
        let baselineIdx = versions.findIndex(v => v.version === "v0");
        if (baselineIdx < 0) baselineIdx = 0;
        this.setData({
          health, llm, versions, reports, evolutions, evalsets, evalsetIdx,
          baselineIdx, activity, loaded: true, offline: false,
        });
      })
      .catch(() => this.setData({ loaded: true, offline: true }))
      .finally(() => { if (done) done(); });
  },

  pickedEvalset() {
    const s = this.data.evalsets[this.data.evalsetIdx];
    return (s && s.evalset_id) || "evalset_v1";
  },
  pickedBaseline() {
    const v = this.data.versions[this.data.baselineIdx];
    return (v && v.version) || "v0";
  },

  onEvalset(e) { this.setData({ evalsetIdx: Number(e.detail.value) }); },
  onBaseline(e) { this.setData({ baselineIdx: Number(e.detail.value) }); },

  runEval(e) {
    const version = e.currentTarget.dataset.version;
    this.setData({ loading: true });
    wx.showLoading({ title: `评测 ${version}…` });
    request("/api/eval/run", "POST", { version, evalset: this.pickedEvalset() })
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
    request("/api/evolve/run", "POST", { evalset: this.pickedEvalset(), baseline: this.pickedBaseline() })
      .then(s => {
        wx.hideLoading();
        wx.showToast({ title: `完成:最佳 ${s.best.version}`, icon: "success" });
        this.refresh();
        wx.navigateTo({ url: `/pages/evolution/evolution?id=${s.evolution_id}` });
      })
      .catch(err => {
        wx.hideLoading();
        if (err && err.statusCode === 409) {
          wx.showModal({
            title: "无法启动",
            content: "自进化循环正在运行中,请稍后再试。",
            showCancel: false,
          });
        }
      })
      .finally(() => this.setData({ evolving: false }));
  },

  goReport(e) { wx.navigateTo({ url: "/pages/report/report?id=" + e.currentTarget.dataset.id }); },
  goEvolution(e) { wx.navigateTo({ url: "/pages/evolution/evolution?id=" + e.currentTarget.dataset.id }); },
  goCase(e) { wx.navigateTo({ url: "/pages/case-detail/case-detail?id=" + e.currentTarget.dataset.id }); },
  goDrafts() { wx.navigateTo({ url: "/pages/drafts/drafts" }); },

  onActivityTap(e) {
    const { kind, ref } = e.currentTarget.dataset;
    if (kind === "eval" && ref) this.goReport({ currentTarget: { dataset: { id: ref } } });
    else if (kind === "evolve" && ref) this.goEvolution({ currentTarget: { dataset: { id: ref } } });
    else if (kind === "case" && ref) this.goCase({ currentTarget: { dataset: { id: ref } } });
    else if (kind === "draft") this.goDrafts();
  },
});
