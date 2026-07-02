"""Canonical JSON 序列化（v0，目标对齐 RFC 8785 / JCS）。

跨语言可复验是普适性的根本：任何实现对同一对象必须产出**同一字节序列**，
从而 SHA-256 与签名验证在 Python/TS/Go/Rust 间一致。

v0 规则：
- dict 键按 Unicode 码点字典序排序；
- 紧凑分隔符，无多余空白；
- 字符串做 NFC 归一；
- UTF-8 编码；
- **拒绝 float**：数字一律用整数；小数请以字符串承载（避免跨语言浮点格式分歧）。
"""

from __future__ import annotations

import json
import unicodedata
from typing import Any


def _normalize(obj: Any) -> Any:
    if obj is None or isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        raise ValueError(
            "canonical JSON (v0) 不接受 float；整数用 int，小数请用字符串承载。"
        )
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if not isinstance(k, str):
                raise TypeError(f"canonical JSON 的键必须是字符串，得到 {type(k)}")
            out[unicodedata.normalize("NFC", k)] = _normalize(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    raise TypeError(f"canonical JSON 不支持的类型: {type(obj)}")


def canonical_str(obj: Any) -> str:
    return json.dumps(
        _normalize(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def canonical_bytes(obj: Any) -> bytes:
    return canonical_str(obj).encode("utf-8")
