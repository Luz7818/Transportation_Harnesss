# 5 分钟接入指南(INTEGRATION)

面向想要程序化接入交通分析自进化 Harness 的开发者与外部系统。
所有能力都通过一套 REST API 提供:发起分析、运行评测、一键自进化、
版本对比、Case 管理、LLM 智能层。本文给出三条接入路径:
**cURL(30 秒验证)→ Python SDK(推荐)→ 原生 HTTP(任意语言)**。

> 交互式 API 参考:服务运行时访问 `/docs`(Swagger UI)与 `/help`(网页文档中心);
> 机器可读规范:`docs/openapi.json`(可导入 Postman / Apifox)。

## 1. 服务地址与令牌

| 环境 | Base URL | 说明 |
| --- | --- | --- |
| 本地开发 | `http://127.0.0.1:8765` | `python webapp/app.py` 启动 |
| 云端(当前) | `http://47.114.37.174:8765` | 阿里云 ECS,Docker 常驻 |
| 生产(规划) | `https://<备案域名>` | Nginx + HTTPS 已预置 |

令牌双通道,二者其一即可通过鉴权:

1. **机器令牌**(推荐给脚本/CI/外部系统):服务端启动时设置环境变量
   `AUTH_TOKEN=<串>`,请求携带 `X-API-Token: <串>` 请求头;
2. **登录会话**:调 `POST /api/auth/login`(默认账号 admin/harness123),
   后续请求自动携带会话 Cookie(HttpOnly,7 天有效)。

`/api/health` 与 `/api/auth/*` 始终免鉴权,可用于拨测。
内网演示可设 `AUTH_MODE=open` 完全放行(仅限内网)。

## 2. 30 秒验证(cURL)

```bash
BASE=http://47.114.37.174:8765
TOKEN=<你的令牌>

curl -s $BASE/api/health
curl -s -H "X-API-Token: $TOKEN" $BASE/api/versions
curl -s -H "X-API-Token: $TOKEN" -H "Content-Type: application/json" \
     -d '{"version":"v2","dataset_name":"base"}' $BASE/api/analyze
```

## 3. Python SDK(推荐)

```bash
pip install ./sdk                                  # 从仓库安装(构建产物见 sdk/dist)
# 发布后可用:pip install transportation-harness-sdk
```

### 场景 A:发起一次交通分析

```python
from harness_client import TransportationHarnessClient

with TransportationHarnessClient(base_url="http://47.114.37.174:8765",
                                 token="你的令牌") as client:
    out = client.analyze(version="v2", dataset_name="base")   # 也可选 rain_peak/incident/evening_peak
    print(out["summary"])
    for seg in out["segments"]:
        print(seg["segment_id"], seg["classification"], seg["saturation"])
```

### 场景 B:运行评测并取回强类型结果

```python
result = client.run_eval(version="v2", evalset="evalset_v1")
print(f"{result.version}: {result.passed_count}/{result.total} = {result.accuracy:.1%}")
print("归档报告:", result.report_id)

for case in result.failed_cases():        # 未通过案例明细(强类型)
    print(case.case_id, case.label, [c.detail for c in case.checks if not c.passed])
```

### 场景 C:一键自进化 + 回归守护

```python
summary = client.evolve(timeout=60.0)     # 基线 → 最多 2 轮 → 归档
print(summary["best"], summary["stop_reason"])

reports = client.reports()
diff = client.compare(reports[-2]["report_id"], reports[-1]["report_id"])
print("新通过:", diff.newly_passed)
print("回归:", diff.regressed)             # 非空即应阻止合入
```

CLI 等价操作(装 SDK 后即得):

```bash
harness-client health  --base-url $BASE --token $TOKEN
harness-client eval    --version v2 --base-url $BASE --token $TOKEN
harness-client analyze --version v2 --dataset rain_peak --base-url $BASE --token $TOKEN
```

## 4. 原生 HTTP(任意语言,不用 SDK)

SDK 只是薄封装;任何语言的 HTTP 客户端按 `docs/openapi.json` 即可直接对接:

```python
import httpx                                    # 或 requests,模式相同

with httpx.Client(base_url=BASE, headers={"X-API-Token": TOKEN}) as client:
    result = client.post("/api/eval/run", json={"version": "v2"}).json()
    assert result["accuracy"] == 1.0
```

要点:所有请求/响应均为 JSON;错误统一 `{"detail": "..."}`;
鉴权失败的响应码恒为 401。

## 5. 错误码约定

| 状态码 | 含义 | 典型原因 |
| --- | --- | --- |
| 400 | 请求参数不合法 | 路径不存在于数据集 / 等级枚举外 / ID 不存在 |
| 401 | 未授权 | 令牌缺失或与 `AUTH_TOKEN` 不一致;会话过期 |
| 404 | 资源不存在 | 未知版本 / 评测集 / 报告 ID |
| 409 | 冲突 | 一键自进化正在运行(互斥锁) |
| 429 | 登录限流 | 10 分钟内连续 5 次登录失败 |
| 502 | 上游故障 | LLM 智能层调用失败(未配 Key 时为离线 Mock,不会出现) |
| 500 | 服务器内部错误 | 已捕获为 JSON `detail`,请附日志反馈 |

限流说明:登录接口内置失败锁定(5 次/10 分钟);**通用请求限流由部署侧网关
(Nginx `limit_req` 等)负责**,应用层保持无状态横向扩展友好。

## 6. OpenAPI 与代码生成

- 规范文件:仓库内 `docs/openapi.json`(OpenAPI 3.1,28 路径,按
  auth/metadata/analysis/cases/eval/reports/llm 分组),由
  `python scripts/export_openapi.py` 重新生成;
- Postman/Apifox:Import → 选择该 JSON,即可获得全部端点的可调试集合;
- 代码生成:`openapi-generator generate -i docs/openapi.json -g <语言>` 可产出
  其它语言的客户端(SDK 已覆盖 Python,无需生成)。

## 相关文档

- [docs/API.md](API.md) —— 全端点参考手册
- [docs/LLM.md](LLM.md) —— LLM 智能层设计
- [DEPLOY.md](../DEPLOY.md) —— 部署形态与公网接入
- [sdk/](../sdk/) —— Python SDK 源码与构建产物
