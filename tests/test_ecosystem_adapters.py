"""Ecosystem adapter registry + mqtt_iot work_fn example."""

from __future__ import annotations

import json
from pathlib import Path

from novapanda.ecosystem import iter_adapters, list_adapter_summaries, load_adapter
from novapanda.surfaces import ProviderAdapter

ROOT = Path(__file__).resolve().parents[1]


def test_registry_lists_seed_adapters():
    slugs = {m.slug for m in iter_adapters()}
    assert {"openclaw", "mqtt_iot", "ros2"} <= slugs
    assert "_template" not in slugs
    rows = list_adapter_summaries()
    assert len(rows) >= 3
    assert load_adapter("openclaw").binding.endswith("BINDING-OPENCLAW.md")


def test_adapter_author_checklist_well_formed():
    doc = json.loads(
        (ROOT / "conformance" / "adapter_author_checklist.json").read_text(encoding="utf-8")
    )
    assert "AD-01" in {x["id"] for x in doc["must"]}


def test_mqtt_iot_work_fn_shape():
    from adapters.mqtt_iot.plugin import build_deliverable

    out = build_deliverable({
        "exchange_id": "ex-1",
        "resource_type": "data.extraction.structured",
        "quantity": 1,
        "rule_id": "R-extract-invoice-v1",
        "sensor": {"device_id": "meter-9", "value": 12.5, "unit": "kWh", "topic": "iot/m9"},
    })
    assert out["invoice_no"].startswith("IOT-")
    assert out["currency"] == "USD"
    assert "total" in out


def test_provider_adapter_fulfill_smoke():
    """ProviderAdapter + mqtt work_fn against in-process lifecycle."""
    from fastapi.testclient import TestClient

    from novapanda.identity import Identity
    from novapanda.node import create_app
    from novapanda.sdk import NovaPandaClient
    from adapters.mqtt_iot.plugin import build_deliverable

    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    client = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    provider = NovaPandaClient("http://testserver", Identity.generate(), http=tc)

    ex = client.propose(
        provider=provider.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"},
        idempotency_key="eco-mqtt-1",
    )
    eid = ex["exchange_id"]
    client.contract(eid)
    provider.contract(eid)
    client.escrow(eid, amount=100, currency="USD")

    def work(req: dict) -> dict:
        req = dict(req)
        req["sensor"] = {"device_id": "cabin-1", "amount_display": "100.00"}
        return build_deliverable(req)

    delivered = ProviderAdapter(provider, work).fulfill(eid)
    assert delivered["state"] == "DELIVERED"
    verified = client.verify(eid)
    assert verified["state"] == "VERIFIED"
    settled = client.confirm(eid)
    assert settled["state"] == "SETTLED"
