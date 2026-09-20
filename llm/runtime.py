"""LLM Runtime:统一的模型访问层 —— 配置、调用、结构化输出、缓存与审计的接缝在这里。

设计原则(详见 docs/LLM.md):
- 零 SDK 依赖:直接对任意 OpenAI 兼容端点发 HTTP(stdlib urllib),OpenAI/DeepSeek/vLLM/Ollama 通吃;
- 离线可复现:未配置 LLM_API_KEY 时自动降级为确定性 Mock(``MockLLMRuntime``),
  整条评测闭环不依赖网络、不产生费用,CI 与课堂演示照常运行;
- 一切可审计:每次调用写审计日志(用途/模型/耗时/token/缓存命中),
  响应按「模型+用途+提示词」哈希缓存,同输入同输出。

环境变量:
  LLM_BASE_URL  OpenAI 兼容端点,如 https://api.deepseek.com/v1、http://localhost:11434/v1
  LLM_API_KEY   对应密钥(未设置即进入 Mock 模式;无鉴权端点填 EMPTY 即可)
  LLM_MODEL     模型名,默认 gpt-4o-mini
  LLM_EXTRA_BODY 可选,JSON 对象字符串,原样并入请求体(如 {"enable_thinking": false})
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from llm import store


class LLMError(RuntimeError):
    """LLM 调用或输出解析失败。"""


@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    timeout: float = 30.0
    temperature: float = 0.2
    extra_body: dict = field(default_factory=dict)


def load_config() -> LLMConfig | None:
    """从环境变量读取配置;未配置完整(base_url + api_key)返回 None → 使用 Mock。

    LLM_EXTRA_BODY(JSON 对象字符串)原样并入请求体,用于供应商/模型专属参数,
    如 {"enable_thinking": false} 关闭 Qwen3 思考模式;非法 JSON 直接报错,失败可见。
    """
    base = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
    key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    if not (base and key):
        return None
    extra: dict = {}
    raw = os.getenv("LLM_EXTRA_BODY", "").strip()
    if raw:
        try:
            extra = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM_EXTRA_BODY 不是合法 JSON:{exc}") from exc
        if not isinstance(extra, dict):
            raise LLMError("LLM_EXTRA_BODY 必须是 JSON 对象")
    return LLMConfig(base_url=base, api_key=key, model=model, extra_body=extra)


def _parse_json_content(content: str) -> dict:
    """解析模型输出为 JSON;容忍 ```json 代码围栏。"""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("`" * 3, 2)[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型输出不是合法 JSON:{exc}") from exc
    if not isinstance(data, dict):
        raise LLMError("模型输出 JSON 不是对象")
    return data


class LLMRuntime:
    """真实端点运行时:OpenAI 兼容 chat/completions,强制 JSON 输出,带缓存与审计。"""

    def __init__(self, config: LLMConfig):
        self.config = config

    @property
    def model(self) -> str:
        return self.config.model

    @property
    def kind(self) -> str:
        return "openai-compatible"

    def complete_json(self, *, purpose: str, system: str, user: str,
                      max_chars: int = 6000) -> dict:
        user = user[:max_chars]  # 上下文预算:超长输入截断,控制单次成本上限
        key = store.cache_key(self.config.model, purpose, system, user)
        cached = store.cache_get(key)
        if cached is not None:
            store.journal_append(purpose, self.config.model, 0.0, {}, cache_hit=True)
            return cached

        body = {
            "model": self.config.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": self.config.temperature,
            "response_format": {"type": "json_object"},
        }
        body.update(self.config.extra_body)  # 模型专属参数(如 enable_thinking)原样透传
        payload = json.dumps(body).encode("utf-8")

        last_err: Exception | None = None
        for _attempt in range(2):  # 瞬时网络/5xx 重试一次
            t0 = time.perf_counter()
            try:
                req = urllib.request.Request(
                    self.config.base_url + "/chat/completions", data=payload,
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {self.config.api_key}"})
                with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                    out = json.loads(resp.read().decode("utf-8"))
                data = _parse_json_content(out["choices"][0]["message"]["content"])
                usage = {k: out.get("usage", {}).get(k) for k in
                         ("prompt_tokens", "completion_tokens", "total_tokens")}
                store.cache_put(key, data)
                store.journal_append(purpose, self.config.model,
                                     (time.perf_counter() - t0) * 1000, usage, cache_hit=False)
                return data
            except (urllib.error.URLError, TimeoutError, OSError, KeyError,
                    json.JSONDecodeError, LLMError) as exc:
                last_err = exc
                time.sleep(0.5)
        raise LLMError(f"LLM 调用失败(重试 1 次后):{last_err}") from last_err


class MockLLMRuntime:
    """离线确定性替身:不联网、零成本、输出完全由输入决定。

    Mock 的价值不是"假装调用了模型",而是让 LLM 工作流的**编排结构**
    (上下文组装 → 结构化输出 → 校验 → 人工确认 → 落盘)在不配 Key 时也
    完整可演示、可测试;配置 Key 后仅替换 complete_json 的实现,其余零改动。
    """

    model = "mock-deterministic"
    kind = "mock"

    def complete_json(self, *, purpose: str, system: str, user: str,
                      max_chars: int = 6000) -> dict:
        from llm import mocks

        user = user[:max_chars]
        t0 = time.perf_counter()
        data = mocks.render(purpose, user)
        store.journal_append(purpose, self.model, (time.perf_counter() - t0) * 1000,
                             {"estimated_prompt_tokens": len(user) // 2}, cache_hit=False)
        return data


_RUNTIME: LLMRuntime | MockLLMRuntime | None = None


def get_runtime() -> LLMRuntime | MockLLMRuntime:
    """进程级单例;配置只在首次调用时读取(测试可用 reset_runtime() 重置)。"""
    global _RUNTIME
    if _RUNTIME is None:
        config = load_config()
        _RUNTIME = LLMRuntime(config) if config else MockLLMRuntime()
    return _RUNTIME


def reset_runtime() -> None:
    global _RUNTIME
    _RUNTIME = None


def status() -> dict:
    runtime = get_runtime()
    return {
        "kind": runtime.kind,
        "model": runtime.model,
        "configured": runtime.kind != "mock",
        "env": ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_EXTRA_BODY"],
        "cache_count": store.cache_count(),
        "recent_runs": store.journal_tail(5),
    }
