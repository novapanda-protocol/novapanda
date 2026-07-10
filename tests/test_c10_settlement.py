"""C10 — Settlement adapter idempotency / failure / mock rail (NP-SETTLE)."""

from __future__ import annotations

import pytest

from novapanda.settlement import MockSettlement, SettlementError


def test_c10_mock_settle_idempotent_and_rail():
    s = MockSettlement()
    h = s.escrow("ex-1", 10, "USD")
    r1 = s.settle(h)
    r2 = s.settle(h)
    assert r1["status"] == "settled"
    assert r2["status"] == "settled"
    assert r1["rail"] == "mock"
    assert r2["handle"] == h


def test_c10_mock_refund_idempotent():
    s = MockSettlement()
    h = s.escrow("ex-2", 5, "USD")
    assert s.refund(h)["status"] == "refunded"
    assert s.refund(h)["status"] == "refunded"
    assert s.refund(h)["rail"] == "mock"


def test_c10_conflict_settle_after_refund():
    s = MockSettlement()
    h = s.escrow("ex-3", 1, "USD")
    s.refund(h)
    with pytest.raises(SettlementError):
        s.settle(h)


def test_c10_negative_amount_rejected():
    s = MockSettlement()
    with pytest.raises(SettlementError):
        s.escrow("ex-4", -1, "USD")
