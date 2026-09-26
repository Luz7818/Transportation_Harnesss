// 统一请求封装:携带用户登录换来的短期会话令牌,统一错误提示。
// 安全前提:小程序包会分发到用户手机,打进包里的任何常量都等于公开,所以这里不再有
// 静态机器令牌 —— 令牌由 /api/auth/login 按账号签发(有效期 7 天),存在本机 storage;
// 无令牌、令牌过期或服务端回 401 时,清掉令牌并回登录页重新换取。

const TOKEN_KEY = "harness_session_token";
const EXPIRES_KEY = "harness_session_expires_at";
const BASE_URL_KEY = "harness_base_url";
const RETURN_TO_KEY = "harness_return_to";

const LOGIN_PAGE = "/pages/login/login";
const FALLBACK_PAGE = "/pages/dashboard/dashboard";
const RENEW_SOON = 24 * 3600;   // 令牌剩余不足 24 小时提示续登

let lastNeedLoginAt = 0;        // 并行请求同时缺凭据时只提示、只跳一次
let renewalWarned = false;      // 临期提示每次启动只打扰一次

/* ---------------------------- 服务器地址 ---------------------------- */

// config.js 不入库(内含真实服务器地址),从仓库直接克隆、尚未复制出该文件时 require 会失败;
// 兜底成空串交给界面提示去配置,而不是让整个请求模块崩掉。
function configBaseUrl() {
  try {
    return require("../config.js").BASE_URL || "";
  } catch (e) {
    return "";
  }
}

// 优先取用户在登录页填的覆盖值,其次取 config.js;去掉末尾斜杠,避免拼出 //api/...
function getBaseUrl() {
  const raw = String(wx.getStorageSync(BASE_URL_KEY) || configBaseUrl()).trim();
  return raw.replace(/\/+$/, "");
}

function setBaseUrl(url) {
  const value = String(url || "").trim();
  if (value) wx.setStorageSync(BASE_URL_KEY, value);
  else wx.removeStorageSync(BASE_URL_KEY);
}

/* ---------------------------- 会话令牌 ---------------------------- */

function getToken() {
  return String(wx.getStorageSync(TOKEN_KEY) || "");
}

// 服务端未返回 expires_at 时为 null(不猜有效期,过期与否交给 401 判定)
function secondsLeft() {
  const expiresAt = Number(wx.getStorageSync(EXPIRES_KEY));
  return expiresAt > 0 ? expiresAt - Math.floor(Date.now() / 1000) : null;
}

function sessionUsable() {
  if (!getToken()) return false;
  const left = secondsLeft();
  return left === null || left > 0;
}

function saveSession(token, expiresAt) {
  wx.setStorageSync(TOKEN_KEY, String(token || ""));
  wx.setStorageSync(EXPIRES_KEY, Number(expiresAt) || 0);
}

function clearSession() {
  wx.removeStorageSync(TOKEN_KEY);
  wx.removeStorageSync(EXPIRES_KEY);
}

function currentPath() {
  const pages = getCurrentPages();
  const page = pages[pages.length - 1];
  return page ? "/" + page.route : "";
}

function gotoLogin() {
  const from = currentPath();
  if (from === LOGIN_PAGE) return;
  if (from) wx.setStorageSync(RETURN_TO_KEY, from);   // 记住来源页,登录成功后跳回
  wx.navigateTo({ url: LOGIN_PAGE });
}

// 登录成功后的回跳:能退回去处就退回去(保留原页状态),冷启动直达登录页时按记录的路径重开
function backAfterLogin() {
  const target = String(wx.getStorageSync(RETURN_TO_KEY) || "");
  wx.removeStorageSync(RETURN_TO_KEY);
  if (getCurrentPages().length > 1) {
    wx.navigateBack();
    return;
  }
  wx.reLaunch({ url: target || FALLBACK_PAGE });
}

// 本地无令牌 / 服务端判 401 两条路径共用:清掉令牌、提示并跳登录页
function needLogin(detail) {
  clearSession();
  const now = Date.now();
  if (now - lastNeedLoginAt <= 3000) return;
  lastNeedLoginAt = now;
  wx.showToast({ title: String(detail).slice(0, 30), icon: "none" });
  gotoLogin();
}

// 令牌临期(剩余不足 24 小时):登录页与请求层共用这一个判据
function needsRenewal() {
  const left = secondsLeft();
  return left !== null && left > 0 && left <= RENEW_SOON;
}

// 临期提示:每次启动只打扰一次
function warnIfExpiring() {
  if (renewalWarned || !needsRenewal()) return;
  renewalWarned = true;
  wx.showToast({ title: `登录将在约 ${Math.ceil(secondsLeft() / 3600)} 小时后过期,请重新登录`, icon: "none", duration: 3000 });
}

/* ---------------------------- 请求 ---------------------------- */

function detailOf(data, statusCode) {
  let detail = (data && data.detail) || `请求失败(${statusCode})`;
  if (typeof detail === "object") {
    detail = Object.values(detail).flat().join("; ");   // FastAPI 校验错误是数组,拼成一句
  }
  return String(detail);
}

function toError(message, statusCode) {
  const err = new Error(message);
  err.statusCode = statusCode;      // 页面据此区分 409(自进化运行中)等业务错误
  return err;
}

function authHeader() {
  const token = getToken();
  return token ? { Authorization: "Bearer " + token } : {};
}

function request(path, method = "GET", data = null) {
  const isAuthCall = path.indexOf("/api/auth/") === 0;   // 登录/登出本身不需要凭据
  return new Promise((resolve, reject) => {
    const baseUrl = getBaseUrl();
    if (!baseUrl) {
      wx.showToast({ title: "请先在登录页填写服务器地址", icon: "none" });
      reject(toError("未配置服务器地址", 0));
      return;
    }
    if (!isAuthCall) {
      warnIfExpiring();
      if (!sessionUsable()) {
        needLogin("请先登录");
        reject(toError("未登录", 401));
        return;
      }
    }
    wx.request({
      url: baseUrl + path,
      method,
      data: data || undefined,
      header: authHeader(),
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }
        const detail = detailOf(res.data, res.statusCode);
        if (res.statusCode === 401 && !isAuthCall) needLogin(detail);   // 提示语用服务端的 detail
        else wx.showToast({ title: detail.slice(0, 30), icon: "none" });
        reject(toError(detail, res.statusCode));
      },
      fail() {
        wx.showToast({ title: "网络错误,请检查服务器地址", icon: "none" });
        reject(toError("network error", 0));
      },
    });
  });
}

// 登录换取会话令牌。失败不做任何自动重试 —— 服务端对同一用户名连续失败 5 次锁定 10 分钟,
// 重试只会加重锁定;detail(含剩余锁定秒数)原样抛给登录页展示。
function login(username, password) {
  return request("/api/auth/login", "POST", { username, password }).then(out => {
    if (!out || !out.token) {
      throw new Error("登录成功但服务端未返回会话令牌,请确认后端已启用会话令牌鉴权");
    }
    saveSession(out.token, out.expires_at);
    return out;
  });
}

module.exports = {
  request, login,
  getBaseUrl, setBaseUrl,
  getToken, secondsLeft, needsRenewal, backAfterLogin,
};

// 兼容旧的具名导出(其他页面 `const { BASE_URL } = require("../utils/api.js")`):
// 它是实时值而非快照,因为服务器地址可能被用户在登录页覆盖
Object.defineProperty(module.exports, "BASE_URL", {
  get: getBaseUrl, enumerable: true, configurable: true,
});
