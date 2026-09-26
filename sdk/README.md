# transportation-harness-sdk

交通分析自进化 Harness 的官方 Python SDK(导入名 `harness_client`)。

```bash
pip install ./sdk            # 从仓库本地安装
# 或发布后:pip install transportation-harness-sdk
```

```python
from harness_client import TransportationHarnessClient

# base_url 换成你的服务地址(本地跑就是 http://127.0.0.1:8765);
# token 是服务端启动时设的 AUTH_TOKEN 那一串(仓库里不记录真实值)
with TransportationHarnessClient(base_url="http://<你的服务器地址>:8765",
                                 token="<AUTH_TOKEN 的值>") as client:
    print(client.health())
    result = client.run_eval(version="v2")          # 强类型 EvalResult
    print(result.accuracy, result.report_id)
    comparison = client.compare(result.report_id, other_report_id)
    print(comparison.regressed)                      # 回归列表,非空即阻止合入

# 没有 AUTH_TOKEN 时也可以走登录通道(SDK 自动持有会话 Cookie):
# TransportationHarnessClient(base_url="http://<你的服务器地址>:8765",
#                             username="admin", password="<你的口令>")
```

命令行:

```bash
harness-client health --base-url http://<你的服务器地址>:8765 --token <AUTH_TOKEN 的值>
harness-client eval --version v2            # 不传 --base-url/--token 时取本地默认与
                                            # HARNESS_BASE_URL / HARNESS_TOKEN 环境变量
```

完整接入文档见 [docs/INTEGRATION.md](../docs/INTEGRATION.md)。
