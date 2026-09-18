# transportation-harness-sdk

交通分析自进化 Harness 的官方 Python SDK(导入名 `harness_client`)。

```bash
pip install ./sdk            # 从仓库本地安装
# 或发布后:pip install transportation-harness-sdk
```

```python
from harness_client import TransportationHarnessClient

with TransportationHarnessClient(base_url="http://47.114.37.174:8765",
                                 token="your-token") as client:
    print(client.health())
    result = client.run_eval(version="v2")          # 强类型 EvalResult
    print(result.accuracy, result.report_id)
    comparison = client.compare(result.report_id, other_report_id)
    print(comparison.regressed)                      # 回归列表,非空即阻止合入
```

命令行:

```bash
harness-client health --base-url http://47.114.37.174:8765 --token <TOKEN>
harness-client eval --version v2
```

完整接入文档见 [docs/INTEGRATION.md](../docs/INTEGRATION.md)。
