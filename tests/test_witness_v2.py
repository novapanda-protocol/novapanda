import pytest
from fastapi.testclient import TestClient

from novapanda.hashing import result_hash_of_json
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.store import SQLiteStore
from novapanda.v2.witness import (
    WITNESS_V2_ENABLED,
    WitnessV2NotEnabledError,
    build_stake_lock,
    build_witness_attestation,
    validate_stake_lock,
    validate_witness_attestation,
    witness_sign,
)
from tests.helpers import dual_contract_engine

GOOD = {"invoice_no": "W-1", "total": "100.00", "currency": "USD"}


def test_build_and_validate_witness_attestation():
    witness = Identity.generate()
    doc = build_witness_attestation(
        vdc_id="abc123",
        witness=witness,
        claim="delivery verified by witness",
        vdc_result_hash="sha256:" + "a" * 64,
    )
    witness_sign(doc, witness)
    assert validate_witness_attestation(doc) == []


def test_invalid_witness_attestation_detected():
    doc = build_witness_attestation(
        vdc_id="x",
        witness=Identity.generate(),
        claim="ok",
        vdc_result_hash="bad",
    )
    errs = validate_witness_attestation(doc)
    assert any("vdc_result_hash" in e for e in errs)


def test_stake_lock_validation():
    agent = Identity.generate()
    stake = build_stake_lock(
        agent_id=agent.agent_id, amount=100, currency="USD", purpose="witness bond"
    )
    assert validate_stake_lock(stake) == []


def test_attach_witness_disabled_by_default():
    from novapanda.exchange import ExchangeEngine
    from novapanda.settlement import MockSettlement

    engine = ExchangeEngine(MockSettlement())
    witness = Identity.generate()
    att = build_witness_attestation(
        vdc_id="v1", witness=witness, claim="c",
        vdc_result_hash="sha256:" + "b" * 64,
    )
    witness_sign(att, witness)
    with pytest.raises(WitnessV2NotEnabledError):
        engine.attach_witness_v2("ex-missing", att)
    assert WITNESS_V2_ENABLED is False


def test_node_validate_witness_endpoint():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    witness = Identity.generate()
    att = build_witness_attestation(
        vdc_id="v2", witness=witness, claim="witnessed",
        vdc_result_hash=result_hash_of_json({"x": 1}),
    )
    witness_sign(att, witness)
    r = tc.post("/v2/witness/validate", json={"attestation": att})
    assert r.status_code == 200
    assert r.json()["valid"] is True


def test_node_attach_returns_501_when_disabled():
    app = create_app(seed=True, auth=False, store=SQLiteStore(":memory:"))
    tc = TestClient(app)
    engine = app.state.engine
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="w2-attach",
    )
    eid = ex.exchange_id
    dual_contract_engine(engine, eid, client, provider)
    engine.escrow(eid, amount=100, currency="USD")
    engine.deliver(eid, provider, GOOD)

    vdc = engine.get(eid).vdc
    witness = Identity.generate()
    att = build_witness_attestation(
        vdc_id=vdc["vdc_id"], witness=witness, claim="c",
        vdc_result_hash=vdc["result_hash"],
    )
    witness_sign(att, witness)
    r = tc.post(f"/exchanges/{eid}/v2/witness/attach", json={"attestation": att})
    assert r.status_code == 501
    assert r.json()["code"] == "E_NOT_IMPLEMENTED"


def test_node_stake_lock_returns_501():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    agent = Identity.generate()
    r = tc.post("/v2/stake/lock", json={
        "agent_id": agent.agent_id,
        "amount": 100,
        "currency": "USD",
        "purpose": "test",
    })
    assert r.status_code == 501
