const { request } = require("../../utils/api.js");

Page({
  data: {
    versions: [],
    versionIdx: 0,
    datasets: [],
    datasetIdx: 0,
    out: null,
    loading: false,
  },

  onShow() {
    Promise.all([request("/api/versions"), request("/api/datasets")])
      .then(([versions, datasets]) => {
        // picker 只支持单一 range-key,把情景标签拼进显示名
        datasets.forEach(d => {
          d.displayName = d.name + (d.scenario && d.scenario.tag ? ` · ${d.scenario.tag}` : "");
        });
        this.setData({ versions, datasets });
      });
  },

  onVersion(e) { this.setData({ versionIdx: Number(e.detail.value) }); },
  onDataset(e) { this.setData({ datasetIdx: Number(e.detail.value) }); },

  analyze() {
    const version = this.data.versions[this.data.versionIdx].version;
    const dataset_name = this.data.datasets[this.data.datasetIdx].name;
    this.setData({ loading: true });
    wx.showLoading({ title: "分析中…" });
    request("/api/analyze", "POST", { version, dataset_name })
      .then(out => { wx.hideLoading(); this.setData({ out }); })
      .catch(() => wx.hideLoading())
      .finally(() => this.setData({ loading: false }));
  },
});
