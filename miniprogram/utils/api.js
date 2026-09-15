// 统一请求封装:自动携带 X-API-Token,统一错误提示
const { BASE_URL, TOKEN } = require("../config.js");

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
        } else {
          let detail = (res.data && res.data.detail) || `请求失败(${res.statusCode})`;
          if (typeof detail === "object") {
            detail = Object.values(detail).flat().join("; ");
          }
          wx.showToast({ title: String(detail).slice(0, 30), icon: "none" });
          reject(new Error(String(detail)));
        }
      },
      fail() {
        wx.showToast({ title: "网络错误,请检查服务器地址", icon: "none" });
        reject(new Error("network error"));
      },
    });
  });
}

module.exports = { request };
