const {
  login, getBaseUrl, setBaseUrl, getToken, secondsLeft, needsRenewal, backAfterLogin,
} = require("../../utils/api.js");

// 剩余时长的可读写法:不足 1 小时的都说成分钟,避免出现"剩余 0 小时"
function humanLeft(left) {
  if (left >= 86400) return `${Math.floor(left / 86400)} 天`;
  if (left >= 3600) return `${Math.floor(left / 3600)} 小时`;
  return `${Math.max(1, Math.ceil(left / 60))} 分钟`;
}

function describeSession() {
  if (!getToken()) return "";
  const left = secondsLeft();
  if (left === null) return "本机已存有会话令牌,重新登录可续期。";
  if (left <= 0) return "本机会话已过期,请重新登录。";
  const renew = needsRenewal() ? "剩余不足 24 小时,建议现在重新登录续期。" : "";
  return `本机已登录,会话剩余约 ${humanLeft(left)}。${renew}`;
}

Page({
  data: {
    baseUrl: "",
    username: "",
    password: "",
    error: "",
    sessionText: "",
    submitting: false,
  },

  onLoad() {
    this.setData({ baseUrl: getBaseUrl(), sessionText: describeSession() });
  },

  onInput(e) {
    this.setData({ [e.currentTarget.dataset.field]: e.detail.value });
  },

  submit() {
    if (this.data.submitting) return;
    const baseUrl = this.data.baseUrl.trim();
    const username = this.data.username.trim();
    const password = this.data.password;
    if (!baseUrl) { this.showError("请填写服务器地址"); return; }
    if (!username || !password) { this.showError("请填写用户名与口令"); return; }

    setBaseUrl(baseUrl);
    this.setData({ submitting: true, error: "" });
    wx.showLoading({ title: "登录中…" });
    login(username, password)
      .then(out => {
        wx.hideLoading();
        wx.showToast({ title: `已登录:${out.username || username}`, icon: "success" });
        backAfterLogin();
      })
      .catch(err => {
        wx.hideLoading();
        // 不自动重试:服务端对同一用户名连续失败 5 次会锁定 10 分钟,重试只会加重锁定
        this.showError(err.message === "network error" ? "连不上服务器,请检查地址与网络" : err.message);
      })
      .finally(() => this.setData({ submitting: false, sessionText: describeSession() }));
  },

  showError(message) {
    this.setData({ error: String(message).replace(/^请求失败\(\d+\)$/, "登录失败") });
  },
});
