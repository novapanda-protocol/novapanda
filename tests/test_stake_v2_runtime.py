import pytest
from troodon.v2 import federation as fed_mod
from troodon.v2 import witness as witness_mod
from troodon.v2.stake import lock_stake, release_stake, reset_stakes_for_tests
from troodon.identity import Identity


@pytest.fixture(autouse=True)
def _enable_v2(monkeypatch):
    monkeypatch.setattr(witness_mod, "WITNESS_V2_ENABLED", True)
    monkeypatch.setattr(fed_mod, "FEDERATION_V2_ENABLED", True)
    reset_stakes_for_tests()
    yield
    reset_stakes_for_tests()


def test_lock_and_release_stake():
    agent = Identity.generate()
    stake = lock_stake(
        agent_id=agent.agent_id, amount=100, currency="USD", purpose="witness bond"
    )
    assert stake["status"] == "locked"
    released = release_stake(stake["stake_id"])
    assert released["status"] == "released"


def test_slash_after_lock():
    from troodon.exchange import ExchangeEngine
    from troodon.settlement import MockSettlement

    agent = Identity.generate()
    stake = lock_stake(
        agent_id=agent.agent_id, amount=50, currency="USD", purpose="slash test"
    )
    engine = ExchangeEngine(MockSettlement())
    slashed = engine.slash_stake_v2(
        stake, reason="malicious witness", slashed_by=agent.agent_id
    )
    assert slashed["status"] == "slashed"
