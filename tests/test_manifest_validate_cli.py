"""manifest validate CLI + NP-LITE Outbox 对齐。"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from novapanda.adopter import AdopterRuntime
from novapanda.cli import main as cli_main
from novapanda.identity import Identity
from novapanda.manifest import build_agent_manifest, verify_agent_manifest
from novapanda.manifest_validate import (
    check_lite_outbox_alignment,
    validate_agent_manifest,
)
from novapanda.node import create_app
from novapanda.sdk import NovaPandaClient


def test_validate_signed_manifest_ok():
    ident = Identity.generate()
    m = build_agent_manifest(
        ident,
        capabilities=[{
            "resource_type": "energy.electric.dc",
            "rules": ["R-energy-dc-meter-v1"],
            "price": {"amount": 1, "currency": "USD"},
        }],
        exchange_endpoint="http://x/exchanges",
        profiles=["NP-MIN", "NP-PHYS", "NP-LITE"],
        lite={"tier": "edge", "canonical": "novapanda-c1", "offline_queue": True},
    )
    assert verify_agent_manifest(m)
    report = validate_agent_manifest(m, require_profiles=True)
    assert report["ok"] is True
    assert report["checks"]["signature_valid"] is True


def test_validate_bad_sig_fails():
    ident = Identity.generate()
    m = build_agent_manifest(
        ident,
        capabilities=[{"resource_type": "service.task.generic", "rules": ["R-task-status-v1"]}],
        exchange_endpoint="http://x/exchanges",
        profiles=["NP-MIN"],
    )
    m["sig"] = "AAAA"
    report = validate_agent_manifest(m)
    assert report["ok"] is False
    assert any("signature" in e for e in report["errors"])


def test_lite_without_canonical_errors():
    ident = Identity.generate()
    m = build_agent_manifest(
        ident,
        capabilities=[{"resource_type": "x", "rules": ["r"]}],
        exchange_endpoint="http://x/exchanges",
        profiles=["NP-MIN", "NP-LITE"],
        lite={"tier": "edge", "canonical": "private-dialect", "offline_queue": True},
    )
    report = validate_agent_manifest(m)
    assert report["ok"] is False
    assert any("canonical" in e for e in report["errors"])


def test_cli_manifest_validate(tmp_path: Path):
    ident = Identity.generate()
    m = build_agent_manifest(
        ident,
        capabilities=[{"resource_type": "data.extraction.structured", "rules": ["R-extract-invoice-v1"]}],
        exchange_endpoint="http://x/exchanges",
        profiles=["NP-MIN"],
    )
    path = tmp_path / "m.json"
    path.write_text(json.dumps(m), encoding="utf-8")
    assert cli_main(["manifest", "validate", str(path)]) == 0
    m["sig"] = "dead"
    path.write_text(json.dumps(m), encoding="utf-8")
    assert cli_main(["manifest", "validate", str(path)]) == 1


def test_adopter_lite_alignment(tmp_path: Path):
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    rt = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        tmp_path / "a",
    )
    manifest = rt.build_manifest(
        capabilities=[{
            "resource_type": "energy.electric.dc",
            "rules": ["R-energy-dc-meter-v1"],
            "price": {"amount": 1050, "currency": "USD"},
        }],
        declare_lite=True,
        profiles=["NP-MIN", "NP-PHYS"],
    )
    assert "NP-LITE" in manifest["profiles"]
    assert manifest["lite"]["offline_queue"] is True
    assert validate_agent_manifest(manifest)["ok"] is True

    align = rt.check_lite_alignment(profiles=manifest["profiles"])
    assert align["ok"] is True
    assert align["applicable"] is True

    # 负例：假装 flush 不拦截
    bad = check_lite_outbox_alignment(
        profiles=["NP-LITE"],
        offline_queue_implemented=True,
        flush_blocked_when_offline=False,
    )
    assert bad["ok"] is False
