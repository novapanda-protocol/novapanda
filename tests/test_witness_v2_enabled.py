import pytest
from fastapi.testclient import TestClient

from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.store import SQLiteStore
from novapanda.v2 import witness as witness_mod
from novapanda.v2.witness import build_witness_attestation, witness_sign
from tests.helpers import dual_contract_engine

GOOD = {"invoice_no": "W-2", "total": "100.00", "currency": "USD"}


@pytest.fixture
def enable_witness_v2(monkeypatch):
    monkeypatch.setattr(witness_mod, "WITNESS_V2_ENABLED", True)
    yield
    monkeypatch.setattr(witness_mod, "WITNESS_V2_ENABLED", False)


def test_attach_witness_when_enabled(enable_witness_v2):
    app = create_app(seed=True, auth=False, store=SQLiteStore(":memory:"))
    tc = TestClient(app)
    engine = app.state.engine
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="w2-on",
    )
    eid = ex.exchange_id
    dual_contract_engine(engine, eid, client, provider)
    engine.escrow(eid, amount=100, currency="USD")
    engine.deliver(eid, provider, GOOD)
    vdc = engine.get(eid).vdc

    witness = Identity.generate()
    att = build_witness_attestation(
        vdc_id=vdc["vdc_id"], witness=witness, claim="independent witness",
        vdc_result_hash=vdc["result_hash"],
    )
    witness_sign(att, witness)
    r = tc.post(f"/exchanges/{eid}/v2/witness/attach", json={"attestation": att})
    assert r.status_code == 200
    updated = engine.get(eid).vdc
    assert updated["evidence"]["level"] == "third_party_witnessed"
    assert len(updated["evidence"]["witnesses"]) == 1
