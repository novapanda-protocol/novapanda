"""生态适配器示例：mqtt_iot work_fn + ProviderAdapter → SETTLED。

运行：  python demo/adopter_mqtt_iot.py

对齐 adapters/mqtt_iot · docs/ecosystem-adapters.md。
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from adapters.mqtt_iot.plugin import build_deliverable
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.reverify import reverify
from novapanda.sdk import NovaPandaClient
from novapanda.surfaces import ProviderAdapter

OUT = Path(__file__).parent / "out" / "mqtt_iot"
PRICE = {"amount": 100, "currency": "USD"}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    client = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    provider = NovaPandaClient("http://testserver", Identity.generate(), http=tc)

    ex = client.propose(
        provider=provider.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R-extract-invoice-v1",
        price=PRICE,
        idempotency_key="demo-mqtt-iot-1",
    )
    eid = ex["exchange_id"]
    client.contract(eid)
    provider.contract(eid)
    client.escrow(eid, amount=PRICE["amount"], currency=PRICE["currency"])

    held: dict = {}

    def work(req: dict) -> dict:
        req = dict(req)
        req["sensor"] = {
            "device_id": "cabin-meter-1",
            "amount_display": "100.00",
            "topic": "iot/cabin/energy",
            "value": 2.5,
            "unit": "kWh",
        }
        held["deliverable"] = build_deliverable(req)
        return held["deliverable"]

    ProviderAdapter(provider, work).fulfill(eid)
    client.verify(eid)
    settled = client.confirm(eid)
    assert settled["state"] == "SETTLED"
    checks = reverify(settled["vdc"], held["deliverable"])
    out = {
        "ok": settled["state"] == "SETTLED" and checks.get("settled_valid") is True,
        "exchange_id": eid,
        "adapter": "mqtt_iot",
        "settlement": "mock",
        "reverify": checks,
    }
    (OUT / "last_run.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"工件: {OUT}")


if __name__ == "__main__":
    main()
