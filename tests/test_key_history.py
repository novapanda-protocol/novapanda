from novapanda.identity import Identity
from novapanda.key_history import build_key_history, validate_key_history, verify_with_key_history


def test_build_and_validate_key_history():
    identity = Identity.generate()
    doc = build_key_history(identity)
    assert validate_key_history(doc) == []


def test_tampered_key_history_fails():
    identity = Identity.generate()
    doc = build_key_history(identity)
    doc["current_pubkey"] = "tampered"
    assert validate_key_history(doc) != []


def test_verify_with_key_history_delegates_to_current_key():
    identity = Identity.generate()
    doc = build_key_history(identity)
    msg = b"hello"
    sig = identity.sign(msg)
    assert verify_with_key_history(identity.agent_id, sig, msg, doc) is True
