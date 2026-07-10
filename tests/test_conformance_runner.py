from conformance.suite import SUITE, list_cases, run_case

_CORE_IDS = tuple(f"C{i}" for i in range(1, 9))
_EXTENDED_IDS = (
    "C9",
    "C10",
    "C11",
    "C12",
    "C-NODE-R",
    "C-LITE-RT",
    "C-PRIV",
    "C-S1-SANDBOX",
    "C-MCP",
)


def test_suite_lists_c1_through_c8():
    ids = [c.case_id for c in SUITE]
    assert ids[:8] == list(_CORE_IDS)
    for case_id in _EXTENDED_IDS:
        assert case_id in ids


def test_list_cases_shape():
    items = list_cases()
    assert len(items) == len(SUITE)
    assert [item["id"] for item in items] == [c.case_id for c in SUITE]
    assert all("tests" in item and item["tests"] for item in items)


def test_run_case_invokes_pytest(monkeypatch):
    called = {}

    def fake_pytest(args):
        called["args"] = args
        return 0

    assert run_case("C2", pytest_run=fake_pytest) == 0
    assert "test_produced_vdc_conforms_to_schema" in called["args"][0]
