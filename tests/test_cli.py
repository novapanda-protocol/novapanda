"""CLI rails / quote / negotiate."""

from __future__ import annotations

import json
import os

from novapanda.cli import main


def test_cli_rails_multi_rail(monkeypatch):
    monkeypatch.setenv("NOVAPANDA_RAILS", "mock,x402")
    monkeypatch.setenv("NOVAPANDA_DEFAULT_RAIL", "mock")
    rc = main(["rails"])
    assert rc == 0


def test_cli_quote_micro_usdc(monkeypatch, capsys):
    monkeypatch.setenv("NOVAPANDA_RAILS", "mock,x402,sandbox")
    rc = main(["quote", "-a", "50", "-c", "USDC"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["recommended_rail"] == "x402"
    assert out["amount_class"] == "micro"


def test_cli_negotiate_preview(monkeypatch, capsys):
    monkeypatch.setenv("NOVAPANDA_RAILS", "mock,x402")
    rc = main(["negotiate", "-a", "50", "-c", "USDC", "--preferred", "x402"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["binding_preview"]["rail"] == "x402"


def test_cli_conformance_list(capsys):
    rc = main(["conformance", "list"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    ids = {c["id"] for c in data["cases"]}
    assert "C10" in ids


def test_cli_conformance_report(capsys):
    rc = main(["conformance", "report"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["report_version"] == "0.3"
    assert data["gap_audit"]["ok"] is True
    assert any(c["id"] == "C-MCP" for c in data["cases"])
    assert "registration_draft" in data
    assert data["registration_draft"]["implementation"].startswith("novapanda")
    assert "registration" in data


def test_cli_ecosystem_list(capsys):
    rc = main(["ecosystem", "list"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    slugs = {a["slug"] for a in data["adapters"]}
    assert {"openclaw", "mqtt_iot", "ros2"} <= slugs
    assert data["count"] >= 3
