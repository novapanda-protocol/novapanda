from fastapi.testclient import TestClient

from troodon.identity import Identity
from troodon.node import create_app
from troodon.v1.did import agent_id_to_did, build_did_document
from troodon.terms import sign_contract_ack


def test_propose_with_pure_provider_did():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    provider = Identity.generate()
    client = Identity.generate()
    doc = build_did_document(provider)
    tc.post("/v1/did/register", json={"document": doc})
    did = agent_id_to_did(provider.agent_id)
    r = tc.post("/exchanges", json={
        "client": client.agent_id,
        "provider": did,
        "resource_type": "data.extraction.structured",
        "quantity": 1,
        "rule_id": "R-extract-invoice-v1",
        "price": {"amount": 100, "currency": "USD"},
        "idempotency_key": "did-pure-provider",
    })
    assert r.status_code == 201
    assert r.json()["provider"] == provider.agent_id


def test_contract_with_party_did_only():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    engine = app.state.engine
    client, provider = Identity.generate(), Identity.generate()
    for ident in (client, provider):
        tc.post("/v1/did/register", json={"document": build_did_document(ident)})
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"},
        idempotency_key="did-contract-pure",
    )
    eid = ex.exchange_id
    sig = sign_contract_ack(client, ex)
    r = tc.post(f"/exchanges/{eid}/contract", json={
        "signature": sig,
        "party_did": agent_id_to_did(client.agent_id),
    })
    assert r.status_code == 200


def test_resolve_returns_registered_pubkey():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    provider = Identity.generate()
    doc = build_did_document(provider)
    tc.post("/v1/did/register", json={"document": doc})
    did = agent_id_to_did(provider.agent_id)
    resolved = tc.get(f"/v1/did/resolve/{did}").json()
    assert resolved["public_key_b64url"] == provider.pubkey_b64url
    assert resolved["resolved_via"] == "document"
