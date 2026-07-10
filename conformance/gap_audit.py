"""T15 — audit conformance suite vs expected case registry."""

from __future__ import annotations

from .suite import SUITE

EXPECTED_CASES = frozenset({
    "C1",
    "C2",
    "C3",
    "C4",
    "C5",
    "C6",
    "C7",
    "C8",
    "C9",
    "C10",
    "C11",
    "C12",
    "C-NODE-R",
    "C-LITE-RT",
    "C-PRIV",
    "C-S1-SANDBOX",
})

RESERVED_ONLY = frozenset({"C-MCP"})  # informative; wired in suite, not L1 hard gate


def audit() -> dict:
    wired = {c.case_id for c in SUITE}
    missing = sorted(EXPECTED_CASES - wired)
    extra = sorted(wired - EXPECTED_CASES - RESERVED_ONLY)
    return {
        "wired": sorted(wired),
        "expected": sorted(EXPECTED_CASES),
        "reserved_only": sorted(RESERVED_ONLY),
        "missing": missing,
        "extra": extra,
        "ok": not missing,
    }


def main() -> int:
    report = audit()
    print("NovaPanda conformance gap audit (T15)")
    print(f"  wired:   {', '.join(report['wired'])}")
    print(f"  missing: {', '.join(report['missing']) or '—'}")
    print(f"  extra:   {', '.join(report['extra']) or '—'}")
    print(f"  reserved (not required in suite): {', '.join(report['reserved_only']) or '—'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
