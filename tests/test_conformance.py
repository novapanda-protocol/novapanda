import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from troodon import vdc as V
from troodon.exchange import ExchangeEngine
from troodon.hashing import result_hash_of_json
from troodon.identity import Identity
from troodon.reputation import ReputationLog
from troodon.settlement import MockSettlement
from tests.helpers import dual_contract_engine

SCHEMAS = Path(__file__).parents[1] / "spec" / "schemas"


def _load(name):
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def _settled_vdc():
    client, provider = Identity.generate(), Identity.generate()
    deliverable = {"invoice_no": "A-001", "total": "100.00", "currency": "USD"}
    doc = V.build_vdc(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        result_hash=result_hash_of_json(deliverable), rule_id="R-extract-invoice-v1",
        evidence_level="dual_signed", started_at="2026-06-28T00:00:00Z",
        finished_at="2026-06-28T00:00:01Z", idempotency_key="k", state="DELIVERED",
    )
    V.provider_sign(doc, provider)
    V.client_sign(doc, client)
    doc["state"] = "SETTLED"
    return doc


def test_produced_vdc_conforms_to_schema():
    validator = Draft202012Validator(_load("vdc.schema.json"))
    errors = list(validator.iter_errors(_settled_vdc()))
    assert errors == [], [e.message for e in errors]


def test_schema_rejects_malformed_vdc():
    validator = Draft202012Validator(_load("vdc.schema.json"))
    bad = _settled_vdc()
    del bad["result_hash"]
    assert list(validator.iter_errors(bad)) != []


def test_reputation_entries_conform_to_schema():
    node = Identity.generate()
    log = ReputationLog(node)
    client, provider = Identity.generate(), Identity.generate()
    engine = ExchangeEngine(MockSettlement(), reputation=log)

    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="c1",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"invoice_no": "A-1"})
    engine.verify(ex.exchange_id)
    engine.confirm(ex.exchange_id, client)

    validator = Draft202012Validator(_load("reputation-entry.schema.json"))
    entries = log.entries()
    assert entries
    for entry in entries:
        errors = list(validator.iter_errors(entry))
        assert errors == [], [e.message for e in errors]
