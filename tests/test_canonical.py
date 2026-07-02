import pytest

from novapanda.canonical import canonical_bytes, canonical_str


def test_key_order_independent():
    a = {"b": 1, "a": 2, "c": {"y": 1, "x": 2}}
    b = {"a": 2, "c": {"x": 2, "y": 1}, "b": 1}
    assert canonical_bytes(a) == canonical_bytes(b)


def test_compact_and_sorted():
    assert canonical_str({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_float_rejected():
    with pytest.raises(ValueError):
        canonical_bytes({"x": 1.5})


def test_nfc_normalization():
    # 同一字符的两种 Unicode 组合应归一为相同字节
    composed = "\u00e9"          # é
    decomposed = "e\u0301"        # e + combining acute
    assert canonical_bytes({"k": composed}) == canonical_bytes({"k": decomposed})


def test_unicode_preserved_utf8():
    assert canonical_str({"k": "交割"}) == '{"k":"交割"}'


def test_nested_list_order_preserved():
    assert canonical_str({"k": [3, 1, 2]}) == '{"k":[3,1,2]}'
