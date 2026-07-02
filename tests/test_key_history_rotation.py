from novapanda.identity import Identity
from novapanda.key_history import build_key_history, verify_with_key_history


def test_old_signature_via_previous_keys():
    old = Identity.generate()
    new = Identity.generate()
    message = b"rotated-agent-message"
    old_sig = old.sign(message)
    history = build_key_history(
        new,
        previous_keys=[{"pubkey": old.pubkey_b64url, "retired_at": "2026-01-01T00:00:00Z"}],
    )
    assert verify_with_key_history(new.agent_id, old_sig, message, history) is True
    assert verify_with_key_history(new.agent_id, old_sig, message, None) is False
