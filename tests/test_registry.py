from troodon.registry import (
    DEFAULT_ONTOLOGY_PATH,
    DEFAULT_RULES_PATH,
    load_default_registries,
)


def test_default_ontology_loads():
    onto, _ = load_default_registries()
    types = {t["type_id"] for t in onto.list()}
    assert "data.extraction.structured" in types
    assert "energy.electric.dc" in types
    assert "actuation.robot.task" in types
    energy = onto.get("energy.electric.dc")
    assert energy.get("reserved") is True


def test_default_rules_load_invoice_schema():
    _, rules = load_default_registries()
    r = rules.get("R-extract-invoice-v1")
    assert r is not None
    assert r["resource_type"] == "data.extraction.structured"
    assert "schema" in r
    assert rules.get("R-extract-schema-v1") is not None
    assert rules.get("R-energy-dc-meter-v1") is not None
    assert rules.get("R-actuation-task-v1") is not None
    assert rules.get("R-task-status-v1") is not None


def test_paths_exist():
    assert DEFAULT_ONTOLOGY_PATH.is_file()
    assert DEFAULT_RULES_PATH.is_file()
