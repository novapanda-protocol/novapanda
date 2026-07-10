"""C-LITE-RT — NP-LITE thin envelope ↔ C1 canonical round-trip."""

from __future__ import annotations

import pytest

from novapanda.canonical import canonical_bytes
from novapanda.lite import (
    OfflineQueue,
    assert_not_device_as_exchange_state,
    from_lite_envelope,
    roundtrip,
    to_lite_envelope,
)


SAMPLE = {"z": 1, "a": 2, "nested": {"b": True}}


def test_c_lite_rt_01_roundtrip_equality():
    result = roundtrip(SAMPLE)
    assert result["equal"] is True
    assert canonical_bytes(result["restored"]) == canonical_bytes(SAMPLE)


def test_c_lite_rt_02_binding_mismatch_rejects():
    env = to_lite_envelope(SAMPLE)
    env["canonical"] = "wrong-binding"
    with pytest.raises(ValueError, match="canonical_binding_mismatch"):
        from_lite_envelope(env)
    bad_ver = to_lite_envelope(SAMPLE)
    bad_ver["lite_version"] = "9.9"
    with pytest.raises(ValueError, match="unsupported_lite_version"):
        from_lite_envelope(bad_ver)


def test_c_lite_rt_03_envelope_maps_to_c1_canonical_bytes():
    env = to_lite_envelope(SAMPLE)
    restored = from_lite_envelope(env)
    # Same semantic object ⇒ same C1 bytes
    assert canonical_bytes(restored) == canonical_bytes(SAMPLE)
    # Envelope itself is transport; payload_b64 carries C1 bytes
    import base64

    raw = base64.b64decode(env["payload_b64"])
    assert raw == canonical_bytes(SAMPLE)


def test_c_lite_rt_04_offline_queue_idempotent_and_device_state_guard():
    q = OfflineQueue()
    assert q.enqueue(idempotency_key="k1", payload={"x": 1})["accepted"] is True
    assert q.enqueue(idempotency_key="k1", payload={"x": 2})["accepted"] is False
    assert len(q.drain()) == 1
    with pytest.raises(ValueError, match="device_runtime_state"):
        assert_not_device_as_exchange_state("busy")
    assert_not_device_as_exchange_state("SETTLED")
