"""Generate conformance report for compatibility / UC-40 self-attestation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from conformance.gap_audit import audit
from conformance.suite import SUITE, list_cases


def _reference_registration_draft() -> dict[str, Any]:
    """Copy-paste starter for docs/compatibility.md PRs (reference node)."""
    wired = sorted({c.case_id for c in SUITE})
    vectors = [c for c in wired if c != "C-MCP"] + (["C-MCP"] if "C-MCP" in wired else [])
    return {
        "implementation": "novapanda (reference)",
        "language": "Python",
        "maintainer": "青合 / 社区",
        "profiles_declared": [
            "NP-MIN",
            "NP-NODE",
            "NP-BUNDLE",
            "NP-SETTLE",
            "NP-PHYS",
            "NP-DELEGATE",
            "NP-PRIV",
            "NP-LITE",
            "NP-CLAIM-XFER (optional env)",
        ],
        "vectors": vectors,
        "level_self_report": "L2+",
        "mock_or_sandbox_note": "settlement mock/sandbox; Stripe sandbox tested; CLAIM production requires env",
        "plugfest_log_url": "(fill: CI or local `conformance report --run` log)",
        "node_url": "(fill: https://node.example/.well-known/novapanda.json)",
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }


def build_report(*, run_all: bool = False, pytest_run=None) -> dict[str, Any]:
    gap = audit()
    report: dict[str, Any] = {
        "report_version": "0.3",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gap_audit": gap,
        "cases": list_cases(),
        "case_count": len(SUITE),
        "registration_draft": _reference_registration_draft(),
        "registration": {
            "compatibility_matrix": "docs/compatibility.md",
            "plugfest_guide": "conformance/EXTERNAL_PLUGFEST.md",
            "uc40_design": "internal/design/UC-40-认证流程设计.md",
            "pr_checklist": "docs/compatibility.md §2.1",
            "suggested_pr_fields": [
                "implementation",
                "language",
                "maintainer",
                "profiles_declared",
                "vectors",
                "level_self_report",
                "mock_or_sandbox_note",
                "plugfest_log_url",
                "node_url",
                "updated",
            ],
        },
        "next_steps": [
            "Run full suite: python -m novapanda conformance report --run",
            "Optional: python demo/plugfest.py",
            "PR one row to docs/compatibility.md",
        ],
    }
    if run_all:
        from conformance.suite import run_all as run_all_cases

        rc = run_all_cases(pytest_run=pytest_run)
        report["run_all"] = {"exit_code": rc, "passed": rc == 0}
    return report
