"""信誉门槛：propose/escrow 前只读 gate（不写入账本）。"""

from __future__ import annotations

from typing import Optional


def apply_witness_score_boost(
    score: Optional[float],
    *,
    witness_stake_count: int = 0,
    witness_bonus_per_stake: float = 0.05,
    witness_bonus_cap: float = 0.25,
) -> tuple[Optional[float], float]:
    """见证质押加权：有效 score = min(1.0, score + bonus)。"""
    if score is None:
        return None, 0.0
    bonus = min(witness_bonus_cap, witness_stake_count * witness_bonus_per_stake)
    effective = min(1.0, round(score + bonus, 4))
    return effective, bonus


def check_reputation_gate(
    reputation_log,
    agent_id: str,
    *,
    min_score: Optional[float],
    weights: Optional[dict[str, float]] = None,
    strict_no_history: bool = False,
    witness_stake_count: int = 0,
    witness_bonus_per_stake: float = 0.05,
    witness_bonus_cap: float = 0.25,
) -> dict:
    """返回 {allowed, score, effective_score, witness_bonus, entry_count, reason}。"""
    if min_score is None:
        return {
            "allowed": True,
            "score": None,
            "effective_score": None,
            "witness_bonus": 0.0,
            "entry_count": 0,
            "reason": "gate disabled",
        }

    summary = reputation_log.weighted_score(agent_id, weights=weights or {})
    score = summary.get("score")
    entry_count = summary.get("entry_count", 0)
    effective, bonus = apply_witness_score_boost(
        score,
        witness_stake_count=witness_stake_count,
        witness_bonus_per_stake=witness_bonus_per_stake,
        witness_bonus_cap=witness_bonus_cap,
    )

    if entry_count == 0 or score is None:
        if strict_no_history:
            return {
                "allowed": False,
                "score": score,
                "effective_score": effective,
                "witness_bonus": bonus,
                "entry_count": entry_count,
                "reason": "no reputation history (strict gate)",
            }
        return {
            "allowed": True,
            "score": score,
            "effective_score": effective,
            "witness_bonus": bonus,
            "entry_count": entry_count,
            "reason": "no reputation history",
        }

    check_score = effective if effective is not None else score
    if check_score < min_score:
        return {
            "allowed": False,
            "score": score,
            "effective_score": effective,
            "witness_bonus": bonus,
            "entry_count": entry_count,
            "reason": f"effective score {check_score} below minimum {min_score}",
        }

    return {
        "allowed": True,
        "score": score,
        "effective_score": effective,
        "witness_bonus": bonus,
        "entry_count": entry_count,
        "reason": "score ok",
    }
