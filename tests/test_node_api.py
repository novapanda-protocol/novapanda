import pytest
from fastapi.testclient import TestClient

from troodon import vdc as V
from troodon.identity import Identity
from troodon.node import create_app
from troodon.sdk import TroodonClient
from tests.helpers import dual_contract_sdk

RULE_ID = "R-extract-invoice-v1"
RESOURCE = "data.extraction.structured"
GOOD = {"invoice_no": "A-001", "total": "100.00", "currency": "USD"}
BAD = {"invoice_no": "A-001", "total": "100.00"}  # 缺 currency


@pytest.fixture
def ctx():
    app = create_app(seed=True, auth=False)  # 本文件测 API 语义；鉴权见 test_auth.py
    tc = TestClient(app)
    client_id, provider_id = Identity.generate(), Identity.generate()
    client = TroodonClient("http://testserver", client_id, http=tc)
    provider = TroodonClient("http://testserver", provider_id, http=tc)
    return client, provider


def _setup_escrowed(client: TroodonClient, provider: TroodonClient, idem="t1"):
    ex = client.propose(
        provider=provider.agent_id, resource_type=RESOURCE, quantity=1,
        rule_id=RULE_ID, price={"amount": 100, "currency": "USD"}, idempotency_key=idem,
    )
    eid = ex["exchange_id"]
    dual_contract_sdk(client, provider, eid)
    client.escrow(eid, amount=100, currency="USD")
    return eid


def test_manifest_discoverable(ctx):
    client, _ = ctx
    r = client._get("/.well-known/troodon.json")
    assert r["protocol"] == "troodon"
    assert RESOURCE in r["resource_types"]


def test_happy_path_dual_signed_settlement(ctx):
    client, provider = ctx
    eid = _setup_escrowed(client, provider)

    provider.deliver(eid, GOOD)
    v = client.verify(eid)
    assert v["state"] == "VERIFIED"
    assert v["verify_result"]["passed"] is True

    settled = client.confirm(eid)
    assert settled["state"] == "SETTLED"
    # 节点从未持有私钥；返回的双签 VDC 可被任何人独立复验
    assert V.is_valid_settled(settled["vdc"]) is True
    assert settled["settlement_receipt"]["status"] == "settled"


def test_reject_path_refunds(ctx):
    client, provider = ctx
    eid = _setup_escrowed(client, provider, idem="t-reject")
    provider.deliver(eid, BAD)
    v = client.verify(eid)
    assert v["state"] == "REJECTED"
    assert v["verify_result"]["passed"] is False
    assert v["settlement_receipt"]["status"] == "refunded"


def test_reputation_recorded_for_both_parties(ctx):
    client, provider = ctx
    eid = _setup_escrowed(client, provider, idem="t-rep")
    provider.deliver(eid, GOOD)
    client.verify(eid)
    client.confirm(eid)

    prov_rep = provider.reputation(provider.agent_id)
    cli_rep = client.reputation(client.agent_id)
    assert len(prov_rep["entries"]) == 1
    assert prov_rep["entries"][0]["outcome"] == "settled"
    assert len(cli_rep["entries"]) == 1


def test_node_rejects_tampered_vdc(ctx):
    """篡改 deliverable 但沿用旧签名 -> 节点验签/哈希校验必须拒绝。"""
    client, provider = ctx
    eid = _setup_escrowed(client, provider, idem="t-tamper")
    ex = client.get_exchange(eid)
    doc = V.build_vdc(
        client=ex["client"], provider=provider.agent_id, resource_type=RESOURCE,
        quantity=1, result_hash="sha256:deadbeef", rule_id=RULE_ID,
        evidence_level="dual_signed", started_at="2026-06-28T00:00:00Z",
        finished_at="2026-06-28T00:00:01Z", idempotency_key=ex["idempotency_key"],
        nonce=ex["nonce"], state="DELIVERED",
    )
    V.provider_sign(doc, provider.identity)
    # result_hash 与 deliverable 不符 -> 400
    resp = client._http.post(f"/exchanges/{eid}/deliver", json={"vdc": doc, "deliverable": GOOD})
    assert resp.status_code == 400


def test_unknown_exchange_returns_404(ctx):
    client, provider = ctx
    ex = client.propose(
        provider=provider.agent_id, resource_type=RESOURCE, quantity=1,
        rule_id=RULE_ID, price={"amount": 100, "currency": "USD"}, idempotency_key="t-404",
    )
    dual_contract_sdk(client, provider, ex["exchange_id"])
    resp = client._http.post(f"/exchanges/does-not-exist/contract", json={"signature": "x"})
    assert resp.status_code == 404
    assert resp.json()["code"] == "E_NOT_FOUND"


def test_illegal_state_returns_409(ctx):
    client, provider = ctx
    ex = client.propose(
        provider=provider.agent_id, resource_type=RESOURCE, quantity=1,
        rule_id=RULE_ID, price={"amount": 100, "currency": "USD"}, idempotency_key="t-409",
    )
    eid = ex["exchange_id"]
    # 未 contract/escrow 直接 deliver -> 状态机拒绝 409
    resp = client._http.post(f"/exchanges/{eid}/deliver", json={"vdc": {"state": "DELIVERED"}, "deliverable": GOOD})
    assert resp.status_code == 409


def test_health(ctx):
    client, _ = ctx
    r = client._http.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_sweep_admin_token(monkeypatch):
    monkeypatch.setenv("TROODON_ADMIN_TOKEN", "test-admin-secret")
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    assert tc.post("/admin/sweep").status_code == 401
    r = tc.post("/admin/sweep", headers={"X-Admin-Token": "test-admin-secret"})
    assert r.status_code == 200
    assert "expired" in r.json()
