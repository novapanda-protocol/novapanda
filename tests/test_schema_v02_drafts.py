"""v0.2 informative schemas：exchange · agent-manifest。"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from novapanda.identity import Identity
from novapanda.manifest import build_agent_manifest
from novapanda.settlement import MockSettlement
from novapanda.exchange import ExchangeEngine

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "spec" / "schemas"


def _load(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_agent_manifest_schema_accepts_built_manifest():
    schema = _load("agent-manifest.schema.json")
    m = build_agent_manifest(
        Identity.generate(),
        capabilities=[{
            "resource_type": "energy.electric.dc",
            "rules": ["R-energy-dc-meter-v1"],
            "price": {"amount": 1, "currency": "USD"},
        }],
        exchange_endpoint="http://x/exchanges",
        profiles=["NP-MIN", "NP-PHYS", "NP-LITE"],
        lite={"tier": "edge", "canonical": "novapanda-c1", "offline_queue": True},
    )
    Draft202012Validator(schema).validate(m)


def test_exchange_schema_accepts_engine_row():
    schema = _load("exchange.schema.json")
    eng = ExchangeEngine(MockSettlement())
    client, provider = Identity.generate(), Identity.generate()
    ex = eng.propose(
        client=client.agent_id,
        provider=provider.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 10, "currency": "USD"},
        idempotency_key="schema-ex-1",
    )
    from dataclasses import asdict

    row = asdict(ex)
    # deadline_ts 等为 float，schema additionalProperties 允许
    Draft202012Validator(schema).validate(row)


def test_second_impl_checklist_json_well_formed():
    doc = json.loads(
        (ROOT / "conformance" / "second_impl_checklist.json").read_text(encoding="utf-8")
    )
    assert doc["checklist_version"]
    assert len(doc["must"]) >= 5
    assert "SI-01" in {x["id"] for x in doc["must"]}


def test_lite_embedded_checklist_json_well_formed():
    doc = json.loads(
        (ROOT / "conformance" / "lite_embedded_checklist.json").read_text(encoding="utf-8")
    )
    assert doc["profile"] == "NP-LITE"
    assert "LE-01" in {x["id"] for x in doc["must"]}
    assert (ROOT / "docs" / "lite-embedded-boundary.md").is_file()


def test_adapter_author_checklist_listed_in_conformance():
    assert (ROOT / "conformance" / "adapter_author_checklist.json").is_file()
