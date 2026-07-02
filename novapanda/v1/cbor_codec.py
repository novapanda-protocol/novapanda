"""CBOR canonical 编码 v2 占位（依赖 cbor2，可选）。"""

from __future__ import annotations

from ..canonical import _normalize


def cbor_available() -> bool:
    try:
        import cbor2

        cbor2.dumps({"ok": 1}, canonical=True)
        return True
    except Exception:
        return False


def canonical_cbor_bytes(obj) -> bytes:
    """对 canonical 归一化后的对象做 CBOR 编码（确定性）。"""
    if not cbor_available():
        raise ImportError("cbor2 不可用（未安装或 native 扩展加载失败）")
    import cbor2

    normalized = _normalize(obj)
    return cbor2.dumps(normalized, canonical=True)
