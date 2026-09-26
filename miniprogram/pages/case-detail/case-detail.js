const { request } = require("../../utils/api.js");

const TYPE_TEXT = {
  classify: "拥堵等级", metric: "指标校验", no_crash: "健壮性",
  recommendations: "处置建议", congested_empty: "拥堵路段为空", conclusion_keyword: "结论关键词",
};

Page({
  data: { id: "", cs: null, checks: [], loading: true, deleting: false },

  onLoad(options) {
    const id = options.id || "";
    this.setData({ id });
    request("/api/cases/" + encodeURIComponent(id))
      .then(cs => {
        const checks = (cs.checks || []).map((c, i) => ({
          ...c,
          key: "c" + i,
          typeText: TYPE_TEXT[c.type] || c.type,
          expectedText: Array.isArray(c.expected) ? c.expected.join(" / ")
            : (c.expected === null || c.expected === undefined ? "—" : String(c.expected)),
        }));
        this.setData({ cs, checks, loading: false });
      })
      .catch(() => this.setData({ loading: false }));
  },

  del() {
    if (this.data.deleting) return;
    wx.showModal({
      title: "删除 case",
      content: `确定删除 ${this.data.id}?将同时从所有评测集清单移除;已归档报告不受影响。`,
      confirmText: "删除",
      confirmColor: "#dc2626",
      success: res => {
        if (!res.confirm) return;
        this.setData({ deleting: true });
        request("/api/cases/" + encodeURIComponent(this.data.id), "DELETE")
          .then(() => {
            wx.showToast({ title: "已删除", icon: "success" });
            setTimeout(() => wx.navigateBack(), 600);
          })
          .catch(() => {})
          .finally(() => this.setData({ deleting: false }));
      },
    });
  },
});
