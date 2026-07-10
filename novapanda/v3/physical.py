"""物理资源适配 v3（energy.* / actuation.*）· NP-PHYS。"""

from __future__ import annotations

from typing import Any, Iterable, Optional

PHYSICAL_VERSION = "0.3"

RESERVED_TYPES = frozenset({
    "energy.electric.dc",
    "actuation.robot.task",
})

_DELIVERABLE_CHECKS: dict[str, tuple[str, ...]] = {
    "energy.electric.dc": ("session_id", "kwh_delivered", "meter_signature"),
    "actuation.robot.task": ("task_id", "completion_proof", "duration_secs"),
}

# Metered fields that MUST enter result_hash coverage when present.
METERED_FIELDS = ("kwh_delivered", "duration_secs", "window_start", "window_end")


def is_reserved_physical_type(resource_type: str) -> bool:
    return resource_type in RESERVED_TYPES


def declared_physical_types(manifest_types: Optional[Iterable[str]] = None) -> frozenset[str]:
    """Types the implementation advertises (defaults to reserved ontology)."""
    if manifest_types is None:
        return RESERVED_TYPES
    return frozenset(manifest_types)


def validate_physical_deliverable(
    resource_type: str,
    deliverable: Any,
    *,
    allowed_types: Optional[Iterable[str]] = None,
) -> list[str]:
    """校验物理类 deliverable；失败时可复现（稳定排序的 checks）。"""
    errors: list[str] = []
    allowed = declared_physical_types(allowed_types)

    if resource_type not in RESERVED_TYPES:
        # 非物理预留类型：不走物理器（由 Schema 路径处理）
        return []

    if resource_type not in allowed:
        errors.append(f"physical type not in Manifest: {resource_type}")
        return sorted(errors)

    if not isinstance(deliverable, dict):
        return ["deliverable 必须为 object"]

    for field in _DELIVERABLE_CHECKS[resource_type]:
        if field not in deliverable:
            errors.append(f"缺少字段: {field}")

    if resource_type == "energy.electric.dc":
        kwh = deliverable.get("kwh_delivered")
        if kwh is not None and not isinstance(kwh, (int, str)):
            errors.append("kwh_delivered 须为整数或字符串")
        from .iso15118_sim import validate_sim_deliverable

        errors.extend(validate_sim_deliverable(deliverable))

    return sorted(errors)


def physical_checks_report(resource_type: str, deliverable: Any, **kwargs) -> dict:
    errs = validate_physical_deliverable(resource_type, deliverable, **kwargs)
    return {
        "passed": not errs,
        "checks": [{"field_or_rule": e, "ok": False} for e in errs],
        "errors": errs,
    }


def iso15118_session_stub(session_id: str) -> dict:
    """兼容旧 stub：委托 iso15118_sim。"""
    from .iso15118_sim import get_session

    sess = get_session(session_id)
    if sess is None:
        return {
            "adapter": "iso15118-stub/v0",
            "session_id": session_id,
            "status": "unknown",
            "note": "Use POST /v3/iso15118/sessions to create sim session",
        }
    return {
        "adapter": sess.get("sim_version", "iso15118-sim/v1"),
        "session_id": session_id,
        "status": sess.get("status"),
        "kwh_delivered": sess.get("kwh_delivered"),
    }
