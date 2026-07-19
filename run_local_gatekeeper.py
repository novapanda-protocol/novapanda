#!/usr/bin/env python3
"""NovaPanda 本地看门狗（CI-ready · 不公开发布）。

一键校验今晚封档边界：
1. ``state_machine.TRANSITIONS`` 指纹未改（ADR-0002 / 解耦铁律）
2. 敏感路径仍被 gitignore 隔离
3. 关键套件：verification_gateway · agent_skill · depin_embodied_e2e
   （及同夜影子套件，合计约 45 项）

用法::

    python run_local_gatekeeper.py
    # 或
    bash run_local_gatekeeper.sh
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FINGERPRINT_FILE = ROOT / "internal" / "ops" / "TRANSITIONS_FINGERPRINT.txt"

GATE_TESTS = [
    "tests/test_verification_gateway.py",
    "tests/test_agent_skill.py",
    "tests/test_depin_embodied_e2e.py",
    # 同夜影子边界（凑齐 ~45；破坏解耦会在此暴露）
    "tests/test_e2e_agent_workflow.py",
    "tests/test_autonomy_dispatch.py",
    "tests/test_production_hardening.py",
    "tests/test_marketplace_score_match.py",
    # Adopter Runtime 闭环（M1–M6 · 填中空 / Bundle / Skill）
    "tests/test_adopter_runtime.py",
    "tests/test_adopter_av_charge.py",
    "tests/test_adopter_m3_product.py",
    "tests/test_adopter_m4_rails.py",
    "tests/test_adopter_site_patrol.py",
    "tests/test_adopter_skill.py",
    "tests/test_manifest_validate_cli.py",
    "tests/test_schema_v02_drafts.py",
    "tests/test_openclaw_pair.py",
    "tests/test_ecosystem_adapters.py",
]

REQUIRED_GITIGNORE_SNIPPETS = [
    ".env",
    "internal/",
    "deploy/env/production.env",
    "STRIPE_LIVE",
    "SIGNER_BROADCAST",
]


def transitions_fingerprint() -> str:
    sys.path.insert(0, str(ROOT))
    from novapanda import state_machine as sm

    edges: list[str] = []
    for src, dsts in sorted(sm.TRANSITIONS.items()):
        for dst in sorted(dsts):
            edges.append(f"{src}->{dst}")
    return hashlib.sha256("\n".join(edges).encode("utf-8")).hexdigest()[:16]


def check_transitions() -> None:
    live = transitions_fingerprint()
    FINGERPRINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not FINGERPRINT_FILE.is_file():
        FINGERPRINT_FILE.write_text(
            live + "\n# frozen 2026-07-18 shadow archive — do not edit without ADR\n",
            encoding="utf-8",
        )
        print(f"[gate] froze TRANSITIONS fingerprint → {FINGERPRINT_FILE.name} = {live}")
    expected = FINGERPRINT_FILE.read_text(encoding="utf-8").strip().split()[0]
    if live != expected:
        raise SystemExit(
            "FAIL: state_machine.TRANSITIONS fingerprint changed\n"
            f"  expected={expected}\n  got={live}\n"
            "  ADR-0002: do not rewrite TRANSITIONS without review."
        )
    print(f"[gate] TRANSITIONS fingerprint OK ({live})")


def check_gitignore() -> None:
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_GITIGNORE_SNIPPETS if s not in gi]
    if missing:
        raise SystemExit(f"FAIL: .gitignore missing isolation rules: {missing}")
    danger = [
        ROOT / ".env",
        ROOT / "deploy" / "env" / "production.env",
    ]
    for p in danger:
        if p.is_file():
            r = subprocess.run(
                ["git", "check-ignore", "-q", str(p.relative_to(ROOT))],
                cwd=ROOT,
            )
            if r.returncode != 0:
                raise SystemExit(f"FAIL: sensitive file not gitignored: {p}")
    print("[gate] .gitignore secret isolation OK")


def run_pytest() -> None:
    cmd = [sys.executable, "-m", "pytest", *GATE_TESTS, "-q", "--tb=line"]
    print("[gate] running:", " ".join(GATE_TESTS))
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        raise SystemExit(r.returncode)
    print("[gate] pytest OK")


def main() -> int:
    print("=== NovaPanda local gatekeeper ===")
    check_gitignore()
    check_transitions()
    run_pytest()
    print("=== GATE PASS — archive boundary intact ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
