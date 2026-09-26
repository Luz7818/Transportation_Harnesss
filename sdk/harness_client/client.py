"""交通分析自进化 Harness 的官方 Python 客户端。

用法::

    from harness_client import TransportationHarnessClient

    with TransportationHarnessClient(base_url="http://<你的服务器地址>:8765",
                                    token="<AUTH_TOKEN 的值>") as client:
        result = client.run_eval(version="v2")
        print(result.accuracy, result.report_id)

服务端对受保护的 /api/* 认可三种凭据(X-API-Token → Bearer 会话令牌 → 会话 Cookie);
本 SDK 用其中两条:传 ``token`` 走 X-API-Token 请求头(机器客户端),
传 ``username``/``password`` 则自动登录并持有会话 Cookie(交互脚本)。
"""

from __future__ import annotations

from typing import Any

import httpx

from .errors import HarnessAPIError, HarnessAuthError
from .models import CompareResult, EvalResult

__all__ = ["TransportationHarnessClient", "HarnessAPIError", "HarnessAuthError"]


class TransportationHarnessClient:
    """REST 客户端:方法与后端端点一一对应,核心负载返回强类型模型。

    参数:
        base_url: 服务地址,如 ``http://127.0.0.1:8765``(尾斜杠会被规范化)
        token: 机器客户端令牌,与服务端 ``AUTH_TOKEN`` 环境变量一致
        username/password: 交互式登录凭据(与 token 二选一或并用)
        timeout: 单请求超时秒数;evolve 全程可能超过默认值,可按需调大
        transport: 自定义 httpx transport(测试时注入 httpx.ASGITransport)
    """

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ):
        headers = {"Accept": "application/json"}
        if token:
            headers["X-API-Token"] = token
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout, headers=headers, transport=transport,
        )
        if username and password:
            self.login(username, password)

    # -- 生命周期 ------------------------------------------------------------
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> TransportationHarnessClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- 内部 ----------------------------------------------------------------
    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        resp = self._client.request(method, path, **kwargs)
        if resp.status_code == 401:
            raise HarnessAuthError(_detail_of(resp, "未登录或会话已过期"))
        if resp.is_error:
            raise HarnessAPIError(resp.status_code, _detail_of(resp, resp.reason_phrase or "请求失败"))
        if not resp.content:
            return None
        return resp.json()

    # -- 认证与会话 ------------------------------------------------------------
    def login(self, username: str, password: str) -> dict:
        """登录并持有会话 Cookie(httpx 自动携带)。"""
        return self._request("POST", "/api/auth/login", json={"username": username, "password": password})

    def logout(self) -> dict:
        return self._request("POST", "/api/auth/logout")

    def me(self) -> dict:
        return self._request("GET", "/api/auth/me")

    def change_password(self, old_password: str, new_password: str) -> dict:
        return self._request("POST", "/api/auth/password",
                             json={"old_password": old_password, "new_password": new_password})

    # -- 元数据 ----------------------------------------------------------------
    def health(self) -> dict:
        return self._request("GET", "/api/health")

    def versions(self) -> list[dict]:
        return self._request("GET", "/api/versions")

    def datasets(self) -> list[dict]:
        return self._request("GET", "/api/datasets")

    def segments(self, dataset: str) -> dict:
        return self._request("GET", f"/api/segments/{dataset}")

    def evalsets(self) -> list[dict]:
        return self._request("GET", "/api/evalsets")

    def activity(self, limit: int = 12) -> list[dict]:
        return self._request("GET", "/api/activity", params={"limit": limit})

    # -- 交通分析 ----------------------------------------------------------------
    def analyze(self, version: str, dataset_name: str) -> dict:
        """用指定版本管线分析指定情景数据集,返回分级/指标/处置建议。"""
        return self._request("POST", "/api/analyze",
                             json={"version": version, "dataset_name": dataset_name})

    # -- Case 管理 ----------------------------------------------------------------
    def list_cases(self) -> list[dict]:
        return self._request("GET", "/api/cases")

    def get_case(self, case_id: str) -> dict:
        return self._request("GET", f"/api/cases/{case_id}")

    def create_case(self, title: str, label: str, dataset_name: str, segment: str,
                    expected_level: str, expected_saturation: float | None = None,
                    saturation_tol: float = 0.01, notes: str = "",
                    add_to_evalset: bool = True, source: str = "SDK 提交") -> dict:
        """沉淀一条 replaycase,返回 {saved, added_to_evalset, case}。"""
        payload = {"title": title, "label": label, "dataset_name": dataset_name,
                   "segment": segment, "expected_level": expected_level,
                   "saturation_tol": saturation_tol, "notes": notes,
                   "add_to_evalset": add_to_evalset, "source": source}
        if expected_saturation is not None:
            payload["expected_saturation"] = expected_saturation
        return self._request("POST", "/api/cases", json=payload)

    def delete_case(self, case_id: str) -> dict:
        return self._request("DELETE", f"/api/cases/{case_id}")

    def batch_delete_cases(self, ids: list[str]) -> dict:
        return self._request("POST", "/api/cases/batch-delete", json={"ids": ids})

    # -- 评测与自进化 ----------------------------------------------------------------
    def run_eval(self, version: str, evalset: str = "evalset_v1") -> EvalResult:
        """重放评测集并判分,返回强类型 EvalResult(含归档 report_id)。"""
        data = self._request("POST", "/api/eval/run", json={"version": version, "evalset": evalset})
        return EvalResult.from_dict(data)

    def evolve(self, evalset: str = "evalset_v1", baseline: str = "v0", timeout: float | None = None) -> dict:
        """一键自进化(基线 → 最多 2 轮 → 归档),返回逐轮摘要 dict。

        全程耗时随评测集规模增长,必要时通过 timeout 放宽本请求超时。
        """
        body = {"evalset": evalset, "baseline": baseline}
        if timeout is not None:
            return self._request("POST", "/api/evolve/run", json=body, timeout=timeout)
        return self._request("POST", "/api/evolve/run", json=body)

    # -- 报告与对比 ----------------------------------------------------------------
    def reports(self) -> list[dict]:
        return self._request("GET", "/api/reports")

    def get_report(self, report_id: str) -> dict:
        return self._request("GET", f"/api/reports/{report_id}")

    def evolutions(self) -> list[dict]:
        return self._request("GET", "/api/evolutions")

    def get_evolution(self, evolution_id: str) -> dict:
        return self._request("GET", f"/api/evolutions/{evolution_id}")

    def compare(self, a: str, b: str) -> CompareResult:
        """两份报告逐 case 差分;regressed 非空即存在回归。"""
        data = self._request("GET", "/api/compare", params={"a": a, "b": b})
        return CompareResult.from_dict(data)

    # -- LLM 智能层(可选功能,未配置 Key 时为离线 Mock)----------------------------
    def llm_status(self) -> dict:
        return self._request("GET", "/api/llm/status")

    def create_draft(self, complaint: str, dataset_name: str, segment_id: str | None = None) -> dict:
        payload: dict[str, Any] = {"complaint": complaint, "dataset_name": dataset_name}
        if segment_id:
            payload["segment_id"] = segment_id
        return self._request("POST", "/api/llm/drafts", json=payload)

    def list_drafts(self) -> list[dict]:
        return self._request("GET", "/api/llm/drafts")

    def delete_draft(self, draft_id: str) -> dict:
        return self._request("DELETE", f"/api/llm/drafts/{draft_id}")

    def confirm_draft(self, draft_id: str, **fields: Any) -> dict:
        """人工确认 LLM 草稿并沉淀为 replaycase。可选字段:title/label/expected_level/expected_saturation/notes。"""
        return self._request("POST", f"/api/llm/drafts/{draft_id}/confirm", json=fields)

    def diagnose(self, version: str = "v2", evalset: str = "evalset_v1") -> dict:
        """分析者+评审者双智能体失败诊断。"""
        return self._request("POST", "/api/llm/diagnose", json={"version": version, "evalset": evalset})


def _detail_of(resp: httpx.Response, fallback: str) -> str:
    try:
        payload = resp.json()
    except Exception:
        return fallback
    detail = payload.get("detail", fallback) if isinstance(payload, dict) else fallback
    if isinstance(detail, list):  # pydantic 校验错误 → 拼接为可读字符串
        parts = []
        for item in detail:
            if isinstance(item, dict):
                parts.append(f"{'.'.join(str(x) for x in item.get('loc', []))}: {item.get('msg', '')}")
            else:
                parts.append(str(item))
        return "; ".join(parts)
    return str(detail)
