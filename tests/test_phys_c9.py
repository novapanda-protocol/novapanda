"""C9 — NP-PHYS physical / metered deliverable vectors."""

from __future__ import annotations

from novapanda.hashing import result_hash_of_json
from novapanda.v3.iso15118_sim import build_energy_deliverable, create_session
from novapanda.v3.physical import (
    physical_checks_report,
    validate_physical_deliverable,
)


GOOD_ENERGY = {
    "session_id": "sess-c9-1",
    "kwh_delivered": "10.500",
    "meter_signature": "meter-sig-demo",
}


def test_c9_01_missing_metered_field_fails_stable():
    bad = {"session_id": "s", "kwh_delivered": "1.0"}  # missing meter_signature
    r1 = physical_checks_report("energy.electric.dc", bad)
    r2 = physical_checks_report("energy.electric.dc", bad)
    assert r1["passed"] is False
    assert r1["errors"] == r2["errors"]
    assert any("meter_signature" in e for e in r1["errors"])


def test_c9_02_tamper_kwh_breaks_result_hash():
    original = dict(GOOD_ENERGY)
    h1 = result_hash_of_json(original)
    tampered = {**original, "kwh_delivered": "99.000"}
    h2 = result_hash_of_json(tampered)
    assert h1 != h2


def test_c9_03_non_physical_type_not_injured_by_phys_validator():
    # Schema-path resources return no phys errors
    errs = validate_physical_deliverable(
        "data.extraction.structured",
        {"invoice_no": "A-1"},
    )
    assert errs == []


def test_c9_04_iso15118_adapter_deliverable_validates():
    sess = create_session(evse_id="EVSE-C9")
    deliverable = build_energy_deliverable(sess["session_id"], kwh_delivered="3.200")
    errs = validate_physical_deliverable("energy.electric.dc", deliverable)
    assert errs == []


def test_c9_05_undeclared_type_rejected_when_manifest_gated():
    errs = validate_physical_deliverable(
        "energy.electric.dc",
        GOOD_ENERGY,
        allowed_types=["actuation.robot.task"],  # energy not listed
    )
    assert errs
    assert any("not in Manifest" in e for e in errs)
