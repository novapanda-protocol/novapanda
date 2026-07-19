"""Adopter Skill：Function Calling 工具面。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from novapanda.adopter import (
    ADOPTER_TOOL_DEFINITIONS,
    AdopterRuntime,
    AdopterSkill,
    StationRecord,
    adopter_tool_names,
)
from novapanda.adopter.charge import ENERGY_RESOURCE, ENERGY_RULE
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.sdk import NovaPandaClient


def test_adopter_tool_definitions_llm_friendly():
    names = adopter_tool_names()
    assert "adopter_apply_intent" in names
    assert "adopter_discover_stations" in names
    for spec in ADOPTER_TOOL_DEFINITIONS:
        assert len(spec["description"]) > 40
        assert spec["parameters"]["type"] == "object"
        # 产品面：明确不是记账六接口
        assert "novapanda_create" not in spec["name"]


def test_adopter_skill_parse_and_discover(tmp_path: Path):
    app = create_app(seed=True, auth=False, marketplace_enabled=False)
    tc = TestClient(app)
    rt = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        tmp_path / "car",
    )
    pile = Identity.generate().agent_id
    rt.register_station(StationRecord(
        station_id="st-skill",
        agent_id=pile,
        resource_type=ENERGY_RESOURCE,
        rule_id_hint=ENERGY_RULE,
        tags=["energy", "charging"],
    ))
    skill = AdopterSkill(rt)
    assert skill.invoke("adopter_list_tools")["ok"] is True
    parsed = skill.invoke("adopter_parse_intent", {"text": "确认"})
    assert parsed["ok"] and parsed["result"]["action"] == "confirm"
    found = skill.invoke("adopter_discover_stations", {"prefer_marketplace": False})
    assert found["ok"]
    assert found["result"]["winner_agent_id"] == pile


def test_adopter_skill_export_after_simple_settle(tmp_path: Path):
    """最小软件腿：propose…SETTLED 后 Skill 导出。"""
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    buyer = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        tmp_path / "buyer",
    )
    seller = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        tmp_path / "seller",
    )
    good = {"invoice_no": "SK-1", "total": "10.00", "currency": "USD"}
    draft = seller.open_draft(
        peer_id=buyer.agent_id,
        resource_type="data.extraction.structured",
        rule_id="R-extract-invoice-v1",
    )
    ex = buyer.client.propose(
        provider=seller.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 10, "currency": "USD"},
        idempotency_key="skill-ut-1",
    )
    eid = ex["exchange_id"]
    seller.drafts.bind_exchange(draft.draft_id, eid)
    buyer.client.contract(eid)
    seller.client.contract(eid)
    buyer.client.escrow(eid, amount=10, currency="USD")
    seller.prepare_deliverable(draft.draft_id, good)
    seller.deliver_from_draft(draft.draft_id)
    buyer.verify(eid)
    buyer.confirm(eid)
    buyer.remember_settled(eid, role="client", deliverable=good)

    skill = AdopterSkill(buyer)
    out = skill.invoke("adopter_export_pack", {"exchange_id": eid})
    assert out["ok"] is True
    assert out["result"]["fingerprint"].startswith("sha256:")
    anc = skill.invoke("adopter_anchor", {"exchange_id": eid, "multi": False})
    assert anc["ok"] is True
