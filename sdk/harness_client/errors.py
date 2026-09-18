"""SDK 抛出的异常体系。

- HarnessAuthError(401 子类):令牌缺失/错误或会话过期
- HarnessAPIError:其余非 2xx 响应,携带 HTTP 状态码与服务端 detail
"""

from __future__ import annotations


class HarnessAPIError(RuntimeError):
    """服务端返回非 2xx 时抛出。status 为 HTTP 状态码,detail 为服务端错误描述。"""

    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"[{status}] {detail}")


class HarnessAuthError(HarnessAPIError):
    """401:未授权。检查 token 是否与服务端 AUTH_TOKEN 一致,或重新 login()。"""

    def __init__(self, detail: str = "未授权"):
        super().__init__(401, detail)
