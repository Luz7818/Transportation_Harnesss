# 部署指南:公网访问 / 微信小程序接入

后端是标准的 FastAPI 应用,数据(cases / evalsets / reports / 数据集)全部落盘本地目录,
迁移 = 拷贝目录。以下三条路线按成本从低到高排列,按需选择。

## 凭据与首次启动(公网必做)

账密与机器令牌**必须由部署者自己提供**,服务不为任何环境准备可复述的默认值:

```bash
# 1. 生成强随机凭据(任选一种)
python -c "import secrets;print(secrets.token_urlsafe(32))"     # AUTH_TOKEN(≥16 字符,启动时强制校验)
python -c "import secrets;print(''.join(secrets.choice('abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(16)))"  # ADMIN_PASSWORD(8~64 位)

# 2. 写进服务器 .env(该文件已被 .gitignore 排除,严禁入库)
cat >> .env <<'EOF'
AUTH_MODE=login
AUTH_TOKEN=<你的强随机串>
ADMIN_PASSWORD=<你的强口令>
HOST=0.0.0.0
EOF
python webapp/app.py    # .env 在启动时自动读取
```

凭据语义(照 `webapp/auth.py` 实现,不要凭印象改):

- 启动环境里**提供了 `ADMIN_PASSWORD`** → 用它创建/轮换管理员账号,`default_credentials=false`,
  所有接口立即可用;用户名默认 `admin`,可用 `ADMIN_USER` 改;
- **未提供** `ADMIN_PASSWORD` → 随机生成一枚强口令只在控制台打印一次,且 `default_credentials=true`:
  在口令被改掉之前,业务接口对**三种凭据一律 403**,只放行 `/api/health` 与 `/api/auth/*`
  (登录、改密)。用打印的口令登录 → 看板右上角「改密」→ 门禁立即解除;
- **存量部署补收口**:线上 `auth.json` 还是默认口令状态时,在 `.env` 里加上
  `ADMIN_PASSWORD=<新口令>` 重启一次即自动轮换并翻转标记;已在界面改过口令的部署,
  环境变量会被忽略,不会覆盖;
- `AUTH_TOKEN` 短于 16 字符时服务拒绝启动(机器令牌是公网部署唯一的机器凭据,不允许弱值);
- 忘记口令:删掉 `webapp/auth.json` 重启(回到上面两条路径之一)。

其余启动配置:

- 鉴权模式 `AUTH_MODE`:`login`(默认,浏览器需登录)/ `open`(免登录,仅限内网演示);
- 受保护的 `/api/*` 认可三种凭据(任一即可):`X-API-Token: <AUTH_TOKEN>`(SDK/脚本)、
  `Authorization: Bearer <会话令牌>`(小程序;令牌取自 `POST /api/auth/login` 响应体的
  `token`,7 天有效)、`harness_session` Cookie(网页);
- `AUTH_TOKEN` 与 `ADMIN_PASSWORD`、`CORS_ORIGINS`、`HOST`/`PORT`、`SETTINGS_ENABLED` 都是
  **启动期只读一次**,改完必须重启进程(用 systemd / docker compose 重启即可);
- `CORS_ORIGINS` 指定允许的来源(默认 `*`),公网建议收窄
  (配置具体来源时才会启用带 Cookie 的跨域凭证);
- `SETTINGS_ENABLED=1` 才开启 Web 看板的「系统设置」页(在线读写 `.env`),默认关闭;
  开启后也只对**本机直连**或**已登录会话**开放,机器令牌不能用于该接口(详见 docs/API.md)。

服务端已内置的防护(无需配置):口令 PBKDF2 哈希存储、登录连续失败 5 次锁定 10 分钟、
会话 HMAC 签名 + HttpOnly Cookie、API 令牌时序安全比较、文件名白名单防路径穿越、
`.env` 写入原子替换且写前备份;初始口令未改期间业务接口整体 403 门禁、
未处理异常不向客户端回显内部细节;容器以非 root 用户运行并自带健康检查。
`webapp/auth.json` 与会话密钥、`.env` 里的令牌/密钥都已列入 .gitignore,严禁提交或外传;
**仓库与文档里不出现任何真实地址、令牌、口令**,部署时按占位符换成你自己的值。

**部署边界**:单进程文件存储 + 进程内锁,`docker compose` / systemd **只跑一个实例**;
多实例部署时锁不跨进程,评测资产一致性没有保证(需要先换数据库存储)。

## 线上探针(部署后配置一次)

> **当前状态(2026-10-06)**:线上服务已下线,每日探针工作流(`probe.yml`)已随之下撤,
> 本节内容保留作为复活部署时的配置指引。

GitHub Actions 每天只读探测一次线上 `/api/health`,断言「服务在线 + `default_credentials=false`」,
代码改了、线上没动这类漂移当天就会红。配置:仓库 Settings → Secrets and variables →
Actions → New repository secret,Name 填 `LIVE_HEALTH_URL`,Value 填
`http://<你的服务地址>/api/health`。手工触发见 Actions 页的 Live Probe → Run workflow;
本地等价命令:`LIVE_HEALTH_URL=<同上> python scripts/probe_live.py`。

## 路线 A:内网穿透演示(最快,10 分钟)

适合给老师/同学演示、小程序开发调试,不需要服务器和备案域名。

```bash
# 任选一个穿透工具,把本地 8765 映射为公网 HTTPS 地址
npx cloudflared tunnel --url http://127.0.0.1:8765      # Cloudflare 免费临时隧道
# 或:cpolar http 8765 / ngrok http 8765
```

得到形如 `https://xxx.trycloudflare.com` 的地址:
- 网页看板直接访问;
- 小程序 `config.js` 的 `BASE_URL` 填该地址,开发者工具勾选「不校验合法域名」即可真机调试。

> 注意:临时隧道地址会变、有速率限制,仅用于演示/调试,不是正式方案。

## 路线 B:云服务器(Docker + Nginx + HTTPS)—— 正式推荐

适合长期公网服务与小程序正式发布。前提:一台云服务器(阿里云/腾讯云轻量即可)、
一个已备案域名解析到服务器 IP。

```bash
# 1. 上传代码到服务器(或 git clone),然后在项目根目录:
echo "AUTH_TOKEN=你的强随机串" > .env            # 完整模板见 .env.example(全部为占位符)
docker compose up -d --build          # 服务对外监听 8765(建议改为仅 127.0.0.1,见下)

# 2. Nginx 反向代理 + 证书(certbot 自动签发续期)
sudo apt install nginx certbot python3-certbot-nginx
sudo tee /etc/nginx/sites-available/harness <<'EOF'
server {
    server_name harness.example.com;
    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        # 可选:再加一层 Basic Auth 保护网页与 API
        # auth_basic "harness"; auth_basic_user_file /etc/nginx/.htpasswd;
    }
}
EOF
sudo ln -s /etc/nginx/sites-available/harness /etc/nginx/sites-enabled/
sudo certbot --nginx -d harness.example.com     # 自动配置 HTTPS 并续期
```

> compose 里建议把 `ports` 改为 `127.0.0.1:8765:8765`,只让 Nginx 对外,安全性更好。

无 Docker 时也可用 systemd 常驻:

```ini
# /etc/systemd/system/harness.service
[Service]
WorkingDirectory=/opt/Transportation_Harnesss
Environment=AUTH_TOKEN=你的强随机串
ExecStart=/usr/bin/python3 webapp/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## PWA 生效条件

网页的 Service Worker / 安装能力**仅在安全上下文生效**:localhost 调试可用;
公网必须在完成 HTTPS(路线 B 的 certbot 步骤)后自动激活,http IP 访问时优雅降级。

## 路线 B+:交付包部署(打包机产出,目标机免 git)

在**装有 Docker 的打包机**上执行 `python packaging/build_deploy.py`,仓库根产出
`dist/TransportationHarness-deploy-<版本>.zip`:源码 + Dockerfile/compose + `.env.example`
+ 本文档 + scripts/(probe/backup 零依赖脚本) + 《部署说明》;打包机有网络/镜像缓存时
还会内含 `docker save` 的镜像 tar(目标机 `docker load` 免网络,否则在线构建)。

目标机解压后按包内《部署说明》三步走:`cp .env.example .env` 填凭据 →
`docker compose up -d --build`(含 tar 则 `docker load` + `up -d`)→ probe 验收;
本文件其余章节(凭据语义/反代/备份/监控)对交付包同样适用。

## 路线 C:免费托管平台(Render / Fly.io)

无需自己管服务器,适合小团队;免费档有休眠/限额,注意数据卷:

- **Render**:New → Web Service → 连接仓库;Build `pip install -e .`,
  Start `python webapp/app.py`;环境变量里配 `AUTH_TOKEN`;挂 Disk 到 `/app/reports`、`/app/cases`、`/app/evalsets`;
- **Fly.io**:`fly launch`(识别 Dockerfile)→ `fly deploy`;用 `fly volumes` 挂同样三个目录。

平台自带 HTTPS 域名(如 `xxx.onrender.com`),小程序开发调试可用;
**正式发布小程序仍需备案域名**(见下)。

## 微信小程序正式发布清单

1. 后端 HTTPS + 备案域名(路线 B,或路线 C 绑定自定义备案域名);
2. 小程序管理后台 → 开发设置 → `request` 合法域名 → 添加 `https://你的域名`;
3. `miniprogram/config.js`:填 `BASE_URL`(**不要再写任何令牌**,小程序走登录换会话),
   替换 `project.config.json` 的 AppID;
4. 提审前关闭「不校验合法域名」,真机回归一遍三个 Tab。

## 健康检查与监控

```bash
curl https://你的域名/api/health        # {"status":"ok","app_version":"<版本>",...,"default_credentials":false,...}
# default_credentials 必须是 false;为 true 表示初始口令未改,业务接口处于 403 门禁状态
```

UptimeRobot 等拨测服务监控 `/api/health` 即可。

## 数据备份

评测资产(cases/ evalsets/ reports/ 数据集)一键打包:

```bash
python scripts/backup.py                  # → backups/harness_backup_<时间戳>.zip
python scripts/backup.py --out /mnt/nas   # 指定输出目录
```

服务器上用 cron 每日备份(crontab -e):

```cron
0 3 * * * cd /opt/Transportation_Harnesss && /usr/bin/python3 scripts/backup.py --out /var/backups/harness
```

恢复 = 解压 zip 覆盖对应目录(容器部署注意挂载卷路径一致)。
