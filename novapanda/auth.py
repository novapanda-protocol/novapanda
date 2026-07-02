"""请求级鉴权：跨语言一致的请求签名方案 + 防重放。

SDK 与节点共享同一套 `request_signing_bytes`，因此任何语言的客户端都能签出节点可验的签名。
- 认证（authn）：X-Agent-Id + X-Nonce + X-Signature；签名覆盖 method/path/nonce/body 哈希。
- 防重放：同一 agent 的 nonce 不可复用（有界窗口）。
- 授权（authz）：由各端点按"调用者是否为该交换的相关方"判定。
"""

from __future__ import annotations

from collections import deque
from typing import Deque, Optional

from .canonical import canonical_bytes
from .hashing import sha256_hex
from .identity import Identity, verify


def request_signing_bytes(method: str, path: str, nonce: str, body: bytes) -> bytes:
    return canonical_bytes({
        "method": method.upper(),
        "path": path,
        "nonce": nonce,
        "body_sha256": sha256_hex(body),
    })


def sign_request(identity: Identity, method: str, path: str, nonce: str, body: bytes) -> str:
    return identity.sign(request_signing_bytes(method, path, nonce, body))


def verify_request(agent_id: str, signature: str, method: str, path: str,
                   nonce: str, body: bytes) -> bool:
    return verify(agent_id, signature, request_signing_bytes(method, path, nonce, body))


class NonceStore:
    """有界防重放存储：记录每个 agent 最近用过的 nonce。"""

    def __init__(self, window: int = 4096) -> None:
        self._window = window
        self._seen: dict[str, set[str]] = {}
        self._order: dict[str, Deque[str]] = {}

    def check_and_add(self, agent_id: str, nonce: str) -> bool:
        seen = self._seen.setdefault(agent_id, set())
        if nonce in seen:
            return False
        order = self._order.setdefault(agent_id, deque())
        seen.add(nonce)
        order.append(nonce)
        while len(order) > self._window:
            old = order.popleft()
            seen.discard(old)
        return True
