"""哈希工具：统一以 `sha256:<hex>` 表示，便于跨实现比对。"""

from __future__ import annotations

import hashlib

from .canonical import canonical_bytes


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def result_hash(data: bytes) -> str:
    return "sha256:" + sha256_hex(data)


def result_hash_of_json(obj) -> str:
    """对 JSON 交付物先做 canonical 再哈希，保证可复验。"""
    return result_hash(canonical_bytes(obj))
