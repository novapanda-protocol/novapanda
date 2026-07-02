import json
import secrets

import pytest
from fastapi.testclient import TestClient

from novapanda import vdc as V
from novapanda.auth import sign_request
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.sdk import NovaPandaClient
from tests.helpers import dual_contract_sdk

RULE_ID = "R-extract-invoice-v1"
RESOURCE = "data.extraction.structured"
PRICE = {"amount": 100, "currency": "USD"}
GOOD = {"invoice_no": "A-001", "total": "100.00", "currency": "USD"}


@pytest.fixture
def ctx():
    app = create_app(seed=True, auth=True)
    tc = TestClient(app)
    client = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    provider = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    return tc, client, provider


def test_signed_happy_path_works_under_auth(ctx):
    _, client, provider = ctx
    ex = client.propose(provider=provider.agent_id, resource_type=RESOURCE, quantity=1,
                        rule_id=RULE_ID, price=PRICE, idempotency_key="auth-happy")
    eid = ex["exchange_id"]
    dual_contract_sdk(client, provider, eid)
    client.escrow(eid, amount=100, currency="USD")
    provider.deliver(eid, GOOD)
    client.verify(eid)
    settled = client.confirm(eid)
    assert settled["state"] == "SETTLED"
    assert V.is_valid_settled(settled["vdc"]) is True


def test_unsigned_request_rejected(ctx):
    tc, _, provider = ctx
    r = tc.post("/exchanges", json={
        "client": provider.agent_id, "provider": provider.agent_id,
        "resource_type": RESOURCE, "quantity": 1, "rule_id": RULE_ID,
        "price": PRICE, "idempotency_key": "x"})
    assert r.status_code == 401
    assert r.json()["code"] == "E_AUTH_MISSING"


def test_bad_signature_rejected(ctx):
    tc, client, provider = ctx
    body = json.dumps({"client": client.agent_id, "provider": provider.agent_id,
                       "resource_type": RESOURCE, "quantity": 1, "rule_id": RULE_ID,
                       "price": PRICE, "idempotency_key": "y"}).encode()
    headers = {"Content-Type": "application/json", "X-Agent-Id": client.agent_id,
               "X-Nonce": secrets.token_hex(16), "X-Signature": "AAAA"}
    r = tc.post("/exchanges", content=body, headers=headers)
    assert r.status_code == 401
    assert r.json()["code"] == "E_SIG_INVALID"


def test_replayed_nonce_rejected(ctx):
    tc, client, provider = ctx
    body = json.dumps({"client": client.agent_id, "provider": provider.agent_id,
                       "resource_type": RESOURCE, "quantity": 1, "rule_id": RULE_ID,
                       "price": PRICE, "idempotency_key": "replay"}).encode()
    nonce = secrets.token_hex(16)
    headers = {"Content-Type": "application/json", "X-Agent-Id": client.agent_id,
               "X-Nonce": nonce,
               "X-Signature": sign_request(client.identity, "POST", "/exchanges", nonce, body)}
    r1 = tc.post("/exchanges", content=body, headers=headers)
    assert r1.status_code == 201
    r2 = tc.post("/exchanges", content=body, headers=headers)  # 同 nonce 重放
    assert r2.status_code == 409
    assert r2.json()["code"] == "E_REPLAY"


def test_wrong_party_forbidden(ctx):
    tc, client, provider = ctx
    ex = client.propose(provider=provider.agent_id, resource_type=RESOURCE, quantity=1,
                        rule_id=RULE_ID, price=PRICE, idempotency_key="auth-forbid")
    eid = ex["exchange_id"]
    dual_contract_sdk(client, provider, eid)
    client.escrow(eid, amount=100, currency="USD")
    # 服务端授权：deliver 只允许 provider；以 client 身份签名直接打 deliver -> 403
    path = f"/exchanges/{eid}/deliver"
    body = json.dumps({"vdc": {}, "deliverable": {}}).encode()
    nonce = secrets.token_hex(16)
    headers = {"Content-Type": "application/json", "X-Agent-Id": client.agent_id,
               "X-Nonce": nonce,
               "X-Signature": sign_request(client.identity, "POST", path, nonce, body)}
    r = tc.post(path, content=body, headers=headers)
    assert r.status_code == 403
    assert r.json()["code"] == "E_FORBIDDEN"


def test_propose_spoofed_client_forbidden(ctx):
    """签名者（X-Agent-Id）与 body.client 不一致 -> 403。"""
    tc, _, provider = ctx
    attacker = Identity.generate()
    victim = Identity.generate()
    body = json.dumps({
        "client": victim.agent_id,         # 冒充 victim 为 client
        "provider": provider.agent_id, "resource_type": RESOURCE, "quantity": 1,
        "rule_id": RULE_ID, "price": PRICE, "idempotency_key": "spoof",
    }).encode()
    nonce = secrets.token_hex(16)
    headers = {"Content-Type": "application/json", "X-Agent-Id": attacker.agent_id,
               "X-Nonce": nonce,
               "X-Signature": sign_request(attacker, "POST", "/exchanges", nonce, body)}
    r = tc.post("/exchanges", content=body, headers=headers)
    assert r.status_code == 403
    assert r.json()["code"] == "E_FORBIDDEN"
