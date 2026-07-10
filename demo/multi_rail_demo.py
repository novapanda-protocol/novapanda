"""多轨结算演示：quote / negotiate 预览 + 完整交割。

运行：
  python demo/multi_rail_demo.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi.testclient import TestClient

from novapanda.identity import Identity
from novapanda.node import create_app_from_config
from novapanda.sdk import NovaPandaClient

RULE_ID = "R-extract-invoice-v1"
RESOURCE = "data.extraction.structured"
GOOD_USD = {"invoice_no": "MR-001", "total": "100.00", "currency": "USD"}


def main() -> None:
    os.environ.setdefault("NOVAPANDA_AUTH", "0")
    os.environ.setdefault("NOVAPANDA_RAILS", "mock,x402,sandbox")
    os.environ.setdefault("NOVAPANDA_DEFAULT_RAIL", "mock")

    app = create_app_from_config()
    tc = TestClient(app)

    print("=" * 64)
    print("Part A | quote + negotiate (micro USDC -> x402)")
    print("=" * 64)

    quote = tc.get("/node/settlement/quote", params={"amount": 50, "currency": "USDC"}).json()
    print(f"recommended_rail = {quote['recommended_rail']}  amount_class = {quote['amount_class']}")
    for q in quote["quotes"]:
        mark = "Y" if q["eligible"] else "N"
        print(f"  [{mark}] {q['rail']}: {q.get('note') or 'ok'}")

    preview = tc.post(
        "/node/settlement/negotiate",
        json={
            "amount": 50,
            "currency": "USDC",
            "settlement": {
                "preferred_rails": ["x402", "mock"],
                "client_rails": ["x402", "mock"],
                "provider_rails": ["x402", "sandbox"],
            },
        },
    ).json()
    print(f"binding_preview = {preview['binding_preview']}")

    print("\n" + "=" * 64)
    print("Part B | full exchange (USD standard -> mock rail)")
    print("=" * 64)

    client = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    provider = NovaPandaClient("http://testserver", Identity.generate(), http=tc)

    ex = client.propose(
        provider=provider.agent_id,
        resource_type=RESOURCE,
        quantity=1,
        rule_id=RULE_ID,
        price={"amount": 100, "currency": "USD"},
        idempotency_key="multi-rail-demo-usd",
    )
    eid = ex["exchange_id"]
    client.contract(eid)
    contracted = provider.contract(eid)
    binding = contracted.get("settlement_binding") or {}
    print(f"CONTRACTED rail = {binding.get('rail')}")

    client.escrow(eid, amount=100, currency="USD")
    provider.deliver(eid, GOOD_USD)
    client.verify(eid)
    settled = client.confirm(eid)
    receipt = settled.get("settlement_receipt") or {}
    print(f"SETTLED receipt.rail = {receipt.get('rail')}")
    assert binding.get("rail") == "mock"
    assert receipt.get("rail") == "mock"
    print("\nOK: multi-rail quote + binding + settlement complete")


if __name__ == "__main__":
    main()
