"""交换状态机：唯一权威的生命周期定义。

任何节点实现必须遵循同一张转移表，才能保证跨节点 VDC 与信誉可被一致解读。
"""

from __future__ import annotations

PROPOSED = "PROPOSED"
CONTRACTED = "CONTRACTED"
ESCROWED = "ESCROWED"
DELIVERED = "DELIVERED"
VERIFIED = "VERIFIED"
SETTLED = "SETTLED"
REJECTED = "REJECTED"
EXPIRED_REFUNDED = "EXPIRED_REFUNDED"
CANCELLED = "CANCELLED"
DISPUTED = "DISPUTED"

TERMINAL_STATES = frozenset({SETTLED, REJECTED, EXPIRED_REFUNDED, CANCELLED})

TRANSITIONS: dict[str, frozenset[str]] = {
    PROPOSED: frozenset({CONTRACTED, CANCELLED, EXPIRED_REFUNDED}),
    CONTRACTED: frozenset({ESCROWED, CANCELLED, EXPIRED_REFUNDED}),
    ESCROWED: frozenset({DELIVERED, EXPIRED_REFUNDED, CANCELLED}),
    DELIVERED: frozenset({VERIFIED, REJECTED, EXPIRED_REFUNDED}),
    VERIFIED: frozenset({SETTLED, DISPUTED, EXPIRED_REFUNDED}),
    DISPUTED: frozenset({SETTLED, REJECTED}),
    SETTLED: frozenset(),
    REJECTED: frozenset(),
    EXPIRED_REFUNDED: frozenset(),
    CANCELLED: frozenset(),
}


class StateError(Exception):
    pass


def can_transition(src: str, dst: str) -> bool:
    return dst in TRANSITIONS.get(src, frozenset())


def assert_transition(src: str, dst: str) -> None:
    if not can_transition(src, dst):
        raise StateError(f"非法状态转移：{src} -> {dst}")
