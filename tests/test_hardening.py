import json
import secrets

from fastapi.testclient import TestClient

from troodon.auth import sign_request
from troodon.identity import Identity
from troodon.node import create_app
from troodon.store import SQLiteStore


def test_auth_enabled_by_default():
    app = create_app(seed=True)
    assert app.state.auth_enabled is True


def test_nonce_persists_across_app_instances(tmp_path):
    db = str(tmp_path / "nonce.db")
    store = SQLiteStore(db)
    app1 = create_app(seed=True, store=store)
    tc1 = TestClient(app1)
    client = Identity.generate()
    body = json.dumps({"client": client.agent_id, "provider": client.agent_id,
                       "resource_type": "data.extraction.structured", "quantity": 1,
                       "rule_id": "R-extract-invoice-v1",
                       "price": {"amount": 1, "currency": "USD"},
                       "idempotency_key": "n1"}).encode()
    nonce = secrets.token_hex(16)
    headers = {"Content-Type": "application/json", "X-Agent-Id": client.agent_id,
               "X-Nonce": nonce,
               "X-Signature": sign_request(client, "POST", "/exchanges", nonce, body)}
    assert tc1.post("/exchanges", content=body, headers=headers).status_code == 201

    # 新进程/新 app 实例，同一 SQLite：同 nonce 重放 MUST 409
    app2 = create_app(seed=True, store=SQLiteStore(db))
    tc2 = TestClient(app2)
    r = tc2.post("/exchanges", content=body, headers=headers)
    assert r.status_code == 409
    assert r.json()["code"] == "E_REPLAY"


def test_startup_recover_runs_on_lifespan(tmp_path):
    """lifespan 启动时 recover() 应被调用（通过 pending intent 副作用验证）。"""
    db = str(tmp_path / "rec.db")
    store = SQLiteStore(db)
    from troodon import state_machine as sm
    from troodon.exchange import ExchangeEngine
    from troodon.settlement import MockSettlement
    from tests.helpers import dual_contract_engine

    settlement = MockSettlement()
    client, provider = Identity.generate(), Identity.generate()
    engine1 = ExchangeEngine(settlement, store=store)
    ex = engine1.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="life",
    )
    dual_contract_engine(engine1, ex.exchange_id, client, provider)
    engine1.escrow(ex.exchange_id, amount=100, currency="USD")
    engine1.deliver(ex.exchange_id, provider, {"invoice_no": "A-1"})
    engine1.verify(ex.exchange_id)
    live = engine1.get(ex.exchange_id)
    engine1._capture_intent(live, {"action": "settle", "handle": live.escrow_handle, "status": "pending"})
    assert engine1.get(ex.exchange_id).state == sm.VERIFIED

    # 新 app 启动 -> lifespan recover（共享同一 settlement 实例）
    app = create_app(seed=True, store=SQLiteStore(db), settlement=settlement)
    with TestClient(app) as tc:
        tc.get("/.well-known/troodon.json")
    final = SQLiteStore(db).get(ex.exchange_id)
    assert final.state == sm.SETTLED
    assert settlement.status(live.escrow_handle) == "settled"
