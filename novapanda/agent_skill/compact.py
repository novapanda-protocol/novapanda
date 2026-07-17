"""Token 经济紧凑视图：避免把完整 payload / hex 塞进 Agent 上下文。"""

from __future__ import annotations

from typing import Any, Optional


def short_agent_id(agent_id: Optional[str], *, keep: int = 10) -> Optional[str]:
    """压缩 ``ed25519:<base58>`` 为前缀…后缀，节省 token。"""
    if not agent_id:
        return None
    if len(agent_id) <= keep * 2 + 1:
        return agent_id
    return f"{agent_id[:keep]}…{agent_id[-keep:]}"


def compact_terminal_snapshot(snap: Any) -> dict[str, Any]:
    """``ExchangeTerminalSnapshot`` → 短 dict（无冗余 metadata）。"""
    return {
        "exchange_id": getattr(snap, "exchange_id", None),
        "state": getattr(snap, "state", None),
        "outcome": getattr(snap, "outcome_hint", None),
        "amount": getattr(snap, "price_amount", None),
        "currency": getattr(snap, "price_currency", None),
        "vdc_id": getattr(snap, "vdc_id", None),
        "resource_type": getattr(snap, "resource_type", None),
        "qty": getattr(snap, "quantity", None),
        "client": short_agent_id(getattr(snap, "client", None)),
        "provider": short_agent_id(getattr(snap, "provider", None)),
    }


def compact_graph(graph: Any, *, include_payloads: bool = False) -> dict[str, Any]:
    """DAG 视图：默认只给依赖边与资源类型，不含大 payload。"""
    tasks = []
    for t in getattr(graph, "tasks", ()) or ():
        item: dict[str, Any] = {
            "sub_id": t.sub_id,
            "resource_type": t.resource_type,
            "depends_on": list(t.depends_on),
            "tokens": int(t.token_estimate),
            "steps": int(t.step_estimate),
        }
        if include_payloads:
            item["payload"] = _clip_payload(t.payload)
        tasks.append(item)
    return {
        "goal_id": getattr(graph, "goal_id", None),
        "success_rule": getattr(graph, "success_rule", "all_settled"),
        "n_tasks": len(tasks),
        "tasks": tasks,
    }


def compact_auction(auction: Any) -> Optional[dict[str, Any]]:
    if auction is None:
        return None
    awards = []
    for a in getattr(auction, "awards", ()) or ():
        w = a.winner
        awards.append(
            {
                "sub_id": a.sub_id,
                "provider": short_agent_id(w.agent_id),
                "listing_id": w.listing_id,
                "amount": w.quote.price.amount,
                "currency": w.quote.price.currency,
                "score": round(float(a.breakdown.total), 4),
            }
        )
    return {
        "goal_id": getattr(auction, "goal_id", None),
        "awards": awards,
        "unfilled": list(getattr(auction, "unfilled", ()) or ()),
        "reason": _clip_str(getattr(auction, "reason", "") or "", 120),
    }


def compact_orchestration(
    report: Any, *, include_payloads: bool = False, include_results: bool = False
) -> dict[str, Any]:
    """编排报告紧凑版——Function Calling 默认返回此形状。"""
    phase = getattr(report, "phase", None)
    phase_v = phase.value if hasattr(phase, "value") else phase
    legs_out = []
    for leg in (getattr(report, "legs", None) or {}).values():
        row: dict[str, Any] = {
            "sub_id": leg.sub_id,
            "state": leg.state,
            "exchange_id": leg.exchange_id,
            "vdc_id": leg.vdc_id,
            "provider": short_agent_id(leg.provider),
        }
        if leg.error:
            row["error"] = _clip_str(leg.error, 120)
        if include_results and leg.result is not None:
            row["result"] = _clip_payload(leg.result)
        legs_out.append(row)

    out: dict[str, Any] = {
        "goal_id": report.goal_id,
        "phase": phase_v,
        "ok": phase_v == "done",
        "graph": compact_graph(report.graph, include_payloads=include_payloads),
        "auction": compact_auction(report.auction),
        "legs": legs_out,
        "bundle": _compact_bundle(getattr(report, "bundle_view", None)),
    }
    if report.error:
        out["error"] = _clip_str(report.error, 160)
    if include_results and report.final_delivery is not None:
        out["final_delivery"] = _clip_payload(report.final_delivery)
    return out


def _compact_bundle(bundle: Optional[dict]) -> Optional[dict[str, Any]]:
    if not bundle:
        return None
    return {
        "goal_id": bundle.get("goal_id"),
        "n_exchanges": len(bundle.get("exchange_ids") or []),
        "n_vdcs": len(bundle.get("vdc_ids") or []),
        "depends_on": bundle.get("depends_on") or {},
        "success_rule": bundle.get("success_rule"),
        # 完整 id 列表可能较长：只保留计数 + 最多 3 个样例
        "exchange_ids_sample": list(bundle.get("exchange_ids") or [])[:3],
        "vdc_ids_sample": list(bundle.get("vdc_ids") or [])[:3],
    }


def _clip_payload(payload: Any, limit: int = 240) -> Any:
    if payload is None or isinstance(payload, (int, float, bool)):
        return payload
    if isinstance(payload, str):
        return _clip_str(payload, limit)
    if isinstance(payload, dict):
        keys = list(payload.keys())
        if len(keys) > 8:
            return {"_keys": keys[:8], "_n": len(keys), "_note": "truncated"}
        return {k: _clip_payload(payload[k], limit // 2) for k in keys[:8]}
    if isinstance(payload, (list, tuple)):
        if len(payload) > 5:
            return [_clip_payload(x, limit // 2) for x in payload[:5]] + [
                f"…+{len(payload) - 5}"
            ]
        return [_clip_payload(x, limit // 2) for x in payload]
    return _clip_str(repr(payload), limit)


def _clip_str(s: str, limit: int) -> str:
    s = " ".join(str(s).split())
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "…"
