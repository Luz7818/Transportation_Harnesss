# API 参考手册

Transportation Harness 的全部能力通过一套 REST API 暴露,网页看板与微信小程序共用同一套接口。
本文是完整的人读参考;运行中的实例还提供:

- **文档中心(本文的网页版)**:`http://127.0.0.1:8765/help`
- **交互式 OpenAPI(Swagger)**:`http://127.0.0.1:8765/docs`,可直接在浏览器里发请求调试

约定:Base URL 为 `http://127.0.0.1:8765`;所有请求与响应均为 JSON;
错误统一返回 `{"detail": "人类可读的中文说明"}`。

## 目录

- [鉴权方式](#鉴权方式)
- [认证与会话](#认证与会话)
- [元数据](#元数据)
- [交通分析](#交通分析)
- [Case 管理](#case-管理)
- [评测与自进化](#评测与自进化)
- [报告与对比](#报告与对比)
- [LLM 智能层](#llm-智能层)
- [错误码约定](#错误码约定)
- [端到端完整示例](#端到端完整示例)
- [客户端集成](#客户端集成)

---

## 鉴权方式

三类身份由同一条中间件裁决:

| 模式 | 启用方式 | 行为 |
| --- | --- | --- |
| **login**(默认) | `AUTH_MODE=login` 或不设置 | 除 `/api/auth/*`、`/api/health` 外,所有 `/api/*` 需登录会话(HttpOnly Cookie);配置 `AUTH_TOKEN` 后也接受 `X-API-Token` 头 |
| **open** | `AUTH_MODE=open` | 全部放行,以 `demo` 身份进入工作台。**仅限内网演示** |
| **令牌** | 启动时 `AUTH_TOKEN=<强随机串>` | 机器客户端(小程序/脚本)以 `X-API-Token: <串>` 请求头访问 |

安全内建:口令 PBKDF2 哈希(12 万次迭代)、登录连续失败 5 次锁定 10 分钟、HMAC 签名会话(7 天)、
令牌时序安全比较、文件名白名单防路径穿越。

```bash
# 浏览器会话方式:登录并保存 Cookie
curl -c cookies.txt -X POST http://127.0.0.1:8765/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"harness123"}'
curl -b cookies.txt http://127.0.0.1:8765/api/cases

# 机器客户端方式:令牌头
curl -H "X-API-Token: <你的令牌>" http://127.0.0.1:8765/api/health
```

---

## 认证与会话

### POST /api/auth/login — 登录

公开接口。连续失败 5 次锁定 10 分钟。

```jsonc
// 请求
{"username": "admin", "password": "harness123"}
// 200:同时 Set-Cookie: harness_session=... (HttpOnly, 7 天)
{"ok": true, "username": "admin"}
```

错误:`401` 用户名或密码错误;`429` 失败次数过多已锁定(附剩余秒数)。

### POST /api/auth/logout — 登出

清除会话 Cookie,返回 `{"ok": true}`。

### GET /api/auth/me — 当前用户

公开接口,login 模式未登录返回 `401`;open 模式未登录返回 `{"username":"demo"}`。

```jsonc
{"username": "admin"}
```

### POST /api/auth/password — 修改密码

需登录。修改成功后重签会话,当前登录不中断。

```jsonc
// 请求
{"old_password": "harness123", "new_password": "new-pass-2026"}   // 新密码 6~64 位
// 200
{"ok": true}
```

错误:`400` 原密码不正确 / 新密码长度不符。

---

## 元数据

### GET /api/health — 健康检查

公开接口,适合 UptimeRobot 等拨测。

```jsonc
{
  "status": "ok",
  "auth_mode": "login",
  "default_credentials": true,   // true = 仍在使用默认口令,应尽快修改
  "versions": ["v0", "v1", "v2"],
  "case_count": 16, "evalset_count": 2, "report_count": 3
}
```

### GET /api/versions — 管线版本与 CHANGELOG

```jsonc
[{"version": "v1", "name": "算法修正", "changes": ["拥堵分级改为以饱和度 V/C 为主…", "…"]}]
```

### GET /api/datasets — 情景数据集列表

```jsonc
[{"name": "rain_peak", "description": "雨天早高峰…",
  "scenario": {"tag": "雨天早高峰", "insight": "通行能力 ×0.85、车速普降…"}}]
```

内置:`base` 常规早高峰 / `rain_peak` 雨天 / `incident` 事故占道 / `evening_peak` 晚高峰 /
`missing_volume` 缺失数据 / `empty` 空数据。

### GET /api/segments/{dataset} — 数据集内路段列表

供沉淀 case 时下拉选择。

```jsonc
{"dataset": "base", "segments": [{"segment_id": "S-01", "name": "城东大道", "volume": 3000, "speed": 45}]}
```

错误:`400` 非法数据集名;`404` 数据集不存在。

### GET /api/activity — 最近动态(统一时间流)

case 沉淀、评测运行、自进化与 LLM 草稿聚合为倒序 feed,可选 `?limit=12`(1~50)。

```jsonc
[{"ts": "2026-09-16T03:28:47", "kind": "eval",    // case | eval | evolve | draft
  "title": "评测 v2 → 100.0%", "detail": "13/13 通过 · evalset_v1",
  "tag": "v2", "ref": "report_v2_20260916T032847"}]
```

### GET /api/evalsets — 评测集清单列表

```jsonc
[{"evalset_id": "evalset_v1", "description": "由 8 月底线上反馈沉淀的 13 条 replaycase 组成",
  "created_at": "2026-08-31", "case_count": 13}]
```

---

## 交通分析

### POST /api/analyze — 用指定版本分析指定数据集

```jsonc
// 请求
{"version": "v2", "dataset_name": "rain_peak"}
```

响应 200(所有版本管线的统一输出结构):

```jsonc
{
  "version": "v2",
  "segments": [{
    "segment_id": "S-02", "name": "学府路",
    "classification": "拥堵",        // 畅通|基本畅通|缓行|拥堵|严重拥堵|数据缺失
    "saturation": 0.91,              // V/C,2 位小数;数据缺失时为 null
    "delay_index": 0.64, "speed_ratio": 0.36,
    "status": "ok", "volume": 3100
  }],
  "congested_segments": ["S-05", "S-02"],   // 按饱和度降序
  "global_congestion_index": 0.8213,        // 流量加权;无有效数据时为 null
  "recommendations": [{"segment_id": "S-02", "text": "学府路:建议优化信号配时…"}],
  "summary": "共分析 10 个路段(有效 10 个,数据缺失 0 个)…"
}
```

错误:`400` 非法数据集名;`404` 未知版本或数据集。

---

## Case 管理

### POST /api/cases — 沉淀 replaycase 并加入评测集

case_id 自动递增生成;「保存文件 + 加入评测集清单」是同一把锁内的原子操作。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `title` | str | 1~80 字符 | 坏例标题 |
| `label` | str | 1~20 字符 | 失败标签(可自建新标签) |
| `dataset_name` | str | 须存在 | 复现所需数据集 |
| `segment` | str | 须在该数据集内 | 路段 ID |
| `expected_level` | str | 六级枚举 | 期望拥堵等级 |
| `expected_saturation` | float? | 0~3,可空 | 期望饱和度(可选,追加 metric 检查) |
| `saturation_tol` | float | 0.0001~0.5,默认 0.01 | 饱和度容差 |
| `notes` | str | ≤200 字符 | 反馈原文 / 复现步骤 |
| `add_to_evalset` | bool | 默认 true | 是否同时加入 evalset_v1 |

```jsonc
// 请求
{"title": "学府路应判为拥堵而非严重拥堵", "label": "阈值错误",
 "dataset_name": "base", "segment": "S-02",
 "expected_level": "拥堵", "expected_saturation": 0.91,
 "notes": "用户点踩:该路段 V/C 已超 0.9"}
// 200
{"saved": "cases/阈值错误/rc-0015.json", "added_to_evalset": true, "case": {"case_id": "rc-0015", "…": "…"}}
```

错误:`400` 字段校验失败;`404` 数据集不存在。

### GET /api/cases — 全部 replaycase

返回 ReplayCase 数组(按 case_id 排序):

```jsonc
[{"case_id": "rc-0001", "title": "学府路(V/C 0.91)被按车速误判为「严重拥堵」",
  "label": "阈值错误", "dataset_name": "base", "source": "线上点踩",
  "created_at": "2026-08-31T00:39:00", "notes": "…",
  "checks": [
    {"type": "classify", "segment": "S-02", "expected": "拥堵"},
    {"type": "metric", "segment": "S-02", "field": "saturation", "expected": 0.91, "tol": 0.01}
  ]}]
```

checks 的 `type` 取值:

| type | 语义 | 关键字段 |
| --- | --- | --- |
| `classify` | 某路段拥堵等级应等于期望 | `segment`, `expected` |
| `metric` | 指标容差内近似相等;`segment` 缺省表示全局字段 | `segment?`, `field`, `expected`, `tol` |
| `no_crash` | 管线必须正常返回不抛异常 | — |
| `recommendations` | 每个拥堵/严重拥堵路段必须有处置建议 | — |
| `congested_empty` | 拥堵路段列表应为空(空数据降级) | — |
| `conclusion_keyword` | 结论文本须覆盖关键词(启发式 judge,可替换为 LLM) | `keywords[]` |

### DELETE /api/cases/{case_id} — 删除 case

从磁盘删除并同时从**所有**评测集清单移除(已归档报告不受影响)。

```jsonc
// 200
{"deleted": "rc-0015"}
```

错误:`404` case 不存在。

---

## 评测与自进化

### POST /api/eval/run — 单版本评测并归档报告

```jsonc
// 请求
{"version": "v2", "evalset": "evalset_v1"}
```

响应 200(EvalResult),同时归档 `reports/report_<版本>_<时间>.json`:

```jsonc
{
  "report_id": "report_v2_20260915T021603",
  "version": "v2", "evalset_id": "evalset_v1", "timestamp": "2026-09-15T02:16:03",
  "total": 13, "passed_count": 13, "accuracy": 1.0,
  "label_stats": {"阈值错误": {"passed": 4, "total": 4}},
  "results": [{"case_id": "rc-0001", "title": "…", "label": "阈值错误", "version": "v2",
               "passed": true, "score": 1.0, "error": null,
               "checks": [{"type": "classify", "target": "S-02", "expected": "拥堵",
                           "actual": "拥堵", "passed": true, "detail": "期望「拥堵」,实际「拥堵」"}],
               "duration_ms": 1.8}],
  "duration_ms": 21.4
}
```

错误:`404` 未知版本或评测集;`400` 评测集引用了不存在的 case。

### POST /api/evolve/run — 一键自进化

基线 → 逐登记版本验证(提升且无回归检查,收益 <5% 或全部通过即提前停止)→ 归档
Markdown + JSON 报告。请求体可省略(兼容旧客户端,默认 baseline=v0);同一时刻仅允许一个循环。

```jsonc
// 请求(可选):baseline 传当前最佳版本即可增量验证新登记的版本
{"evalset": "evalset_scenario_rain", "baseline": "v2"}
```

响应 200(自进化摘要,同时归档 `reports/evolution_*.json`):

```jsonc
{
  "evolution_id": "evolution_20260915_021603",
  "evalset_id": "evalset_v1", "total_cases": 13,
  "baseline": {"version": "v0", "accuracy": 0.0769, "passed_count": 1, "total": 13,
               "failures_by_label": {"阈值错误": ["rc-0001 学府路…"]}},
  "rounds": [{"round": 1, "version": "v1", "version_name": "算法修正", "changes": ["…"],
              "accuracy": 0.8462, "improvement": 0.7692,
              "newly_passed": ["rc-0001"], "regressed": [], "remaining_failures": {}}],
  "pending_versions": [],              // 因单轮上限(EVOLVE_MAX_ROUNDS,默认 2)未验证的版本
  "stop_reason": "评测集已全部通过", "iterations_used": 2,
  "best": {"version": "v2", "accuracy": 1.0, "passed_count": 13, "total": 13},
  "md_report": "reports/report_evolution_20260915_021603.md",
  "timestamp": "20260915_021603"
}
```

错误:`404` 未知基线版本或评测集;`409` 自进化循环正在运行中。

### GET /api/cases/{case_id} — 单条 replaycase 详情

含完整判分规则 checks。错误:`404` case 不存在。

---

## 报告与对比

### GET /api/reports — 报告列表(时间倒序)

```jsonc
[{"report_id": "report_v2_20260915T021603", "version": "v2", "evalset_id": "evalset_v1",
  "accuracy": 1.0, "passed_count": 13, "total": 13, "timestamp": "2026-09-15T02:16:03"}]
```

### GET /api/reports/{report_id} — 单份报告详情

返回与 `/api/eval/run` 相同的完整 EvalResult 结构。错误:`404` 报告不存在。

### GET /api/evolutions — 自进化运行记录(时间倒序)

每次自进化归档一条 `reports/evolution_*.json`,此处返回其摘要列表,供看板时间线回放。

### GET /api/evolutions/{evolution_id} — 单次自进化完整记录

错误:`404` 记录不存在。

### GET /api/compare?a=&b= — 两份报告逐 case 差分

回归验证的核心接口:

```jsonc
{
  "a": {"report_id": "report_v0_…", "version": "v0", "accuracy": 0.0769},
  "b": {"report_id": "report_v2_…", "version": "v2", "accuracy": 1.0},
  "newly_passed": ["rc-0001", "rc-0002"],
  "regressed": [],
  "rows": [{"case_id": "rc-0001", "title": "…", "label": "阈值错误",
            "a_passed": false, "b_passed": true, "a_score": 0.5, "b_score": 1.0}]
}
```

评测集扩充后对比旧报告时,仅两轮共有的 case 参与回归判定。

---

## LLM 智能层

LLM 只接在闭环的薄弱环节上(坏例沉淀加速 / 结论文本评分 / 失败诊断),全部带 Schema
校验、人工确认与调用审计。未配置 `LLM_API_KEY` 时自动降级为离线确定性 Mock。
七维设计(Runtime / Context & Memory / Tool & Workflow / Human-in-the-loop /
Multi-Agent / Evaluation & Governance / 工程化)见 [LLM.md](LLM.md)。

### GET /api/llm/status — Runtime 状态与调用审计

```jsonc
{"kind": "mock", "model": "mock-deterministic", "configured": false,
 "env": ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"], "cache_count": 12,
 "recent_runs": [{"ts": "…", "purpose": "judge", "elapsed_ms": 0.8,
                  "cache_hit": false, "usage": {}}]}
```

### POST /api/llm/drafts — 坏例沉淀助手(草稿,pending)

```jsonc
// 请求
{"complaint": "用户点踩:学府路 V/C 0.91 被误判为缓行,应为拥堵",
 "dataset_name": "base", "segment_id": "S-02"}     // segment_id 可省,助手自动定位
// 200:仅生成草稿,不入库 —— 必须人工确认
{"draft_id": "draft-0001", "status": "pending", "title": "…", "label": "阈值错误",
 "expected_level": "拥堵", "expected_saturation": 0.91,
 "rationale": "…", "llm": {"model": "…", "kind": "…", "purpose": "draft"}}
```

错误:`400` 输入或模型输出未过校验;`404` 数据集不存在;`502` LLM 调用失败。

### POST /api/llm/drafts/{id}/confirm — 人工确认草稿 → 正式 replaycase

请求体可携带编辑覆盖(`title` / `label` / `expected_level` / `expected_saturation` / `notes`,
均可省略即沿用草稿值)。确认后走与手工沉淀**完全相同**的校验与落盘路径,并自动加入评测集。

```jsonc
// 200
{"saved": "cases/阈值错误/rc-0015.json", "added_to_evalset": true,
 "case": {"…": "…"}, "draft_id": "draft-0001"}
```

错误:`400` 字段校验失败(人工编辑也不能绕过);`404` 草稿不存在;`409` 草稿已处理。

### GET /api/llm/drafts — 草稿列表 · DELETE /api/llm/drafts/{id} — 丢弃草稿

### POST /api/llm/diagnose — 失败诊断(分析者 + 评审者双智能体)

```jsonc
// 请求
{"version": "v2", "evalset": "evalset_v1"}
// 200
{"items": [{"label": "阈值错误", "root_cause": "…", "suggestions": ["…"],
            "affected_cases": ["rc-0001"]}],
 "reviewer_notes": "评审者复核意见…",
 "meta": {"version": "v2", "accuracy": 1.0, "total": 13, "passed": 13,
          "failure_count": 0, "model": "…"}}
```

结果仅供参考,不自动改动任何资产;`affected_cases` 经防幻觉过滤,只含真实失败的 case。

**LLM-as-Judge**:在 replaycase 的 checks 中声明
`{"type": "conclusion_quality", "min_score": 0.8}`,评测时由 LLM 按评分细则
(覆盖性/可执行性/简洁性)给结论文本打分,分数与理由随报告持久化可复核;
LLM 故障时该检查降级为"未通过 + 原因可见",不影响整轮评测。

---

## 错误码约定

所有错误统一为 `{"detail": "人类可读的中文说明"}`。

| 状态码 | 含义 | 典型场景 |
| --- | --- | --- |
| `400` | 参数校验失败 | 标题超长、路段不在数据集、期望等级非法、名称含路径字符 |
| `401` | 未登录或会话过期 | login 模式缺少 Cookie / 令牌;口令错误 |
| `404` | 资源不存在 | 未知版本 / 数据集 / 评测集 / 报告 / case |
| `409` | 冲突 | 自进化循环正在运行,重复触发 |
| `429` | 请求被限流 | 登录连续失败 5 次,账号锁定 10 分钟 |
| `502` | 上游调用失败 | LLM 端点不可用或输出未过校验(智能层接口) |
| `500` | 服务器内部错误 | 未预期异常,响应含异常类型便于排查 |

---

## 端到端完整示例

```bash
BASE=http://127.0.0.1:8765
H="X-API-Token: <你的令牌>"
J="Content-Type: application/json"

# 1) 沉淀一条 badcase(自动加入评测集)
curl -s -X POST $BASE/api/cases -H "$H" -H "$J" -d '{
  "title":"学府路应判为拥堵而非严重拥堵","label":"阈值错误",
  "dataset_name":"base","segment":"S-02","expected_level":"拥堵"}'

# 2) 对 v2 跑单版本评测
curl -s -X POST $BASE/api/eval/run -H "$H" -H "$J" \
     -d '{"version":"v2","evalset":"evalset_v1"}'

# 3) 一键自进化(基线 → 最多 2 轮 → 归档)
curl -s -X POST $BASE/api/evolve/run -H "$H" -H "$J" -d '{"evalset":"evalset_v1"}'

# 4) 取两份报告做回归差分(报告 ID 从 GET /api/reports 获取)
curl -s "$BASE/api/compare?a=report_v1_…&b=report_v2_…" -H "$H"
```

## 客户端集成

**Python(requests)**:

```python
import requests

BASE = "http://127.0.0.1:8765"
H = {"X-API-Token": "<你的令牌>"}

# 用 v2 分析雨天情景
out = requests.post(f"{BASE}/api/analyze", headers=H, timeout=10,
                    json={"version": "v2", "dataset_name": "rain_peak"}).json()
print(out["summary"])

# 跑一轮完整自进化
summary = requests.post(f"{BASE}/api/evolve/run", headers=H, timeout=120,
                        json={"evalset": "evalset_v1"}).json()
print(summary["best"], summary["stop_reason"])
```

**微信小程序**:修改 `miniprogram/config.js` 的 `BASE_URL` 与 `TOKEN`(与服务端 `AUTH_TOKEN` 一致),
`utils/api.js` 自动携带 `X-API-Token` 头。正式发布需 HTTPS + 备案域名,清单见 [DEPLOY.md](../DEPLOY.md)。

## 相关文档

- [README](../README.md) — 项目总览、架构图与快速开始
- [ARCHITECTURE](../ARCHITECTURE.md) — 架构分层与设计决策
- [DEPLOY](../DEPLOY.md) — 公网部署三条路线与小程序发布清单
- 运行实例的[文档中心](http://127.0.0.1:8765/help)与[交互式 API](http://127.0.0.1:8765/docs)
