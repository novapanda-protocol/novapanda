import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from troodon.identity import Identity
from troodon.node import create_app
from troodon.v2 import federation as fed_mod
from tests.helpers import dual_contract_engine

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "sdk_parity_vector.json"
GOOD = {"invoice_no": "A-1", "total": "100.00", "currency": "USD"}


def test_sdk_parity_fixture_internally_consistent():
    from troodon import vdc as V
    from troodon.auth import sign_request
    from troodon.terms import contract_ack_bytes, sign_contract_ack, terms_hash_from_dict

    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    provider = Identity.from_private_bytes(bytes.fromhex(data["provider_private_key_hex"]))
    assert provider.agent_id == data["provider_agent_id"]
    assert terms_hash_from_dict(data["exchange"]) == data["terms_hash"]
    assert sign_contract_ack(provider, data["exchange"]) == data["contract_ack_sig"]
    assert contract_ack_bytes(
        terms_hash=data["terms_hash"], exchange_id=data["exchange"]["exchange_id"],
    ).hex() == data["contract_ack_bytes_hex"]
    doc = json.loads(json.dumps(data["unsigned_vdc"]))
    V.provider_sign(doc, provider)
    assert doc["signatures"]["provider_sig"] == data["provider_sig"]


@pytest.fixture
def enable_federation(monkeypatch):
    monkeypatch.setattr(fed_mod, "FEDERATION_V2_ENABLED", True)


def _settled_provider(app, provider: Identity) -> str:
    engine = app.state.engine
    client = Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"},
        idempotency_key=f"score-{provider.agent_id[-8:]}",
    )
    eid = ex.exchange_id
    dual_contract_engine(engine, eid, client, provider)
    engine.escrow(eid, amount=100, currency="USD")
    engine.deliver(eid, provider, GOOD)
    rule = app.state.rules.get("R-extract-invoice-v1")
    engine.verify(eid, rule=rule)
    engine.confirm(eid, client)
    return provider.agent_id


def test_weighted_score_local_entries():
    app = create_app(seed=True, auth=False)
    provider = Identity.generate()
    agent_id = _settled_provider(app, provider)
    score = app.state.reputation.weighted_score(agent_id)
    assert score["entry_count"] >= 1
    assert score["score"] == 1.0


def test_weighted_score_api_with_imported_mirror(enable_federation):
    src = create_app(seed=True, auth=False)
    provider = Identity.generate()
    agent_id = _settled_provider(src, provider)
    bundle = src.state.reputation.export_bundle(agent_id)

    dst = create_app(seed=True, auth=False)
    dst.state.reputation.import_external_bundle(bundle)
    tc = TestClient(dst)
    source = bundle["source_node_id"]
    r = tc.get(
        f"/v2/reputation/{agent_id}/score",
        params={"weights": json.dumps({source: 2.0, dst.state.node_id: 0.5})},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["entry_count"] >= 1
    assert body["weighted_settled"] >= 2.0
