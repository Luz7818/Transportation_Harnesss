"""线上服务只读探针:确认「部署出去的那台」还活着、且初始口令已改。

  LIVE_HEALTH_URL=http://<你的服务地址>/api/health python scripts/probe_live.py

只读 GET /api/health,断言两件事,任一不满足即退出码 1(GitHub Actions 每天跑一次,
见 .github/workflows/probe.yml;服务地址放在仓库 secret LIVE_HEALTH_URL 里,不入库):
  1. status == ok —— 服务在线;
  2. default_credentials == false —— 初始口令已改(代码侧改了、线上没动,当天就会红)。
零第三方依赖;本脚本绝不携带任何凭据,也不访问业务接口。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    url = os.getenv("LIVE_HEALTH_URL", "").strip()
    if not url:
        print("PROBE FAIL:未配置 LIVE_HEALTH_URL(部署时应写入仓库 secret,服务地址不入库)")
        return 1
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            health = json.load(resp)
    except Exception as exc:
        print(f"PROBE FAIL:线上健康检查不可达({url}):{type(exc).__name__}: {exc}")
        return 1
    problems = []
    if health.get("status") != "ok":
        problems.append(f"status={health.get('status')!r}(应为 'ok')")
    if health.get("default_credentials") is not False:
        problems.append("default_credentials 不为 false —— 初始口令未修改,"
                        "业务接口处于 403 门禁状态,请按 DEPLOY.md「凭据与首次启动」收口")
    print(f"线上版本 {health.get('app_version')},auth_mode {health.get('auth_mode')},"
          f"{health.get('case_count')} cases")
    if problems:
        print("PROBE FAIL:" + ";".join(problems))
        return 1
    print("PROBE PASS:线上服务在线,且初始口令已修改")
    return 0


if __name__ == "__main__":
    sys.exit(main())
