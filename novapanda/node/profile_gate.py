"""Manifest profile honesty gate (T03a / A6)."""

from __future__ import annotations

from typing import Iterable

NP_CLAIM_XFER = "NP-CLAIM-XFER"
MOCK_ONLY_PROFILES = {NP_CLAIM_XFER}


def check_profile_honesty(
    profiles: Iterable[str],
    *,
    claim_mock_only: bool = True,
    delegation_supported: bool = True,
) -> list[str]:
    """Return human-readable violations; empty => OK."""
    prof = set(profiles)
    errors: list[str] = []
    if NP_CLAIM_XFER in prof and claim_mock_only:
        errors.append(
            "profiles 含 NP-CLAIM-XFER 但节点仅提供 Claim mock；"
            "请移除宣告或实现生产登记（见 T03a）"
        )
    if "NP-DELEGATE" in prof and not delegation_supported:
        errors.append("profiles 含 NP-DELEGATE 但 delegation 未启用")
    return errors


def assert_profiles_or_raise(profiles: Iterable[str], **kwargs) -> None:
    errs = check_profile_honesty(profiles, **kwargs)
    if errs:
        raise ValueError("; ".join(errs))
