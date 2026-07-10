"""S1 沙箱 HTTP 演示：内置 fake 伙伴网关 + fiat-s1-sandbox 轨。

运行：
  python demo/s1_sandbox_demo.py
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
from novapanda.fiat_fake import create_fiat_fake_app
from novapanda.fiat_gateway import HttpFiatGateway
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.rail_registry import build_rail_registry
from novapanda.sdk import NovaPandaClient
from novapanda.settlement import S1HttpSandboxSettlement

RULE_ID = "R-extract-invoice-v1"
RESOURCE = "data.extraction.structured"
GOOD = {"invoice_no": "S1-001", "total": "100.00", "currency": "USD"}


def main() -> None:
    os.environ.setdefault("NOVAPANDA_AUTH", "0")
    os.environ.setdefault("NOVAPANDA_SANDBOX_PARTNER", "demo-psp")

    fake_tc = TestClient(create_fiat_fake_app())
    gw = HttpFiatGateway("http://testserver", http=fake_tc)

    cfg = NodeConfig(
        settlement="sandbox",
        settlement_rails=["sandbox", "mock"],
        default_rail="sandbox",
        fiat_gateway_url="http://fake.local",
    )
    reg = build_rail_registry(cfg)
    s1 = reg.get("sandbox")
    assert isinstance(s1, S1HttpSandboxSettlement)
    s1.gateway = gw  # 演示注入 fake 伙伴

    app = create_app(seed=True, auth=False, settlement=reg.active_adapter, rail_registry=reg)
    tc = TestClient(app)

    print("=" * 64)
    print("S1 sandbox HTTP demo (fake partner gateway)")
    print("=" * 64)
    rails = tc.get("/node/settlement/rails").json()
    sandbox = next(r for r in rails["rails"] if r["id"] == "fiat-s1-sandbox")
    print(f"rail: {sandbox['id']} env={sandbox['environment']} transport={sandbox.get('transport')}")

    client = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    provider = NovaPandaClient("http://testserver", Identity.generate(), http=tc)

    ex = client.propose(
        provider=provider.agent_id,
        resource_type=RESOURCE,
        quantity=1,
        rule_id=RULE_ID,
        price={"amount": 100, "currency": "USD"},
        idempotency_key="s1-sandbox-http",
        settlement={"preferred_rails": ["fiat-s1-sandbox"], "currency": "USD"},
    )
    eid = ex["exchange_id"]
    client.contract(eid)
    c = provider.contract(eid)
    print(f"binding: {c.get('settlement_binding')}")

    client.escrow(eid, amount=100, currency="USD")
    provider.deliver(eid, GOOD)
    client.verify(eid)
    settled = client.confirm(eid)
    receipt = settled.get("settlement_receipt") or {}
    print(f"SETTLED receipt.rail={receipt.get('rail')} env={receipt.get('environment')}")
    assert receipt.get("rail") == "fiat-s1-sandbox"
    print("\nOK: S1 HTTP sandbox path (fake gateway) — swap NOVAPANDA_FIAT_URL for real partner")


if __name__ == "__main__":
    main()
