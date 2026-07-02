import json

import pytest
from fastapi.testclient import TestClient

from novapanda.identity import Identity
from novapanda.manifest import build_agent_manifest, manifest_agent_id, verify_agent_manifest
from novapanda.node import create_app
from novapanda.v1.did import agent_id_to_did
from tests.helpers import dual_contract_engine

GOOD = {"invoice_no": "D-1", "total": "100.00", "currency": "USD"}


def test_manifest_includes_did_and_resolves():
    provider = Identity.generate()
    manifest = build_agent_manifest(
        provider,
        capabilities=[{"resource_type": "x", "rules": ["R"], "price": {"amount": 1, "currency": "USD"}}],
        exchange_endpoint="http://node/exchanges",
    )
    assert manifest["did"] == agent_id_to_did(provider.agent_id)
    assert verify_agent_manifest(manifest) is True
    assert manifest_agent_id(manifest) == provider.agent_id


def test_manifest_did_mismatch_fails_verify():
    provider = Identity.generate()
    manifest = build_agent_manifest(
        provider,
        capabilities=[{"resource_type": "x", "rules": ["R"], "price": {"amount": 1, "currency": "USD"}}],
        exchange_endpoint="http://node/exchanges",
    )
    other = Identity.generate()
    manifest["did"] = agent_id_to_did(other.agent_id)
    assert verify_agent_manifest(manifest) is False


def test_propose_with_provider_did():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    provider = Identity.generate()
    client = Identity.generate()
    r = tc.post("/exchanges", json={
        "client": client.agent_id,
        "provider": provider.agent_id,
        "provider_did": agent_id_to_did(provider.agent_id),
        "resource_type": "data.extraction.structured",
        "quantity": 1,
        "rule_id": "R-extract-invoice-v1",
        "price": {"amount": 100, "currency": "USD"},
        "idempotency_key": "did-propose-1",
    })
    assert r.status_code == 201


def test_propose_provider_did_mismatch_rejected():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    provider = Identity.generate()
    other = Identity.generate()
    client = Identity.generate()
    r = tc.post("/exchanges", json={
        "client": client.agent_id,
        "provider": provider.agent_id,
        "provider_did": agent_id_to_did(other.agent_id),
        "resource_type": "data.extraction.structured",
        "quantity": 1,
        "rule_id": "R-extract-invoice-v1",
        "price": {"amount": 100, "currency": "USD"},
        "idempotency_key": "did-propose-bad",
    })
    assert r.status_code == 400
    assert r.json()["code"] == "E_DID_MISMATCH"


def test_contract_party_did_ok():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    engine = app.state.engine
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id,
        provider=provider.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"},
        idempotency_key="did-contract-1",
    )
    eid = ex.exchange_id
    from novapanda.terms import sign_contract_ack

    sig = sign_contract_ack(client, ex)
    r = tc.post(f"/exchanges/{eid}/contract", json={
        "signature": sig,
        "party_did": agent_id_to_did(client.agent_id),
    })
    assert r.status_code == 200
