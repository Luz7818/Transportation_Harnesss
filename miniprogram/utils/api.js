// 统一请求封装:自动携带 X-API-Token,统一错误提示;401 时给出令牌配置指引
const { BASE_URL, TOKEN } = require("../config.js");

let last401At = 0; // 并行请求同时 401 时只弹一次指引

function request(path, method = "GET", data = null) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE_URL + path,
      method,
      data: data || undefined,
      header: TOKEN ? { "X-API-Token": TOKEN } : {},
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }
        let detail = (res.data && res.data.detail) || `请求失败(${res.statusCode})`;
        if (typeof detail === "object") {
          detail = Object.values(detail).flat().join("; ");
        }
        if (res.statusCode === 401 && Date.now() - last401At > 3000) {
          last401At = Date.now();
          wx.showModal({
            title: "访问未授权(401)",
            content: "服务器开启了令牌鉴权。请在 miniprogram/config.js 的 TOKEN 中填写与服务器 AUTH_TOKEN 一致的值,保存后重新编译。",
            showCancel: false,
          });
        }
        wx.showToast({ title: String(detail).slice(0, 30), icon: "none" });
        const err = new Error(String(detail));
        err.statusCode = res.statusCode;
        reject(err);
      },
      fail() {
        wx.showToast({ title: "网络错误,请检查服务器地址", icon: "none" });
        reject(new Error("network error"));
      },
    });
  });
}

module.exports = { request, BASE_URL };
