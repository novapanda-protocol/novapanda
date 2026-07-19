# mqtt_iot（示例）

展示 **work_fn** 型适配器：传感器摘要 → deliverable，经 `ProviderAdapter` 交付。

```python
from novapanda.surfaces import ProviderAdapter
from adapters.mqtt_iot.plugin import build_deliverable

# client = NovaPandaClient(...)  # provider identity
ProviderAdapter(client, build_deliverable).fulfill(exchange_id)
```

生产：在 `build_deliverable` 内订阅 MQTT，或由边缘 Agent 填 `request["sensor"]`。  
勿把设备运行态写成 Exchange `state`（见 NP-LITE / lite-embedded-boundary）。
