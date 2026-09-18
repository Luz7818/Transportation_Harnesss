"""transportation-harness-sdk:交通分析自进化 Harness 的官方 Python SDK。

快速开始::

    from harness_client import TransportationHarnessClient

    with TransportationHarnessClient(base_url="http://127.0.0.1:8765",
                                     token="your-token") as client:
        print(client.health())
        result = client.run_eval(version="v2")
        print(result.accuracy, result.report_id)

接入文档:docs/INTEGRATION.md
"""

from .client import TransportationHarnessClient
from .errors import HarnessAPIError, HarnessAuthError
from .models import CaseResult, CheckResult, CompareResult, CompareRow, EvalResult

__version__ = "1.5.0"

__all__ = [
    "TransportationHarnessClient",
    "HarnessAPIError",
    "HarnessAuthError",
    "EvalResult",
    "CaseResult",
    "CheckResult",
    "CompareResult",
    "CompareRow",
    "__version__",
]
