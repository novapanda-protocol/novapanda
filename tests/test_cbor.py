import pytest

from troodon.canonical import canonical_bytes
from troodon.v1.cbor_codec import canonical_cbor_bytes, cbor_available


def test_cbor_module_importable_without_native():
    from troodon.v1 import cbor_codec

    assert hasattr(cbor_codec, "cbor_available")


@pytest.mark.skipif(not cbor_available(), reason="cbor2 unavailable")
def test_cbor_deterministic():
    obj = {"b": 1, "a": "x", "nested": {"z": 2, "y": "ok"}}
    a = canonical_cbor_bytes(obj)
    b = canonical_cbor_bytes({"a": "x", "b": 1, "nested": {"y": "ok", "z": 2}})
    assert a == b
    assert len(a) > 0
    assert canonical_bytes(obj) != a
