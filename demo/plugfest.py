"""Plugfest 脚本：单节点 + 多节点联邦 + 能源物理场景冒烟。

运行：

    python demo/plugfest.py
"""

from __future__ import annotations

import json
import sys

from fastapi.testclient import TestClient

from troodon import vdc as V
from troodon.identity import Identity
from troodon.manifest import build_agent_manifest, verify_agent_manifest
from troodon.node import create_app
from troodon.reverify import reverify
from troodon.sdk import TroodonClient
from troodon.store import SQLiteStore
from troodon.verifier import make_verifier

RULE_ID = "R-extract-invoice-v1"
RESOURCE = "data.extraction.structured"
PRICE = {"amount": 100, "currency": "USD"}
GOOD = {"invoice_no": "PF-001", "total": "100.00", "currency": "USD"}

ENERGY_RULE = "R-energy-dc-meter-v1"
ENERGY_RESOURCE = "energy.electric.dc"
ENERGY_PRICE = {"amount": 1050, "currency": "USD"}
ENERGY_DELIVERABLE = {
    "session_id": "pf-sess-001",
    "kwh_delivered": "10.500",
    "meter_signature": "meter-sig-demo",
}

ACTUATION_RULE = "R-actuation-task-v1"
ACTUATION_RESOURCE = "actuation.robot.task"
ACTUATION_PRICE = {"amount": 500, "currency": "USD"}
ACTUATION_DELIVERABLE = {
    "task_id": "pf-robot-001",
    "completion_proof": "proof-hash-plugfest",
    "duration_secs": 90,
}

FIELD_MATCH_RULE = "R-task-status-v1"
FIELD_MATCH_RESOURCE = "service.task.generic"
FIELD_MATCH_PRICE = {"amount": 80, "currency": "USD"}
FIELD_MATCH_DELIVERABLE = {"status": "done", "score": "A"}


def _lifecycle(client: TroodonClient, provider: TroodonClient, manifest: dict,
               idem: str, tc: TestClient) -> dict:
    cap = manifest["capabilities"][0]
    ex = client.propose(
        provider=manifest["agent_id"],
        resource_type=cap["resource_type"],
        quantity=1,
        rule_id=cap["rules"][0],
        price=cap["price"],
        idempotency_key=idem,
    )
    eid = ex["exchange_id"]
    client.contract(eid)
    provider.contract(eid)
    client.escrow(eid, amount=100, currency="USD")
    provider.deliver(eid, GOOD)
    verified = client.verify(eid)
    settled = client.confirm(eid)

    assert settled["state"] == "SETTLED"
    assert V.is_valid_settled(settled["vdc"])

    pub_verify = tc.post(
        f"/exchanges/{eid}/deliverable/verify", json={"deliverable": GOOD}
    ).json()
    assert pub_verify["matches"] is True

    checks = reverify(settled["vdc"], GOOD, verified.get("verify_result"))
    from troodon.reverify import _all_ok

    return {
        "exchange_id": eid,
        "vdc_id": settled["vdc"]["vdc_id"],
        "vdc": settled["vdc"],
        "verify_result": verified.get("verify_result"),
        "public_hash_verify": pub_verify,
        "reverify": checks,
        "reverify_ok": _all_ok(checks),
    }


def run_single_node() -> bool:
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    client = TroodonClient("http://testserver", Identity.generate(), http=tc)
    provider = TroodonClient("http://testserver", Identity.generate(), http=tc)

    manifest = build_agent_manifest(
        provider.identity,
        capabilities=[{"resource_type": RESOURCE, "rules": [RULE_ID], "price": PRICE}],
        exchange_endpoint="http://testserver/exchanges",
    )
    assert verify_agent_manifest(manifest)

    result = _lifecycle(client, provider, manifest, "plugfest-single", tc)
    print(json.dumps({"scenario": "single_node", **result}, ensure_ascii=False, indent=2))
    return result["reverify_ok"]


def run_federation() -> bool:
    """多节点联邦：交换在 provider 节点完成；client 节点独立拉 VDC 并复验。"""
    provider_store = SQLiteStore(":memory:")
    client_store = SQLiteStore(":memory:")

    provider_app = create_app(seed=True, auth=False, store=provider_store)
    client_app = create_app(seed=True, auth=False, store=client_store)

    provider_tc = TestClient(provider_app)
    client_tc = TestClient(client_app)

    client_id = Identity.generate()
    provider_id = Identity.generate()

    client_sdk = TroodonClient("http://provider", client_id, http=provider_tc)
    provider_sdk = TroodonClient("http://provider", provider_id, http=provider_tc)

    node_manifest = provider_tc.get("/.well-known/troodon.json").json()
    assert node_manifest["protocol"] == "troodon"

    agent_manifest = build_agent_manifest(
        provider_id,
        capabilities=[{"resource_type": RESOURCE, "rules": [RULE_ID], "price": PRICE}],
        exchange_endpoint="http://provider/exchanges",
    )
    assert verify_agent_manifest(agent_manifest)

    result = _lifecycle(client_sdk, provider_sdk, agent_manifest, "plugfest-fed", provider_tc)
    vdc_id = result["vdc_id"]
    eid = result["exchange_id"]

    remote_vdc = provider_tc.get(f"/vdc/{vdc_id}").json()
    assert remote_vdc["vdc_id"] == vdc_id
    assert V.is_valid_settled(remote_vdc)

    assert client_tc.get(f"/vdc/{vdc_id}").status_code == 404

    cross_checks = reverify(remote_vdc, GOOD, result.get("verify_result"))
    from troodon.reverify import _all_ok

    cross_ok = _all_ok(cross_checks)

    rep_bundle = provider_tc.get("/reputation/export").json()
    rep_valid = client_tc.post(
        "/v2/reputation/validate", json={"bundle": rep_bundle}
    ).json()
    assert rep_valid["valid"] is True

    export = provider_tc.get(f"/exchanges/{eid}/export").json()
    assert export["vdc"]["vdc_id"] == vdc_id

    ex_row = provider_store._cx.execute(
        "SELECT data FROM exchanges WHERE id=?", (eid,)
    ).fetchone()[0]
    assert '"vdc_id"' in ex_row
    assert '"vdc":' not in ex_row or '"vdc": null' in ex_row

    print(json.dumps({
        "scenario": "federation",
        "provider_node": node_manifest["node_id"],
        "client_node": client_tc.get("/.well-known/troodon.json").json()["node_id"],
        "exchange_id": eid,
        "vdc_fetched_cross_node": True,
        "client_node_has_vdc": False,
        "vdc_independent_table": True,
        "cross_reverify_ok": cross_ok,
        "reputation_cross_validated": rep_valid["valid"],
        "export_has_vdc": export["vdc"]["vdc_id"] == vdc_id,
        "cross_reverify": cross_checks,
    }, ensure_ascii=False, indent=2))
    return cross_ok


def run_energy() -> bool:
    """能源物理场景：R-energy-dc-meter-v1 + /v3/physical/validate + 全生命周期。"""
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    client = TroodonClient("http://testserver", Identity.generate(), http=tc)
    provider = TroodonClient("http://testserver", Identity.generate(), http=tc)

    manifest = build_agent_manifest(
        provider.identity,
        capabilities=[{
            "resource_type": ENERGY_RESOURCE,
            "rules": [ENERGY_RULE],
            "price": ENERGY_PRICE,
        }],
        exchange_endpoint="http://testserver/exchanges",
    )
    assert verify_agent_manifest(manifest)

    phys = tc.post("/v3/physical/validate", json={
        "resource_type": ENERGY_RESOURCE,
        "deliverable": ENERGY_DELIVERABLE,
    }).json()
    assert phys["valid"] is True

    ex = client.propose(
        provider=manifest["agent_id"],
        resource_type=ENERGY_RESOURCE,
        quantity=1,
        rule_id=ENERGY_RULE,
        price=ENERGY_PRICE,
        idempotency_key="plugfest-energy",
    )
    eid = ex["exchange_id"]
    client.contract(eid)
    provider.contract(eid)
    client.escrow(eid, amount=ENERGY_PRICE["amount"], currency=ENERGY_PRICE["currency"])
    provider.deliver(eid, ENERGY_DELIVERABLE)
    verified = client.verify(eid)
    assert verified["state"] == "VERIFIED"
    assert verified["verify_result"]["passed"] is True

    settled = client.confirm(eid)
    assert settled["state"] == "SETTLED"
    assert V.is_valid_settled(settled["vdc"])

    checks = reverify(settled["vdc"], ENERGY_DELIVERABLE, verified.get("verify_result"))
    from troodon.reverify import _all_ok

    ok = _all_ok(checks)
    print(json.dumps({
        "scenario": "energy_dc",
        "exchange_id": eid,
        "physical_validate": phys,
        "verify_result": verified.get("verify_result"),
        "reverify_ok": ok,
    }, ensure_ascii=False, indent=2))
    return ok


def run_actuation() -> bool:
    """机器人 actuation 物理场景：R-actuation-task-v1 全生命周期。"""
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    client = TroodonClient("http://testserver", Identity.generate(), http=tc)
    provider = TroodonClient("http://testserver", Identity.generate(), http=tc)

    manifest = build_agent_manifest(
        provider.identity,
        capabilities=[{
            "resource_type": ACTUATION_RESOURCE,
            "rules": [ACTUATION_RULE],
            "price": ACTUATION_PRICE,
        }],
        exchange_endpoint="http://testserver/exchanges",
    )

    phys = tc.post("/v3/physical/validate", json={
        "resource_type": ACTUATION_RESOURCE,
        "deliverable": ACTUATION_DELIVERABLE,
    }).json()
    assert phys["valid"] is True

    ex = client.propose(
        provider=manifest["agent_id"],
        resource_type=ACTUATION_RESOURCE,
        quantity=1,
        rule_id=ACTUATION_RULE,
        price=ACTUATION_PRICE,
        idempotency_key="plugfest-actuation",
    )
    eid = ex["exchange_id"]
    client.contract(eid)
    provider.contract(eid)
    client.escrow(eid, amount=ACTUATION_PRICE["amount"], currency=ACTUATION_PRICE["currency"])
    provider.deliver(eid, ACTUATION_DELIVERABLE)
    verified = client.verify(eid)
    assert verified["state"] == "VERIFIED"
    settled = client.confirm(eid)
    assert settled["state"] == "SETTLED"

    checks = reverify(settled["vdc"], ACTUATION_DELIVERABLE, verified.get("verify_result"))
    from troodon.reverify import _all_ok

    ok = _all_ok(checks)
    print(json.dumps({
        "scenario": "actuation_robot",
        "exchange_id": eid,
        "physical_validate": phys,
        "reverify_ok": ok,
    }, ensure_ascii=False, indent=2))
    return ok


def run_field_match() -> bool:
    """field_match LLM judge：schema 预检 + R-task-status-v1 全生命周期。"""
    verifier = make_verifier("llm", llm_judge="field_match")
    app = create_app(seed=True, auth=False, verifier=verifier)
    tc = TestClient(app)
    client = TroodonClient("http://testserver", Identity.generate(), http=tc)
    provider = TroodonClient("http://testserver", Identity.generate(), http=tc)

    manifest = build_agent_manifest(
        provider.identity,
        capabilities=[{
            "resource_type": FIELD_MATCH_RESOURCE,
            "rules": [FIELD_MATCH_RULE],
            "price": FIELD_MATCH_PRICE,
        }],
        exchange_endpoint="http://testserver/exchanges",
    )

    ex = client.propose(
        provider=manifest["agent_id"],
        resource_type=FIELD_MATCH_RESOURCE,
        quantity=1,
        rule_id=FIELD_MATCH_RULE,
        price=FIELD_MATCH_PRICE,
        idempotency_key="plugfest-field-match",
    )
    eid = ex["exchange_id"]
    client.contract(eid)
    provider.contract(eid)
    client.escrow(eid, amount=FIELD_MATCH_PRICE["amount"], currency=FIELD_MATCH_PRICE["currency"])
    provider.deliver(eid, FIELD_MATCH_DELIVERABLE)
    verified = client.verify(eid)
    assert verified["state"] == "VERIFIED"
    assert verified["verify_result"]["passed"] is True
    assert verified["verify_result"]["llm_audit"]["schema_preflight"] == "passed"

    settled = client.confirm(eid)
    assert settled["state"] == "SETTLED"
    assert V.is_valid_settled(settled["vdc"])

    print(json.dumps({
        "scenario": "field_match_llm",
        "exchange_id": eid,
        "verify_result": verified.get("verify_result"),
    }, ensure_ascii=False, indent=2))
    return True


LLM_HTTP_RULE = "R-llm-summary-v1"
LLM_HTTP_RESOURCE = "service.task.generic"
LLM_HTTP_PRICE = {"amount": 50, "currency": "USD"}
LLM_HTTP_DELIVERABLE = {"summary": "PASS: plugfest openai compat gateway"}


def run_llm_http_gateway() -> bool:
    """OpenAI-compat HTTP LLM gateway 全链：fake /v1/chat/completions + schema 预检。"""
    from troodon.llm_fake import create_llm_fake_app

    fake = create_llm_fake_app(mode="regex")
    fake_tc = TestClient(fake)
    verifier = make_verifier(
        "llm",
        llm_judge="openai",
        llm_gateway_url="http://testserver",
        llm_gateway_http=fake_tc,
    )
    app = create_app(seed=True, auth=False, verifier=verifier)
    tc = TestClient(app)
    client = TroodonClient("http://testserver", Identity.generate(), http=tc)
    provider = TroodonClient("http://testserver", Identity.generate(), http=tc)

    manifest = build_agent_manifest(
        provider.identity,
        capabilities=[{
            "resource_type": LLM_HTTP_RESOURCE,
            "rules": [LLM_HTTP_RULE],
            "price": LLM_HTTP_PRICE,
        }],
        exchange_endpoint="http://testserver/exchanges",
    )
    assert verify_agent_manifest(manifest)
    assert manifest.get("did")

    ex = client.propose(
        provider=manifest["agent_id"],
        resource_type=LLM_HTTP_RESOURCE,
        quantity=1,
        rule_id=LLM_HTTP_RULE,
        price=LLM_HTTP_PRICE,
        idempotency_key="plugfest-llm-openai",
    )
    eid = ex["exchange_id"]
    client.contract(eid)
    provider.contract(eid)
    client.escrow(eid, amount=LLM_HTTP_PRICE["amount"], currency=LLM_HTTP_PRICE["currency"])
    provider.deliver(eid, LLM_HTTP_DELIVERABLE)
    verified = client.verify(eid)
    assert verified["state"] == "VERIFIED"
    assert verified["verify_result"]["llm_audit"]["schema_preflight"] == "passed"
    assert verified["verify_result"]["llm_audit"].get("gateway") == "openai-compat"

    settled = client.confirm(eid)
    assert settled["state"] == "SETTLED"
    assert V.is_valid_settled(settled["vdc"])

    print(json.dumps({
        "scenario": "llm_http_openai",
        "exchange_id": eid,
        "verify_result": verified.get("verify_result"),
    }, ensure_ascii=False, indent=2))
    return True


def run_witness_stake() -> bool:
    """witness v2 + stake lock：TROODON_WITNESS_V2=1 多步场景。"""
    from troodon.v2 import witness as witness_mod
    from troodon.v2.witness import build_witness_attestation, witness_sign

    witness_mod.WITNESS_V2_ENABLED = True
    try:
        app = create_app(seed=True, auth=False)
        tc = TestClient(app)
        client = TroodonClient("http://testserver", Identity.generate(), http=tc)
        provider = TroodonClient("http://testserver", Identity.generate(), http=tc)

        manifest = build_agent_manifest(
            provider.identity,
            capabilities=[{"resource_type": RESOURCE, "rules": [RULE_ID], "price": PRICE}],
            exchange_endpoint="http://testserver/exchanges",
        )
        ex = client.propose(
            provider=manifest["agent_id"],
            resource_type=RESOURCE,
            quantity=1,
            rule_id=RULE_ID,
            price=PRICE,
            idempotency_key="plugfest-witness-stake",
        )
        eid = ex["exchange_id"]
        client.contract(eid)
        provider.contract(eid)
        client.escrow(eid, amount=100, currency="USD")
        provider.deliver(eid, GOOD)

        engine = app.state.engine
        vdc = engine.get(eid).vdc
        witness = Identity.generate()
        att = build_witness_attestation(
            vdc_id=vdc["vdc_id"],
            witness=witness,
            claim="plugfest witness",
            vdc_result_hash=vdc["result_hash"],
        )
        witness_sign(att, witness)
        attach = tc.post(f"/exchanges/{eid}/v2/witness/attach", json={"attestation": att})
        assert attach.status_code == 200
        updated = engine.get(eid).vdc
        assert updated["evidence"]["level"] == "third_party_witnessed"

        stake = tc.post("/v2/stake/lock", json={
            "agent_id": witness.agent_id,
            "amount": 50,
            "currency": "USD",
            "purpose": "witness bond",
            "exchange_id": eid,
            "vdc_id": vdc["vdc_id"],
        })
        assert stake.status_code == 200
        assert stake.json().get("stake_id")

        print(json.dumps({
            "scenario": "witness_stake",
            "exchange_id": eid,
            "witness": witness.agent_id,
            "stake_id": stake.json().get("stake_id"),
        }, ensure_ascii=False, indent=2))
        return True
    finally:
        witness_mod.WITNESS_V2_ENABLED = False


def run_confirm_timeout() -> bool:
    """VERIFIED 后 confirm 超时：sweep 触发 EXPIRED_REFUNDED + 退款。"""
    from troodon import state_machine as sm
    from troodon.settlement import MockSettlement

    settlement = MockSettlement()
    app = create_app(seed=True, auth=False, settlement=settlement)
    tc = TestClient(app)
    client = TroodonClient("http://testserver", Identity.generate(), http=tc)
    provider = TroodonClient("http://testserver", Identity.generate(), http=tc)

    manifest = build_agent_manifest(
        provider.identity,
        capabilities=[{"resource_type": RESOURCE, "rules": [RULE_ID], "price": PRICE}],
        exchange_endpoint="http://testserver/exchanges",
    )
    ex = client.propose(
        provider=manifest["agent_id"],
        resource_type=RESOURCE,
        quantity=1,
        rule_id=RULE_ID,
        price=PRICE,
        idempotency_key="plugfest-confirm-timeout",
        timeouts={"confirm": 30},
    )
    eid = ex["exchange_id"]
    client.contract(eid)
    provider.contract(eid)
    client.escrow(eid, amount=100, currency="USD")
    provider.deliver(eid, GOOD)
    verified = client.verify(eid)
    assert verified["state"] == sm.VERIFIED

    engine = app.state.engine
    row = engine.get(eid)
    assert row.deadline_ts is not None
    expired = engine.sweep(now_ts=row.deadline_ts + 1)
    assert [e.exchange_id for e in expired] == [eid]
    assert row.state == sm.EXPIRED_REFUNDED
    assert settlement.status(row.escrow_handle) == "refunded"

    print(json.dumps({
        "scenario": "confirm_timeout",
        "exchange_id": eid,
        "final_state": row.state,
        "escrow_status": settlement.status(row.escrow_handle),
    }, ensure_ascii=False, indent=2))
    return True


def run() -> bool:
    ok_single = run_single_node()
    ok_fed = run_federation()
    ok_energy = run_energy()
    ok_actuation = run_actuation()
    ok_field_match = run_field_match()
    ok_llm_http = run_llm_http_gateway()
    ok_witness = run_witness_stake()
    ok_confirm = run_confirm_timeout()
    return (
        ok_single
        and ok_fed
        and ok_energy
        and ok_actuation
        and ok_field_match
        and ok_llm_http
        and ok_witness
        and ok_confirm
    )


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
