# 部署指南:公网访问 / 微信小程序接入

后端是标准的 FastAPI 应用,数据(cases / evalsets / reports / 数据集)全部落盘本地目录,
迁移 = 拷贝目录。以下三条路线按成本从低到高排列,按需选择。

## 前置:安全配置(公网必做)

```bash
# 1. 生成强随机令牌(PowerShell)
-join ((48..57) + (97..122) | Get-Random -Count 32 | % {[char]$_})

# 2. 启动时注入(登录模式 + 机器客户端令牌)
AUTH_MODE=login AUTH_TOKEN=<上面生成的串> python webapp/app.py
```

- 鉴权模式 `AUTH_MODE`:`login`(默认,浏览器需登录,首次账号 admin/harness123,
  登录后请立即修改;可用 `ADMIN_USER`/`ADMIN_PASSWORD` 覆盖初始口令)/
  `open`(免登录,仅限内网演示);
- `AUTH_TOKEN` 供机器客户端(小程序/脚本)以 `X-API-Token` 请求头访问,浏览器登录会话
  与令牌二者其一通过即可;
- `CORS_ORIGINS` 指定允许的来源(默认 `*`),公网建议收窄
  (配置具体来源时才会启用带 Cookie 的跨域凭证)。

服务端已内置的防护(无需配置):口令 PBKDF2 哈希存储、登录连续失败 5 次锁定 10 分钟、
会话 HMAC 签名 + HttpOnly Cookie、API 令牌时序安全比较、文件名白名单防路径穿越;
容器以非 root 用户运行并自带健康检查。`webapp/auth.json` 含口令哈希与会话密钥,
已列入 .gitignore,严禁提交或外传。

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
echo "AUTH_TOKEN=你的强随机串" > .env
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

## 路线 C:免费托管平台(Render / Fly.io)

无需自己管服务器,适合小团队;免费档有休眠/限额,注意数据卷:

- **Render**:New → Web Service → 连接仓库;Build `pip install -r requirements.txt`,
  Start `python webapp/app.py`;环境变量里配 `AUTH_TOKEN`;挂 Disk 到 `/app/reports`、`/app/cases`、`/app/evalsets`;
- **Fly.io**:`fly launch`(识别 Dockerfile)→ `fly deploy`;用 `fly volumes` 挂同样三个目录。

平台自带 HTTPS 域名(如 `xxx.onrender.com`),小程序开发调试可用;
**正式发布小程序仍需备案域名**(见下)。

## 微信小程序正式发布清单

1. 后端 HTTPS + 备案域名(路线 B,或路线 C 绑定自定义备案域名);
2. 小程序管理后台 → 开发设置 → `request` 合法域名 → 添加 `https://你的域名`;
3. `miniprogram/config.js`:填 `BASE_URL` 与 `TOKEN`,替换 `project.config.json` 的 AppID;
4. 提审前关闭「不校验合法域名」,真机回归一遍三个 Tab。

## 健康检查与监控

```bash
curl https://你的域名/api/health        # {"status":"ok","app_version":"1.5.0",...}
# 令牌开启后:
curl -H "X-API-Token: <token>" https://你的域名/api/health
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
