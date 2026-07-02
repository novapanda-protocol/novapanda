import json

from fastapi.testclient import TestClient

from novapanda import state_machine as sm
from novapanda import vdc as V
from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.settlement import MockSettlement
from novapanda.store import SQLiteStore
from tests.helpers import dual_contract_engine

GOOD = {"invoice_no": "V-1", "total": "100.00", "currency": "USD"}
RULE = "R-extract-invoice-v1"


def _propose(engine, client, provider, idem="vdc-t1"):
    return engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id=RULE,
        price={"amount": 100, "currency": "USD"}, idempotency_key=idem,
    )


def test_vdc_stored_in_separate_table_not_in_exchange_json(tmp_path):
    db = str(tmp_path / "vdc.db")
    store = SQLiteStore(db)
    engine = ExchangeEngine(MockSettlement(), store=store)
    client, provider = Identity.generate(), Identity.generate()

    ex = _propose(engine, client, provider)
    eid = ex.exchange_id
    dual_contract_engine(engine, eid, client, provider)
    engine.escrow(eid, amount=100, currency="USD")
    engine.deliver(eid, provider, GOOD)
    engine.verify(eid)
    settled = engine.confirm(eid, client)

    row = store._cx.execute(
        "SELECT data FROM exchanges WHERE id=?", (eid,)
    ).fetchone()[0]
    payload = json.loads(row)
    assert payload.get("vdc") is None
    assert payload.get("vdc_id") == settled.vdc["vdc_id"]

    vdc_row = store._cx.execute(
        "SELECT data FROM vdcs WHERE vdc_id=?", (settled.vdc["vdc_id"],)
    ).fetchone()
    assert vdc_row is not None
    assert json.loads(vdc_row[0])["state"] == sm.SETTLED


def test_vdc_survives_engine_restart(tmp_path):
    db = str(tmp_path / "vdc2.db")
    client, provider = Identity.generate(), Identity.generate()

    engine1 = ExchangeEngine(MockSettlement(), store=SQLiteStore(db))
    ex = _propose(engine1, client, provider, idem="vdc-restart")
    eid = ex.exchange_id
    dual_contract_engine(engine1, eid, client, provider)
    engine1.escrow(eid, amount=100, currency="USD")
    engine1.deliver(eid, provider, GOOD)
    engine1.verify(eid)
    settled = engine1.confirm(eid, client)
    vid = settled.vdc["vdc_id"]

    engine2 = ExchangeEngine(MockSettlement(), store=SQLiteStore(db))
    assert engine2.find_vdc(vid)["vdc_id"] == vid
    reloaded = engine2.get(eid)
    assert reloaded.vdc is not None
    assert V.is_valid_settled(reloaded.vdc)


def test_get_vdc_api_uses_table():
    app = create_app(seed=True, auth=False, store=SQLiteStore(":memory:"))
    tc = TestClient(app)
    engine = app.state.engine
    client, provider = Identity.generate(), Identity.generate()
    ex = _propose(engine, client, provider, idem="vdc-api")
    eid = ex.exchange_id
    dual_contract_engine(engine, eid, client, provider)
    engine.escrow(eid, amount=100, currency="USD")
    engine.deliver(eid, provider, GOOD)
    rule = app.state.rules.get(RULE)
    engine.verify(eid, rule=rule)
    settled = engine.confirm(eid, client)
    vid = settled.vdc["vdc_id"]

    r = tc.get(f"/vdc/{vid}")
    assert r.status_code == 200
    assert r.json()["vdc_id"] == vid
