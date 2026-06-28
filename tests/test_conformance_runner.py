from conformance.suite import SUITE, list_cases, run_case


def test_suite_lists_c1_through_c7():
    ids = [c.case_id for c in SUITE]
    assert ids == ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]


def test_list_cases_shape():
    items = list_cases()
    assert len(items) == 7
    assert all("tests" in item for item in items)


def test_run_case_invokes_pytest(monkeypatch):
    called = {}

    def fake_pytest(args):
        called["args"] = args
        return 0

    assert run_case("C2", pytest_run=fake_pytest) == 0
    assert "test_produced_vdc_conforms_to_schema" in called["args"][0]
