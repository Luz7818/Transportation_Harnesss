# Transportation Harness 私有化部署说明

单机/服务器的最短部署路径。前提:Docker(含 compose 插件)、8765 端口空闲;
若包内不含镜像 tar,还需能访问 Docker Hub(或已配置镜像加速)。

## 1. 部署与验收

1. 解压本包,进入 `deploy/` 目录;
2. 准备凭据:`cp .env.example .env`,编辑 `.env` 至少设置
   `AUTH_TOKEN=<≥16 位强随机串>`(机器客户端令牌,公网必设)与
   `ADMIN_PASSWORD=<你的强口令>`(初始管理员口令,提供即视为已设置);
3. 启动:包内**含镜像 tar** 时 `docker load -i transportation-harness-<版本>.tar`
   后 `docker compose up -d`(免网络);**不含 tar** 时
   `docker compose up -d --build`(在线构建);
4. 验收:`curl http://127.0.0.1:8765/api/health` 应返回 `"status":"ok"` 且
   `"default_credentials":false`;装有 Python 的机器也可
   `LIVE_HEALTH_URL=http://127.0.0.1:8765/api/health python scripts/probe_live.py`;
5. 浏览器打开 `http://<主机>:8765`,用 `.env` 里的 ADMIN_PASSWORD 登录。

## 2. 日常运维

- **数据卷**:cases/ evalsets/ reports/ pipeline/data/ drafts/ llm_cache/ 相对
  本目录落盘,容器升级/重建不丢评测资产;
- **备份**:`python scripts/backup.py --out <目录>`(cron 示例见 docs/DEPLOY.md);
- **升级**:解压新版本包覆盖(数据卷目录不动)→ 含 tar 则 `docker load` 新镜像,
  然后 `docker compose up -d --build`;镜像版本号随包升级,compose 已对号;
- **安全建议**:生产环境把 docker-compose.yml 的 ports 改为
  `"127.0.0.1:8765:8765"`,由 Nginx 反代 + HTTPS 对外(步骤见 docs/DEPLOY.md 路线 B);
- 凭据语义、CORS、小程序接入、Render/Fly.io 托管等完整说明见 `docs/DEPLOY.md`。
