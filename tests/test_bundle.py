"""C8 · NP-BUNDLE 向量：Bundle 字段 + prior_vdc_refs 复验拒收。"""

from __future__ import annotations

from novapanda.bundle import (
    bundle_ready,
    topological_order,
    validate_bundle,
    validate_prior_vdc_refs,
)
from novapanda.identity import Identity


def test_bundle_missing_fields():
    assert "missing field: goal_id" in validate_bundle({"bundle_version": "0.1"})


def test_bundle_ok_and_topo():
    doc = {
        "bundle_version": "0.1",
        "goal_id": "goal-dd",
        "correlation_id": "corr-1",
        "exchange_ids": ["ex_a", "ex_b", "ex_c"],
        "depends_on": {"ex_c": ["ex_a", "ex_b"]},
        "success_rule": "all_settled",
        "vdc_ids": [],
    }
    assert validate_bundle(doc) == []
    assert topological_order(doc)[:2] == ["ex_a", "ex_b"]
    assert topological_order(doc)[-1] == "ex_c"
    assert not bundle_ready(doc, exchange_states={"ex_a": "SETTLED", "ex_b": "SETTLED", "ex_c": "PROPOSED"})
    assert bundle_ready(
        doc,
        exchange_states={"ex_a": "SETTLED", "ex_b": "SETTLED", "ex_c": "SETTLED"},
    )


def test_prior_vdc_refs_reject_missing_required():
    errs = validate_prior_vdc_refs(
        [{"vdc_id": "missing", "required": True}],
        resolve_vdc=lambda _i: None,
    )
    assert any("not found" in e for e in errs)


def test_prior_vdc_refs_accept_valid_settled():
    client = Identity.generate()
    provider = Identity.generate()
    deliverable = {"invoice_no": "A-1", "total": "10.00", "currency": "USD"}
    # Prefer engine path for a real VDC if signing helpers are awkward
    from fastapi.testclient import TestClient
    from novapanda.node import create_app
    from novapanda.sdk import NovaPandaClient

    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    c = NovaPandaClient("http://testserver", client, http=tc)
    p = NovaPandaClient("http://testserver", provider, http=tc)
    ex = c.propose(
        provider=p.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 10, "currency": "USD"},
        idempotency_key="c8-prior-1",
    )
    eid = ex["exchange_id"]
    c.contract(eid)
    p.contract(eid)
    c.escrow(eid, amount=10, currency="USD")
    p.deliver(eid, deliverable)
    c.verify(eid)
    settled = c.confirm(eid)
    vdc = settled["vdc"]
    vdc_id = vdc.get("vdc_id") or settled.get("vdc_id") or eid

    store = {vdc_id: vdc, eid: vdc}

    def resolve(vid):
        return store.get(vid) or (vdc if vid == vdc.get("vdc_id") else None)

    # Try known keys
    candidates = [vdc.get("vdc_id"), eid]
    vid = next(x for x in candidates if x)
    store[vid] = vdc

    errs = validate_prior_vdc_refs(
        [{"vdc_id": vid, "claim": "invoice_ok", "required": True}],
        resolve_vdc=lambda i: store.get(i),
        resolve_deliverable=lambda _i: deliverable,
    )
    assert errs == [], errs


def test_prior_vdc_refs_reject_bad_deliverable():
    from fastapi.testclient import TestClient
    from novapanda.node import create_app
    from novapanda.sdk import NovaPandaClient

    client = Identity.generate()
    provider = Identity.generate()
    deliverable = {"invoice_no": "A-1", "total": "10.00", "currency": "USD"}
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    c = NovaPandaClient("http://testserver", client, http=tc)
    p = NovaPandaClient("http://testserver", provider, http=tc)
    ex = c.propose(
        provider=p.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 10, "currency": "USD"},
        idempotency_key="c8-prior-bad",
    )
    eid = ex["exchange_id"]
    c.contract(eid)
    p.contract(eid)
    c.escrow(eid, amount=10, currency="USD")
    p.deliver(eid, deliverable)
    c.verify(eid)
    settled = c.confirm(eid)
    vdc = settled["vdc"]
    vid = vdc.get("vdc_id") or eid
    errs = validate_prior_vdc_refs(
        [{"vdc_id": vid, "required": True}],
        resolve_vdc=lambda _i: vdc,
        resolve_deliverable=lambda _i: {"invoice_no": "TAMPERED", "total": "10.00", "currency": "USD"},
    )
    assert any("reverify failed" in e for e in errs)
