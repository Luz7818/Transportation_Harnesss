// 使用说明:把本文件**复制一份**并重命名为同目录的 `config.js`(小程序没有构建期环境变量,
// `utils/api.js` 用 `require("../config.js")` 读取;该文件已被根目录 .gitignore 忽略,不会入库)。
//
// 只需要填服务器地址,**不要再往这里写任何令牌**:
// 小程序包会分发到用户手机上,打进包里的常量等于公开,历史上的静态机器令牌就是这么泄漏的。
// 现在的鉴权方式是用户在 `pages/login` 用管理员分配的账号口令调 `POST /api/auth/login`,
// 换回一个 7 天有效的会话令牌存在手机 storage 里,请求时以 `Authorization: Bearer <令牌>` 发出。
//
// 开发调试:微信开发者工具勾选「不校验合法域名」即可用 http + 局域网地址;
// 正式发布:必须 HTTPS + 已备案域名,并在小程序后台配置 request 合法域名(见 README.md)。
module.exports = {
  BASE_URL: "http://<你的服务器地址>:8765",
};
