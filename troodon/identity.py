"""身份与签名：Ed25519 + agent_id = "ed25519:" + base58(pubkey)。

私钥永不离开本地；任何对端只凭 agent_id（含公钥）即可验签——无需预建关系。
"""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

_PREFIX = "ed25519:"
_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = ""
    while n > 0:
        n, rem = divmod(n, 58)
        out = _B58_ALPHABET[rem] + out
    pad = 0
    for byte in data:
        if byte == 0:
            pad += 1
        else:
            break
    return _B58_ALPHABET[0] * pad + out


def b58decode(s: str) -> bytes:
    n = 0
    for ch in s:
        n = n * 58 + _B58_ALPHABET.index(ch)
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n > 0 else b""
    pad = 0
    for ch in s:
        if ch == _B58_ALPHABET[0]:
            pad += 1
        else:
            break
    return b"\x00" * pad + body


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def pubkey_from_agent_id(agent_id: str) -> bytes:
    if not agent_id.startswith(_PREFIX):
        raise ValueError(f"非法 agent_id（缺少 {_PREFIX} 前缀）: {agent_id}")
    return b58decode(agent_id[len(_PREFIX):])


class Identity:
    """持有 Ed25519 私钥的本地身份。"""

    def __init__(self, private_key: Ed25519PrivateKey):
        self._sk = private_key

    @classmethod
    def generate(cls) -> "Identity":
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_private_bytes(cls, raw: bytes) -> "Identity":
        return cls(Ed25519PrivateKey.from_private_bytes(raw))

    def private_bytes(self) -> bytes:
        return self._sk.private_bytes(
            Encoding.Raw, PrivateFormat.Raw, NoEncryption()
        )

    @property
    def public_bytes(self) -> bytes:
        return self._sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    @property
    def agent_id(self) -> str:
        return _PREFIX + b58encode(self.public_bytes)

    @property
    def pubkey_b64url(self) -> str:
        return _b64url_encode(self.public_bytes)

    def sign(self, message: bytes) -> str:
        return _b64url_encode(self._sk.sign(message))


def verify(agent_id: str, signature_b64url: str, message: bytes) -> bool:
    try:
        pk = Ed25519PublicKey.from_public_bytes(pubkey_from_agent_id(agent_id))
        pk.verify(_b64url_decode(signature_b64url), message)
        return True
    except Exception:
        return False


def verify_pubkey_b64url(pubkey_b64url: str, signature_b64url: str, message: bytes) -> bool:
    """用裸 base64url 公钥验签（密钥轮换历史）。"""
    try:
        pk = Ed25519PublicKey.from_public_bytes(_b64url_decode(pubkey_b64url))
        pk.verify(_b64url_decode(signature_b64url), message)
        return True
    except Exception:
        return False
