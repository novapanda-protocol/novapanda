from troodon.identity import Identity
from troodon.node import create_app
from troodon.reputation import ReputationLog
from troodon.v2.reputation_agg import aggregate_reputation_bundles
from tests.helpers import dual_contract_engine

GOOD = {"invoice_no": "A-1", "total": "100.00", "currency": "USD"}


def _bundle_for(node: Identity) -> dict:
    log = ReputationLog(node)
    from troodon.exchange import ExchangeEngine
    from troodon.settlement import MockSettlement

    engine = ExchangeEngine(MockSettlement(), reputation=log)
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"}, idempotency_key=f"agg-{node.agent_id[-6:]}",
    )
    eid = ex.exchange_id
    dual_contract_engine(engine, eid, client, provider)
    engine.escrow(eid, amount=100, currency="USD")
    engine.deliver(eid, provider, GOOD)
    engine.verify(eid)
    engine.confirm(eid, client)
    return log.export_bundle()


def test_aggregate_weighted_scores():
    b1 = _bundle_for(Identity.generate())
    b2 = _bundle_for(Identity.generate())
    agent = b1["entries"][0]["agent_id"]
    result = aggregate_reputation_bundles(
        [b1, b2], weights={b1["source_node_id"]: 2.0, b2["source_node_id"]: 1.0}
    )
    assert result["valid"] is True
    assert agent in result["agents"]
    assert result["agents"][agent]["settled"] >= 2.0


def test_aggregate_api():
    from fastapi.testclient import TestClient

    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    bundle = _bundle_for(Identity.generate())
    r = tc.post("/v2/reputation/aggregate", json={"bundles": [bundle], "weights": {}})
    assert r.status_code == 200
    assert r.json()["valid"] is True
