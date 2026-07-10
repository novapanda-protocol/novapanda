"""T15–T18 integration smoke."""

from fastapi.testclient import TestClient

from conformance.gap_audit import audit
from novapanda.node import create_app


def test_t15_gap_audit_ok():
    report = audit()
    assert report["ok"] is True
    assert "C11" in report["wired"]
    assert "C12" in report["wired"]


def test_t16_spec_volumes_exist():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "spec"
    for name in ("README.md", "CORE.md", "NP-HTTP.md", "NP-OPS.md", "NP-V2.md", "SPEC.md"):
        assert (root / name).is_file(), name
    index = (root / "SPEC.md").read_text(encoding="utf-8")
    assert "CORE.md" in index


def test_t17_admin_recover_and_intents():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    intents = tc.get("/admin/settlement/intents")
    assert intents.status_code == 200
    assert "stale_pending" in intents.json()
    rec = tc.post("/admin/recover")
    assert rec.status_code == 200
    assert rec.json()["ok"] is True


def test_t17_stale_alert_after_injected_pending(tmp_path):
    from novapanda.exchange import ExchangeEngine
    from novapanda.identity import Identity
    from novapanda.settlement import MockSettlement
    from novapanda import state_machine as sm
    from novapanda.store import SQLiteStore
    from tests.helpers import dual_contract_engine

    db = str(tmp_path / "rb04.db")
    s = MockSettlement()
    client, provider = Identity.generate(), Identity.generate()
    engine = ExchangeEngine(s, store=SQLiteStore(db))
    ex = engine.propose(
        client=client.agent_id,
        provider=provider.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R1",
        price={"amount": 1, "currency": "USD"},
        idempotency_key="rb04",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=1, currency="USD")
    live = engine.get(ex.exchange_id)
    engine._capture_intent(
        live,
        {"action": "settle", "handle": live.escrow_handle, "status": "pending"},
    )
    stale_ex = engine.get(ex.exchange_id)
    stale_ex.updated_at = "2020-01-01T00:00:00Z"
    engine._store.save(stale_ex)
    app = create_app(seed=True, auth=False)
    app.state.engine = engine
    app.state.settlement = s
    tc = TestClient(app)
    health = tc.get("/admin/settlement/intents").json()
    assert health["stale_pending_count"] >= 1
    rec = tc.post("/admin/recover").json()
    assert live.exchange_id in rec["recovered"]
