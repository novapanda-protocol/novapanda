"""NovaPanda Conformance Suite — C1–C12 + NODE-R / LITE / PRIV / S1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import pytest


@dataclass(frozen=True)
class ConformanceCase:
    case_id: str
    title: str
    tests: tuple[str, ...]


SUITE: tuple[ConformanceCase, ...] = (
    ConformanceCase(
        "C1",
        "规范化/签名",
        (
            "tests/test_canonical.py",
            "tests/test_cbor.py",
            "tests/test_vdc_cbor.py",
            "tests/test_vdc_dual_encoding.py",
        ),
    ),
    ConformanceCase(
        "C2",
        "VDC 结构",
        ("tests/test_conformance.py::test_produced_vdc_conforms_to_schema",),
    ),
    ConformanceCase(
        "C3",
        "状态机",
        (
            "tests/test_state_machine.py",
            "tests/test_timeout.py",
            "tests/test_confirm_timeout.py",
        ),
    ),
    ConformanceCase(
        "C4",
        "幂等/重放",
        (
            "tests/test_replay_ref.py",
            "tests/test_hardening.py",
            "tests/test_auth.py",
        ),
    ),
    ConformanceCase(
        "C5",
        "验收确定性",
        (
            "tests/test_verifier.py",
            "tests/test_llm_verifier.py",
            "tests/test_llm_judge_registry.py",
        ),
    ),
    ConformanceCase(
        "C6",
        "信誉链",
        (
            "tests/test_reputation.py",
            "tests/test_reputation_agg.py",
            "tests/test_reputation_score.py",
        ),
    ),
    ConformanceCase(
        "C7",
        "Manifest/发现",
        ("tests/test_manifest.py",),
    ),
    ConformanceCase(
        "C8",
        "Bundle/prior_vdc_refs",
        ("tests/test_bundle.py",),
    ),
    ConformanceCase(
        "C9",
        "物理/计量证据",
        ("tests/test_phys_c9.py",),
    ),
    ConformanceCase(
        "C10",
        "Settlement 适配幂等/失败/mock rail · 多轨注册表",
        ("tests/test_c10_settlement.py", "tests/test_c10_multi_rail.py"),
    ),
    ConformanceCase(
        "C11",
        "Claim 无锚 / 双花拒绝",
        ("tests/test_c11_claim.py",),
    ),
    ConformanceCase(
        "C12",
        "DELEGATE 过期/限价/轨白名单/撤销/额度",
        ("tests/test_c12_delegate.py",),
    ),
    ConformanceCase(
        "C-NODE-R",
        "recover / pending settlement intent",
        ("tests/test_c_node_r.py",),
    ),
    ConformanceCase(
        "C-LITE-RT",
        "LITE 瘦报文 ↔ C1 round-trip",
        ("tests/test_c_lite_rt.py",),
    ),
    ConformanceCase(
        "C-PRIV",
        "PRIV hash_only / 无 Operator PII",
        ("tests/test_c_priv.py",),
    ),
    ConformanceCase(
        "C-S1-SANDBOX",
        "S1 沙箱轨诚实 Manifest / env gate",
        ("tests/test_c_s1_sandbox.py",),
    ),
    ConformanceCase(
        "C-MCP",
        "MCP 绑定 ≡ SDK（informative → v0.2 suite）",
        ("tests/test_c_mcp.py",),
    ),
)


def list_cases() -> list[dict]:
    return [{"id": c.case_id, "title": c.title, "tests": list(c.tests)} for c in SUITE]


def run_case(
    case_id: str,
    *,
    pytest_run: Optional[Callable[..., int]] = None,
) -> int:
    runner = pytest_run or pytest.main
    wanted = case_id.upper()
    case = next((c for c in SUITE if c.case_id.upper() == wanted), None)
    if case is None:
        raise ValueError(f"未知 conformance case: {case_id}")
    return runner(list(case.tests))


def run_all(*, pytest_run: Optional[Callable[..., int]] = None) -> int:
    runner = pytest_run or pytest.main
    paths: list[str] = []
    for case in SUITE:
        paths.extend(case.tests)
    return runner(paths)
