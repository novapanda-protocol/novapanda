"""Exchange Bundle helpers (Profile NP-BUNDLE) — client-side composition.

节点默认可忽略 depends_on；本模块供编排方与一致性向量使用。
"""

from __future__ import annotations

from typing import Any

from .reverify import reverify


BUNDLE_REQUIRED_FIELDS = (
    "bundle_version",
    "goal_id",
    "correlation_id",
    "exchange_ids",
    "success_rule",
)


def validate_bundle(doc: dict[str, Any]) -> list[str]:
    """返回错误列表；空列表表示最小字段合法。"""
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["bundle must be an object"]
    for key in BUNDLE_REQUIRED_FIELDS:
        if key not in doc:
            errors.append(f"missing field: {key}")
    ids = doc.get("exchange_ids")
    if ids is not None and not isinstance(ids, list):
        errors.append("exchange_ids must be a list")
    elif isinstance(ids, list) and not all(isinstance(x, str) and x for x in ids):
        errors.append("exchange_ids entries must be non-empty strings")
    depends = doc.get("depends_on")
    if depends is not None:
        if not isinstance(depends, dict):
            errors.append("depends_on must be an object")
        elif isinstance(ids, list):
            id_set = set(ids)
            for child, parents in depends.items():
                if child not in id_set:
                    errors.append(f"depends_on key not in exchange_ids: {child}")
                if not isinstance(parents, list):
                    errors.append(f"depends_on[{child}] must be a list")
                else:
                    for p in parents:
                        if p not in id_set:
                            errors.append(f"depends_on parent not in exchange_ids: {p}")
    rule = doc.get("success_rule")
    if rule is not None and not isinstance(rule, str):
        errors.append("success_rule must be a string")
    gate = doc.get("human_gate")
    if gate is not None and not isinstance(gate, dict):
        errors.append("human_gate must be an object")
    return errors


def validate_prior_vdc_refs(
    refs: list[dict[str, Any]],
    *,
    resolve_vdc,
    resolve_deliverable=None,
) -> list[str]:
    """校验 prior_vdc_refs。

    resolve_vdc(vdc_id) -> vdc dict | None
    resolve_deliverable(vdc_id) -> deliverable | None（可选；缺省则跳过内容哈希复验）
    """
    errors: list[str] = []
    if not isinstance(refs, list):
        return ["prior_vdc_refs must be a list"]
    for i, ref in enumerate(refs):
        if not isinstance(ref, dict):
            errors.append(f"ref[{i}] must be an object")
            continue
        vdc_id = ref.get("vdc_id")
        required = bool(ref.get("required", False))
        if not vdc_id:
            errors.append(f"ref[{i}] missing vdc_id")
            continue
        doc = resolve_vdc(vdc_id)
        if doc is None:
            if required:
                errors.append(f"required prior VDC not found: {vdc_id}")
            continue
        deliverable = None
        if resolve_deliverable is not None:
            deliverable = resolve_deliverable(vdc_id)
        if deliverable is not None:
            from .reverify import _all_ok

            checks = reverify(doc, deliverable)
            if not _all_ok(checks):
                errors.append(f"prior VDC reverify failed: {vdc_id}")
        else:
            # 至少检查双签形状 / settled 标记（无 deliverable 时弱校验）
            from . import vdc as V

            if not V.is_valid_settled(doc):
                if required:
                    errors.append(f"required prior VDC not valid settled: {vdc_id}")
    return errors


def bundle_ready(
    doc: dict[str, Any],
    *,
    exchange_states: dict[str, str],
) -> bool:
    """按 success_rule 判断目标是否达成（编排方使用）。"""
    if validate_bundle(doc):
        return False
    rule = doc.get("success_rule") or "all_settled"
    ids: list[str] = list(doc.get("exchange_ids") or [])
    if rule == "all_settled":
        return all(exchange_states.get(i) == "SETTLED" for i in ids)
    if isinstance(rule, str) and rule.startswith("quorum:"):
        try:
            n = int(rule.split(":", 1)[1])
        except ValueError:
            return False
        settled = sum(1 for i in ids if exchange_states.get(i) == "SETTLED")
        return settled >= n
    return False


def topological_order(doc: dict[str, Any]) -> list[str]:
    """按 depends_on 给出启动顺序；无依赖的并列按 exchange_ids 原序。"""
    errs = validate_bundle(doc)
    if errs:
        raise ValueError("; ".join(errs))
    ids: list[str] = list(doc["exchange_ids"])
    depends: dict[str, list[str]] = {
        k: list(v) for k, v in (doc.get("depends_on") or {}).items()
    }
    remaining = set(ids)
    ordered: list[str] = []
    while remaining:
        ready = [
            i for i in ids
            if i in remaining and all(p not in remaining for p in depends.get(i, []))
        ]
        if not ready:
            raise ValueError("depends_on contains a cycle or missing parents")
        for i in ready:
            ordered.append(i)
            remaining.remove(i)
    return ordered
