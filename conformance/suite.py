"""NovaPanda Conformance Suite — C1–C7 一致性测试映射。"""

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
)


def list_cases() -> list[dict]:
    return [{"id": c.case_id, "title": c.title, "tests": list(c.tests)} for c in SUITE]


def run_case(
    case_id: str,
    *,
    pytest_run: Optional[Callable[..., int]] = None,
) -> int:
    runner = pytest_run or pytest.main
    case = next((c for c in SUITE if c.case_id == case_id.upper()), None)
    if case is None:
        raise ValueError(f"未知 conformance case: {case_id}")
    return runner(list(case.tests))


def run_all(*, pytest_run: Optional[Callable[..., int]] = None) -> int:
    runner = pytest_run or pytest.main
    paths: list[str] = []
    for case in SUITE:
        paths.extend(case.tests)
    return runner(paths)
