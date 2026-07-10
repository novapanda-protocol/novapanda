"""C-S1-SANDBOX — T13 honesty: sandbox rail Manifest + env gate (no partner HTTP)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from novapanda.config import NodeConfig
from novapanda.node import create_app
from novapanda.settlement import SandboxSettlement, assert_settlement_env_gate


def test_c_s1_sandbox_receipt_honesty():
    s = SandboxSettlement(partner="trial-partner")
    h = s.escrow("ex-s1", 7, "USD")
    receipt = s.settle(h)
    assert receipt["rail"] == "fiat-s1-sandbox"
    assert receipt["environment"] == "sandbox"
    assert receipt["licensed"] is False
    assert "production" not in (receipt.get("note") or "").lower() or "≠" in receipt["note"]
    rail = s.manifest_rail()
    assert rail["capabilities"] == ["authorize", "capture", "void"]
    assert rail["reconcile"]["format"] == ["csv", "json"]
    assert "api_base" not in rail  # secrets / partner URL stay out of public Manifest


def test_c_s1_manifest_via_node():
    app = create_app(seed=True, auth=False, settlement=SandboxSettlement(partner="p1"))
    tc = TestClient(app)
    rails = tc.get("/node/settlement/rails").json()
    entry = rails["rails"][0]
    assert entry["environment"] == "sandbox"
    assert entry["licensed"] is False
    assert entry.get("capabilities")
    assert "NP-SETTLE" in rails["profiles"]
    m = tc.get("/.well-known/novapanda.json").json()
    detail = m["settlement_detail"]["rails"][0]
    assert detail["environment"] == "sandbox"
    assert "api_base" not in detail or detail.get("api_base") is None


def test_c_s1_env_gate_blocks_non_mock_without_env(monkeypatch):
    monkeypatch.delenv("NOVAPANDA_SETTLEMENT_ENV", raising=False)
    monkeypatch.delenv("SETTLEMENT_ENV", raising=False)
    with pytest.raises(ValueError, match="non-mock"):
        assert_settlement_env_gate(settlement_name="x402", settlement_env=None)
    # sandbox / mock always ok
    assert_settlement_env_gate(settlement_name="sandbox", settlement_env=None)
    assert_settlement_env_gate(settlement_name="mock", settlement_env=None)
    # non-mock allowed with explicit env
    assert_settlement_env_gate(settlement_name="x402", settlement_env="sandbox")


def test_c_s1_config_make_settlement_sandbox(monkeypatch):
    monkeypatch.setenv("NOVAPANDA_SANDBOX_PARTNER", "cfg-partner")
    cfg = NodeConfig(settlement="sandbox")
    s = cfg.make_settlement()
    assert isinstance(s, SandboxSettlement)
    assert s.partner == "cfg-partner"