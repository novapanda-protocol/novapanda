from novapanda.blobs import InMemoryBlobStore, SQLiteBlobStore
from novapanda.exchange import ExchangeEngine
from novapanda.hashing import result_hash_of_json
from novapanda.identity import Identity
from novapanda.registry import load_default_registries
from novapanda.settlement import MockSettlement
from novapanda.store import SQLiteStore
from novapanda.verifier import SchemaVerifier
from tests.helpers import dual_contract_engine

GOOD = {"invoice_no": "A-001", "total": "100.00", "currency": "USD"}


def test_content_addressed_ref_matches_result_hash(tmp_path):
    db = str(tmp_path / "b.db")
    store = SQLiteStore(db)
    blobs = SQLiteBlobStore(db)
    _, rules = load_default_registries()
    rule = rules.get("R-extract-invoice-v1")
    engine = ExchangeEngine(MockSettlement(), verifier=SchemaVerifier(),
                            store=store, blob_store=blobs)
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="blob-1",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, GOOD)

    persisted = store.get(ex.exchange_id)
    assert persisted.deliverable is None
    assert persisted.deliverable_ref == result_hash_of_json(GOOD)
    assert persisted.deliverable_ref == persisted.result_hash
    assert blobs.has(persisted.deliverable_ref)

    ex2 = ExchangeEngine(MockSettlement(), verifier=SchemaVerifier(),
                         store=SQLiteStore(db), blob_store=SQLiteBlobStore(db))
    verified = ex2.verify(ex.exchange_id, rule=rule)
    assert verified.state == "VERIFIED"


def test_blob_dedup_same_content():
    blobs = InMemoryBlobStore()
    ref1 = blobs.put("ex-1", GOOD)
    ref2 = blobs.put("ex-2", GOOD)
    assert ref1 == ref2


def test_inmemory_blob_get_deliverable():
    blobs = InMemoryBlobStore()
    engine = ExchangeEngine(MockSettlement(), blob_store=blobs)
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 1, "currency": "USD"}, idempotency_key="blob-mem",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=1, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"x": 1})
    assert engine.get_deliverable(ex.exchange_id) == {"x": 1}


def test_public_deliverable_verify_endpoint(tmp_path):
    from fastapi.testclient import TestClient

    from novapanda.node import create_app
    from novapanda.sdk import NovaPandaClient

    db = str(tmp_path / "api.db")
    store = SQLiteStore(db)
    blobs = SQLiteBlobStore(db)
    app = create_app(seed=True, auth=False, store=store, blob_store=blobs)
    tc = TestClient(app)
    client = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    provider = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    ex = client.propose(
        provider=provider.agent_id, resource_type="data.extraction.structured",
        quantity=1, rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="blob-api",
    )
    eid = ex["exchange_id"]
    client.contract(eid)
    provider.contract(eid)
    client.escrow(eid, amount=100, currency="USD")
    provider.deliver(eid, GOOD)

    got = tc.get(f"/exchanges/{eid}/deliverable").json()
    assert got == GOOD

    ok = tc.post(f"/exchanges/{eid}/deliverable/verify", json={"deliverable": GOOD}).json()
    assert ok["matches"] is True
    bad = tc.post(f"/exchanges/{eid}/deliverable/verify",
                  json={"deliverable": {"invoice_no": "x"}}).json()
    assert bad["matches"] is False
