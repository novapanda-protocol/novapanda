"""T18 — micro-benchmarks (non-gating; inform performance memo)."""

from __future__ import annotations

import time

from novapanda.canonical import canonical_bytes
from novapanda.hashing import sha256_hex
from novapanda.identity import Identity, verify

_WARMUP = 50
_ITER = 200


def _mean_ms(fn, iterations: int = _ITER) -> float:
    for _ in range(_WARMUP):
        fn()
    start = time.perf_counter()
    for _ in range(iterations):
        fn()
    return (time.perf_counter() - start) / iterations * 1000


def test_bench_canonical_sha256_under_target():
    payload = {"vdc_id": "v", "nested": {"a": 1, "b": 2}}

    def run():
        sha256_hex(canonical_bytes(payload))

    ms = _mean_ms(run)
    assert ms < 10.0, f"canonical+sha256 mean {ms:.3f}ms exceeds 10ms guide"


def test_bench_ed25519_verify_under_target():
    idn = Identity.generate()
    msg = canonical_bytes({"x": 1})
    sig = idn.sign(msg)

    def run():
        assert verify(idn.agent_id, sig, msg)

    ms = _mean_ms(run)
    assert ms < 5.0, f"verify mean {ms:.3f}ms exceeds 5ms guide"
