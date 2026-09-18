/* 交通分析自进化 Harness · Service Worker
 *
 * 缓存策略:
 *   - 导航请求(页面):network-first,失败回退缓存的壳(/ 或 /help)
 *   - GET /static/*:stale-while-revalidate(缓存优先,后台静默更新)
 *   - GET /api/*:network-first,成功写入 api 缓存;离线时回退上次数据
 *   - /api/auth/* 与一切非 GET:永不过 SW,直连网络
 *
 * 更新:改版本号 → install 阶段 skipWaiting → 前端提示「新版本已就绪,刷新生效」。
 * 安全上下文:Service Worker 仅在 localhost / HTTPS 下注册;
 * 公网 http IP 访问时前端注册代码会优雅降级,页面功能不受影响。
 */

"use strict";

const SHELL_CACHE = "harness-shell-v1";
const API_CACHE = "harness-api-v1";

const SHELL_ASSETS = [
  "/",
  "/help",
  "/static/assets/icon.svg",
  "/static/assets/icon-192.png",
  "/static/assets/icon-512.png",
  "/static/assets/icon-maskable-512.png",
  "/static/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== SHELL_CACHE && k !== API_CACHE)
            .map((k) => caches.delete(k)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") self.skipWaiting();
});

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const network = fetch(request)
    .then((resp) => {
      if (resp.ok) cache.put(request, resp.clone());
      return resp;
    })
    .catch(() => cached);
  return cached || network;
}

async function networkFirst(request, cacheName, fallbackUrl) {
  const cache = await caches.open(cacheName);
  try {
    const resp = await fetch(request);
    if (resp.ok) cache.put(request, resp.clone());
    return resp;
  } catch (err) {
    const cached = await cache.match(request);
    if (cached) return cached;
    if (fallbackUrl) {
      const shell = await caches.open(SHELL_CACHE);
      const shellResp = await shell.match(fallbackUrl);
      if (shellResp) return shellResp;
    }
    throw err;
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;                      // 写操作永远直连
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;           // 跨域不拦截
  if (url.pathname.startsWith("/api/auth/")) return;         // 登录态相关直连

  if (request.mode === "navigate") {
    const fallback = url.pathname === "/help" ? "/help" : "/";
    event.respondWith(networkFirst(request, SHELL_CACHE, fallback));
    return;
  }
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(staleWhileRevalidate(request, SHELL_CACHE));
    return;
  }
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(networkFirst(request, API_CACHE));
  }
});
