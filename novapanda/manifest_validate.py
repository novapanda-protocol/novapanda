"""Agent Manifest 校验（``np manifest validate``）。

签名验真 + Profile 诚实提示 + NP-LITE / NP-PHYS 宣告对齐。
不上传私钥；纯本地检查。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional

from .manifest import verify_agent_manifest
from .node.profile_gate import check_profile_honesty

KNOWN_PROFILES = frozenset({
    "NP-MIN",
    "NP-NODE",
    "NP-BUNDLE",
    "NP-PHYS",
    "NP-SETTLE",
    "NP-DELEGATE",
    "NP-PRIV",
    "NP-LITE",
    "NP-REP",
    "NP-CLAIM-XFER",
})

PHYS_RESOURCE_PREFIXES = ("energy.", "actuation.")


def validate_agent_manifest(
    manifest: dict[str, Any],
    *,
    claim_mock_only: bool = True,
    delegation_supported: bool = True,
    require_profiles: bool = False,
) -> dict[str, Any]:
    """返回结构化报告：``ok`` / ``errors`` / ``warnings`` / ``checks``。"""
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}

    if not isinstance(manifest, dict):
        return {
            "ok": False,
            "errors": ["manifest must be an object"],
            "warnings": [],
            "checks": {},
        }

    for key in ("protocol", "agent_id", "pubkey", "capabilities", "endpoints", "sig"):
        if key not in manifest:
            errors.append(f"missing field: {key}")
    checks["required_fields"] = not any(e.startswith("missing field") for e in errors)

    if manifest.get("protocol") not in (None, "novapanda"):
        warnings.append(f"unexpected protocol: {manifest.get('protocol')}")

    sig_ok = False
    if "sig" in manifest and "agent_id" in manifest:
        try:
            sig_ok = bool(verify_agent_manifest(manifest))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"signature verify raised: {exc}")
            sig_ok = False
        if not sig_ok:
            errors.append("signature invalid or agent_id/did mismatch")
    checks["signature_valid"] = sig_ok

    caps = manifest.get("capabilities")
    if caps is not None and not isinstance(caps, list):
        errors.append("capabilities must be a list")
        caps = []
    elif caps is None:
        caps = []
        errors.append("missing field: capabilities")
    checks["capabilities_count"] = len(caps)

    endpoints = manifest.get("endpoints") or {}
    if not isinstance(endpoints, dict):
        errors.append("endpoints must be an object")
    elif not endpoints.get("exchange"):
        warnings.append("endpoints.exchange missing (discovery harder)")

    profiles = manifest.get("profiles")
    if profiles is None:
        if require_profiles:
            errors.append("profiles missing (require_profiles=true)")
        else:
            warnings.append("profiles omitted; recommend declaring at least NP-MIN")
        profiles = []
    elif not isinstance(profiles, list) or not all(isinstance(p, str) for p in profiles):
        errors.append("profiles must be a list of strings")
        profiles = []
    checks["profiles"] = list(profiles)

    unknown = [p for p in profiles if p not in KNOWN_PROFILES]
    if unknown:
        warnings.append(f"unknown profiles (not in registry): {unknown}")

    honesty = check_profile_honesty(
        profiles,
        claim_mock_only=claim_mock_only,
        delegation_supported=delegation_supported,
    )
    errors.extend(honesty)
    checks["profile_honesty"] = not honesty

    # NP-LITE 对齐
    lite = manifest.get("lite")
    if "NP-LITE" in profiles:
        if not isinstance(lite, dict):
            errors.append("NP-LITE declared but lite{} block missing")
        else:
            if lite.get("canonical") not in (None, "novapanda-c1"):
                errors.append(
                    "NP-LITE lite.canonical must be 'novapanda-c1' (no private dialect)"
                )
            if lite.get("offline_queue") is not True:
                warnings.append(
                    "NP-LITE without lite.offline_queue=true; "
                    "Outbox/store-and-forward SHOULD be declared (LITE-03)"
                )
            tier = lite.get("tier")
            if tier not in (None, "lite", "edge", "full"):
                warnings.append(f"lite.tier unusual: {tier}")
        checks["lite_block"] = isinstance(lite, dict)
    elif isinstance(lite, dict):
        warnings.append("lite{} present but NP-LITE not in profiles")

    # NP-PHYS：能力里应有物理资源类型
    if "NP-PHYS" in profiles:
        types = [
            str(c.get("resource_type") or "")
            for c in caps
            if isinstance(c, dict)
        ]
        if not any(t.startswith(PHYS_RESOURCE_PREFIXES) for t in types):
            warnings.append(
                "NP-PHYS declared but no energy.*/actuation.* in capabilities"
            )
        checks["phys_capabilities"] = any(
            t.startswith(PHYS_RESOURCE_PREFIXES) for t in types
        )

    if "NP-MIN" not in profiles and profiles:
        warnings.append("profiles present without NP-MIN; MIN is usually the base")

    ok = not errors
    return {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "agent_id": manifest.get("agent_id"),
        "profiles": list(profiles),
    }


def validate_manifest_file(
    path: Path | str,
    **kwargs: Any,
) -> dict[str, Any]:
    import json

    p = Path(path)
    doc = json.loads(p.read_text(encoding="utf-8"))
    report = validate_agent_manifest(doc, **kwargs)
    report["path"] = str(p)
    return report


def check_lite_outbox_alignment(
    *,
    profiles: Iterable[str],
    offline_queue_implemented: bool,
    flush_blocked_when_offline: bool,
) -> dict[str, Any]:
    """NP-LITE-03 检查单：离线队列与 flush 纪律。"""
    prof = set(profiles)
    errors: list[str] = []
    warnings: list[str] = []
    if "NP-LITE" not in prof:
        return {
            "ok": True,
            "applicable": False,
            "errors": [],
            "warnings": ["NP-LITE not declared; skip outbox alignment"],
        }
    if not offline_queue_implemented:
        errors.append("NP-LITE requires offline queue (Adopter Outbox or equivalent)")
    if not flush_blocked_when_offline:
        errors.append(
            "NP-LITE-03: flush/replay MUST refuse while offline "
            "(no pseudo-SETTLED)"
        )
    return {
        "ok": not errors,
        "applicable": True,
        "errors": errors,
        "warnings": warnings,
    }
