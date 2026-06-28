import pytest
from fastapi.testclient import TestClient

from troodon.identity import Identity
from troodon.node import create_app
from troodon.store import SQLiteStore
from troodon.v2 import witness as witness_mod


@pytest.fixture
def enable_witness(monkeypatch):
    monkeypatch.setattr(witness_mod, "WITNESS_V2_ENABLED", True)
    yield
    monkeypatch.setattr(witness_mod, "WITNESS_V2_ENABLED", False)


def test_stake_persists_in_sqlite(enable_witness):
    app = create_app(seed=True, auth=False, store=SQLiteStore(":memory:"))
    tc = TestClient(app)
    agent = Identity.generate()
    r = tc.post("/v2/stake/lock", json={
        "agent_id": agent.agent_id,
        "amount": 100,
        "currency": "USD",
        "purpose": "bond",
        "exchange_id": "ex-stake-1",
    })
    assert r.status_code == 200
    stake_id = r.json()["stake_id"]

    app2 = create_app(seed=True, auth=False, store=app.state.engine._store)
    tc2 = TestClient(app2)
    from troodon.v2.stake import get_stake
    loaded = get_stake(stake_id)
    assert loaded is not None
    assert loaded["status"] == "locked"


def test_witness_attach_requires_stake_when_configured(enable_witness):
    app = create_app(seed=True, auth=False, witness_require_stake=True)
    tc = TestClient(app)
    engine = app.state.engine
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="w-stake-req",
    )
    eid = ex.exchange_id
    from tests.helpers import dual_contract_engine
    dual_contract_engine(engine, eid, client, provider)
    engine.escrow(eid, amount=100, currency="USD")
    engine.deliver(eid, provider, {"invoice_no": "W", "total": "1.00", "currency": "USD"})
    vdc = engine.get(eid).vdc
    from troodon.v2.witness import build_witness_attestation, witness_sign
    witness = Identity.generate()
    att = build_witness_attestation(
        vdc_id=vdc["vdc_id"], witness=witness, claim="c",
        vdc_result_hash=vdc["result_hash"],
    )
    witness_sign(att, witness)
    r = tc.post(f"/exchanges/{eid}/v2/witness/attach", json={"attestation": att})
    assert r.status_code == 400

    tc.post("/v2/stake/lock", json={
        "agent_id": witness.agent_id,
        "amount": 50,
        "currency": "USD",
        "purpose": "witness",
        "exchange_id": eid,
        "vdc_id": vdc["vdc_id"],
    })
    r2 = tc.post(f"/exchanges/{eid}/v2/witness/attach", json={"attestation": att})
    assert r2.status_code == 200
