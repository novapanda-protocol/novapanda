import pytest
from troodon.v2 import federation as fed_mod
from troodon.node import create_app
from tests.helpers import dual_contract_engine
from troodon.identity import Identity

GOOD = {"invoice_no": "I-1", "total": "100.00", "currency": "USD"}


@pytest.fixture
def enable_federation(monkeypatch):
    monkeypatch.setattr(fed_mod, "FEDERATION_V2_ENABLED", True)


def _settled(app):
    engine = app.state.engine
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="fed-imp2",
    )
    eid = ex.exchange_id
    dual_contract_engine(engine, eid, client, provider)
    engine.escrow(eid, amount=100, currency="USD")
    engine.deliver(eid, provider, GOOD)
    rule = app.state.rules.get("R-extract-invoice-v1")
    engine.verify(eid, rule=rule)
    engine.confirm(eid, client)


def test_import_mirror_extends_local_chain(enable_federation):
    src_app = create_app(seed=True, auth=False)
    _settled(src_app)
    bundle = src_app.state.reputation.export_bundle()
    assert bundle["entry_count"] >= 2

    dst_app = create_app(seed=True, auth=False)
    imported = dst_app.state.reputation.import_external_bundle(bundle)
    assert len(imported) >= 2
    assert all(e.get("import_kind") == "mirror" for e in imported)
    assert dst_app.state.reputation.verify_chain() is True


def test_import_dedupes(enable_federation):
    src_app = create_app(seed=True, auth=False)
    _settled(src_app)
    bundle = src_app.state.reputation.export_bundle()

    dst_app = create_app(seed=True, auth=False)
    rep = dst_app.state.reputation
    first = rep.import_external_bundle(bundle)
    second = rep.import_external_bundle(bundle)
    assert len(first) >= 2
    assert second == []
