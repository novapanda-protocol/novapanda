"""MCP binding read-only surface."""

from __future__ import annotations

from fastapi.testclient import TestClient

from novapanda.bindings.mcp_tools import dispatch_readonly, list_tools
from novapanda.node import create_app_from_config


def test_mcp_tool_catalog_not_empty():
    names = {t["name"] for t in list_tools()}
    assert "np_manifest" in names
    assert "np_settlement_rails" in names


def test_mcp_forbidden_tools():
    import pytest

    with pytest.raises(ValueError, match="forbidden"):
        dispatch_readonly("np_force_settled", base_url="http://x")


def test_mcp_dispatch_manifest(monkeypatch):
    monkeypatch.setenv("NOVAPANDA_AUTH", "0")
    monkeypatch.setenv("NOVAPANDA_RAILS", "mock")
    app = create_app_from_config()
    tc = TestClient(app)
    data = dispatch_readonly("np_manifest", base_url="http://testserver", http=tc)
    assert data.get("protocol") == "novapanda"


def test_mcp_dispatch_quote(monkeypatch):
    monkeypatch.setenv("NOVAPANDA_AUTH", "0")
    monkeypatch.setenv("NOVAPANDA_RAILS", "mock,x402")
    app = create_app_from_config()
    tc = TestClient(app)
    data = dispatch_readonly(
        "np_settlement_quote",
        base_url="http://testserver",
        http=tc,
        params={"amount": 25, "currency": "USDC"},
    )
    assert data["recommended_rail"] == "x402"
