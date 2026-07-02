"""C7：Manifest/发现 — 能被发现、验签并发起交换。"""

from fastapi.testclient import TestClient

from novapanda.identity import Identity
from novapanda.manifest import build_agent_manifest, verify_agent_manifest
from novapanda.node import create_app
from novapanda.sdk import NovaPandaClient
from tests.helpers import dual_contract_sdk

RULE_ID = "R-extract-invoice-v1"
RESOURCE = "data.extraction.structured"
PRICE = {"amount": 100, "currency": "USD"}
GOOD = {"invoice_no": "A-001", "total": "100.00", "currency": "USD"}


def test_agent_manifest_self_signed_and_verifiable():
    provider = Identity.generate()
    manifest = build_agent_manifest(
        provider,
        capabilities=[{
            "resource_type": RESOURCE,
            "rules": [RULE_ID],
            "price": PRICE,
        }],
        exchange_endpoint="http://node.example/exchanges",
        transport=["http", "mcp"],
    )
    assert verify_agent_manifest(manifest) is True
    assert manifest["agent_id"] == provider.agent_id


def test_discover_provider_from_manifest_and_exchange():
    """client 从 provider manifest 发现 rule，完成一笔交换。"""
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    client = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    provider = NovaPandaClient("http://testserver", Identity.generate(), http=tc)

    manifest = build_agent_manifest(
        provider.identity,
        capabilities=[{"resource_type": RESOURCE, "rules": [RULE_ID], "price": PRICE}],
        exchange_endpoint="http://testserver/exchanges",
    )
    assert verify_agent_manifest(manifest)

    cap = manifest["capabilities"][0]
    ex = client.propose(
        provider=manifest["agent_id"],
        resource_type=cap["resource_type"],
        quantity=1,
        rule_id=cap["rules"][0],
        price=cap["price"],
        idempotency_key="c7-1",
    )
    eid = ex["exchange_id"]
    dual_contract_sdk(client, provider, eid)
    client.escrow(eid, amount=100, currency="USD")
    provider.deliver(eid, GOOD)
    client.verify(eid)
    settled = client.confirm(eid)
    assert settled["state"] == "SETTLED"
