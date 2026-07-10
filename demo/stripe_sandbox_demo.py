"""Stripe 沙箱轨演示（fake PaymentIntent，无需 sk_test）。

真沙箱：设 NOVAPANDA_FIAT_PROVIDER=stripe · NOVAPANDA_FIAT_API_KEY=sk_test_…
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi.testclient import TestClient

from novapanda.config import NodeConfig
from novapanda.fiat_gateway import make_fiat_gateway
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.rail_registry import build_rail_registry
from novapanda.sdk import NovaPandaClient
from novapanda.settlement import S1HttpSandboxSettlement
from novapanda.stripe_fake import create_stripe_fake_app

RULE = "R-extract-invoice-v1"
RESOURCE = "data.extraction.structured"
GOOD = {"invoice_no": "STR-001", "total": "10.00", "currency": "USD"}


def main() -> None:
    os.environ.setdefault("NOVAPANDA_AUTH", "0")
    os.environ.setdefault("NOVAPANDA_SANDBOX_PARTNER", "stripe-sandbox")

    stripe_tc = TestClient(create_stripe_fake_app())
    gw = make_fiat_gateway(
        base_url="http://testserver/v1",
        api_key="sk_test_demo",
        http=stripe_tc,
        provider="stripe",
    )

    cfg = NodeConfig(
        settlement="sandbox",
        settlement_rails=["sandbox", "mock"],
        default_rail="sandbox",
        fiat_gateway_url="https://api.stripe.com/v1",
    )
    reg = build_rail_registry(cfg)
    s1 = reg.get("sandbox")
    assert isinstance(s1, S1HttpSandboxSettlement)
    s1.gateway = gw

    app = create_app(seed=True, auth=False, settlement=reg.active_adapter, rail_registry=reg)
    tc = TestClient(app)

    print("=" * 64)
    print("Stripe sandbox demo (fake PaymentIntent)")
    print("=" * 64)

    client = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    provider = NovaPandaClient("http://testserver", Identity.generate(), http=tc)

    ex = client.propose(
        provider=provider.agent_id,
        resource_type=RESOURCE,
        quantity=1,
        rule_id=RULE,
        price={"amount": 1000, "currency": "USD"},
        idempotency_key="stripe-demo-1",
        settlement={"preferred_rails": ["fiat-s1-sandbox"], "currency": "USD"},
    )
    eid = ex["exchange_id"]
    client.contract(eid)
    provider.contract(eid)
    client.escrow(eid, amount=1000, currency="USD")
    provider.deliver(eid, GOOD)
    client.verify(eid)
    settled = client.confirm(eid)
    receipt = settled.get("settlement_receipt") or {}
    print(f"partner={receipt.get('partner')} rail={receipt.get('rail')} env={receipt.get('environment')}")
    assert receipt.get("partner") == "stripe-sandbox"
    print("\nOK: Stripe sandbox path (fake PI) — swap key for sk_test_* on real sandbox")


if __name__ == "__main__":
    main()
