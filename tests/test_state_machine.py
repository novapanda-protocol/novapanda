import pytest

from troodon import state_machine as sm


def test_happy_path_transitions_allowed():
    chain = [sm.PROPOSED, sm.CONTRACTED, sm.ESCROWED, sm.DELIVERED, sm.VERIFIED, sm.SETTLED]
    for src, dst in zip(chain, chain[1:]):
        assert sm.can_transition(src, dst) is True


def test_illegal_transition_rejected():
    assert sm.can_transition(sm.PROPOSED, sm.DELIVERED) is False
    with pytest.raises(sm.StateError):
        sm.assert_transition(sm.ESCROWED, sm.SETTLED)


def test_terminal_states_have_no_exit():
    for s in sm.TERMINAL_STATES:
        assert sm.TRANSITIONS[s] == frozenset()


def test_reject_and_refund_reachable():
    assert sm.can_transition(sm.DELIVERED, sm.REJECTED) is True
    assert sm.can_transition(sm.ESCROWED, sm.EXPIRED_REFUNDED) is True
    assert sm.can_transition(sm.VERIFIED, sm.EXPIRED_REFUNDED) is True
