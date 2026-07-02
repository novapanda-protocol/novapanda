from novapanda.verifier import SchemaVerifier

_SCHEMA = {
    "type": "object",
    "required": ["invoice_no", "total"],
    "properties": {
        "invoice_no": {"type": "string"},
        "total": {"type": "string"},
    },
    "additionalProperties": False,
}
_RULE = {"rule_id": "R-extract-schema-v1", "schema": _SCHEMA}


def test_schema_verifier_passes_valid():
    v = SchemaVerifier()
    r = v.verify({"invoice_no": "A-001", "total": "100.00"}, _RULE)
    assert r["passed"] is True
    assert r["checks"] == []


def test_schema_verifier_fails_missing_field():
    v = SchemaVerifier()
    r = v.verify({"invoice_no": "A-001"}, _RULE)
    assert r["passed"] is False
    assert len(r["checks"]) >= 1


def test_schema_verifier_deterministic_decision():
    v = SchemaVerifier()
    bad = {"invoice_no": 1, "extra": True}
    r1 = v.verify(bad, _RULE)
    r2 = v.verify(bad, _RULE)
    assert r1["passed"] == r2["passed"] is False
    assert r1["checks"] == r2["checks"]


def test_schema_verifier_missing_rule():
    v = SchemaVerifier()
    r = v.verify({"x": 1}, None)
    assert r["passed"] is False


def test_schema_verifier_energy_physical_only():
    v = SchemaVerifier()
    rule = {"rule_id": "R-energy-dc-meter-v1", "resource_type": "energy.electric.dc"}
    good = {
        "session_id": "s1",
        "kwh_delivered": "1.0",
        "meter_signature": "sig",
    }
    r = v.verify(good, rule)
    assert r["passed"] is True
    bad = v.verify({"session_id": "s1"}, rule)
    assert bad["passed"] is False
