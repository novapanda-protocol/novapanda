"""NP-LITE · thin transport envelope (semantic round-trip to C1 canonical JSON)."""

from __future__ import annotations

import base64
import json
from typing import Any

from .canonical import canonical_bytes

LITE_VERSION = "0.1"
CANONICAL_BINDING = "novapanda-c1"


def to_lite_envelope(value: Any) -> dict:
    raw = canonical_bytes(value)
    return {
        "lite_version": LITE_VERSION,
        "canonical": CANONICAL_BINDING,
        "payload_b64": base64.b64encode(raw).decode("ascii"),
        "encoding": "utf-8-json-canonical",
    }


def from_lite_envelope(envelope: dict) -> Any:
    if envelope.get("lite_version") != LITE_VERSION:
        raise ValueError("unsupported_lite_version")
    if envelope.get("canonical") != CANONICAL_BINDING:
        raise ValueError("canonical_binding_mismatch")
    payload = envelope.get("payload_b64")
    if not payload:
        raise ValueError("missing_payload")
    raw = base64.b64decode(payload)
    return json.loads(raw.decode("utf-8"))


def roundtrip(value: Any) -> dict:
    env = to_lite_envelope(value)
    restored = from_lite_envelope(env)
    return {
        "envelope": env,
        "restored": restored,
        "equal": canonical_bytes(restored) == canonical_bytes(value),
    }


# Device runtime states MUST NOT be used as exchange `state` (NP-LITE-04).
DEVICE_RUNTIME_STATES = frozenset({
    "idle",
    "busy",
    "fault",
    "charging",
    "offline",
    "booting",
})

EXCHANGE_STATES = frozenset({
    "PROPOSED",
    "CONTRACTED",
    "ESCROWED",
    "DELIVERED",
    "VERIFIED",
    "SETTLED",
    "REJECTED",
    "DISPUTED",
    "EXPIRED_REFUNDED",
    "CANCELLED",
})


def assert_not_device_as_exchange_state(state: str) -> None:
    if state in DEVICE_RUNTIME_STATES:
        raise ValueError("device_runtime_state_not_exchange_state")
    if state not in EXCHANGE_STATES:
        raise ValueError("unknown_exchange_state")


class OfflineQueue:
    """Minimal offline replay queue with idempotency (NP-LITE-03)."""

    def __init__(self) -> None:
        self._seen: set[str] = set()
        self._items: list[dict] = []

    def enqueue(self, *, idempotency_key: str, payload: Any) -> dict:
        if idempotency_key in self._seen:
            return {"accepted": False, "reason": "duplicate", "idempotency_key": idempotency_key}
        self._seen.add(idempotency_key)
        item = {"idempotency_key": idempotency_key, "payload": payload}
        self._items.append(item)
        return {"accepted": True, "item": item}

    def drain(self) -> list[dict]:
        out = list(self._items)
        self._items.clear()
        return out
