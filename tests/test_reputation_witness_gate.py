from troodon.reputation_gate import apply_witness_score_boost, check_reputation_gate
import pytest


def test_witness_bonus_raises_effective_score():
    effective, bonus = apply_witness_score_boost(0.8, witness_stake_count=3, witness_bonus_per_stake=0.05)
    assert bonus == pytest.approx(0.15)
    assert effective == 0.95


def test_witness_bonus_capped():
    effective, bonus = apply_witness_score_boost(0.8, witness_stake_count=10, witness_bonus_cap=0.25)
    assert bonus == 0.25
    assert effective == 1.0


def test_gate_uses_witness_stakes_to_pass():
    class FakeLog:
        def weighted_score(self, agent_id, weights=None):
            return {"score": 0.8, "entry_count": 1}

    blocked = check_reputation_gate(
        FakeLog(),
        "ed25519:provider",
        min_score=0.85,
        witness_stake_count=0,
    )
    assert blocked["allowed"] is False

    allowed = check_reputation_gate(
        FakeLog(),
        "ed25519:provider",
        min_score=0.85,
        witness_stake_count=1,
        witness_bonus_per_stake=0.05,
    )
    assert allowed["effective_score"] == 0.85
    assert allowed["allowed"] is True
