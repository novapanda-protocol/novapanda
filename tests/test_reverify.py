from novapanda import vdc as V
from novapanda.hashing import result_hash_of_json
from novapanda.identity import Identity
from novapanda.reverify import reverify


def _settled_vdc(deliverable):
    client, provider = Identity.generate(), Identity.generate()
    doc = V.build_vdc(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        result_hash=result_hash_of_json(deliverable), rule_id="R1",
        evidence_level="dual_signed", started_at="2026-06-28T00:00:00Z",
        finished_at="2026-06-28T00:00:01Z", idempotency_key="k", state="DELIVERED",
    )
    V.provider_sign(doc, provider)
    V.client_sign(doc, client)
    doc["state"] = "SETTLED"
    return doc


def test_reverify_all_pass():
    deliverable = {"invoice_no": "A-1"}
    doc = _settled_vdc(deliverable)
    checks = reverify(doc, deliverable)
    assert checks == {
        "provider_sig_valid": True,
        "client_sig_valid": True,
        "settled_valid": True,
        "result_hash_matches": True,
    }


def test_reverify_detects_deliverable_tamper():
    deliverable = {"invoice_no": "A-1"}
    doc = _settled_vdc(deliverable)
    checks = reverify(doc, {"invoice_no": "TAMPERED"})
    assert checks["result_hash_matches"] is False


def test_reverify_replay_matches_node():
    from novapanda.registry import load_default_registries

    deliverable = {"invoice_no": "A-001", "total": "100.00", "currency": "USD"}
    doc = _settled_vdc(deliverable)
    _, rules = load_default_registries()
    rule = rules.get("R-extract-invoice-v1")
    verify_result = {
        "passed": True,
        "replay_inputs_ref": {
            "kind": "inline",
            "rule_id": "R-extract-invoice-v1",
            "schema_inline": rule["schema"],
        },
    }
    checks = reverify(doc, deliverable, verify_result)
    assert checks["replay"]["replay_passed"] is True
    assert checks["replay"]["matches_node"] is True


def test_reverify_detects_signature_tamper():
    deliverable = {"invoice_no": "A-1"}
    doc = _settled_vdc(deliverable)
    doc["quantity"] = 999
    checks = reverify(doc, deliverable)
    assert checks["provider_sig_valid"] is False
    assert checks["settled_valid"] is False
