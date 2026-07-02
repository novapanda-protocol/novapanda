#!/usr/bin/env python3
"""连接公开 mock 试用节点，跑通一条 SETTLED 交换。

用法（仓库根目录）：
  pip install -e .
  python demo/trial_remote.py

默认节点：https://node.novapanda.io（settlement: mock，无真钱）
"""

from __future__ import annotations

import json
import secrets
import sys

from novapanda.identity import Identity
from novapanda.sdk import NovaPandaClient

BASE_URL = "https://node.novapanda.io"
RULE_ID = "R-extract-invoice-v1"
RESOURCE = "data.extraction.structured"
PRICE = {"amount": 100, "currency": "USD"}
GOOD = {"invoice_no": "TRIAL-001", "total": "100.00", "currency": "USD"}


def main() -> int:
    client_id = Identity.generate()
    provider_id = Identity.generate()
    client = NovaPandaClient(BASE_URL, client_id)
    provider = NovaPandaClient(BASE_URL, provider_id)

    idem = f"trial-{secrets.token_hex(8)}"
    print(f"node: {BASE_URL}")
    print(f"client:   {client.agent_id}")
    print(f"provider: {provider.agent_id}")

    ex = client.propose(
        provider=provider.agent_id,
        resource_type=RESOURCE,
        quantity=1,
        rule_id=RULE_ID,
        price=PRICE,
        idempotency_key=idem,
    )
    eid = ex["exchange_id"]
    client.contract(eid)
    provider.contract(eid)
    client.escrow(eid, amount=100, currency="USD")
    provider.deliver(eid, GOOD)
    client.verify(eid)
    settled = client.confirm(eid)

    if settled["state"] != "SETTLED":
        print(f"unexpected state: {settled['state']}", file=sys.stderr)
        return 1

    print(json.dumps({
        "ok": True,
        "exchange_id": eid,
        "vdc_id": settled["vdc"]["vdc_id"],
        "settlement": settled.get("settlement_receipt", {}).get("status"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
