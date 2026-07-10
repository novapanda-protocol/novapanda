"""C-PRIV — NP-PRIV posture vectors (hash_only / no Operator PII)."""

from __future__ import annotations

from novapanda.hashing import result_hash_of_json
from novapanda.privacy import (
    assert_vdc_has_no_operator_pii,
    ciphertext_meta_wrap,
    hash_only_wrap,
    validate_privacy_tags,
)


def test_c_priv_01_hash_only_preserves_content_hash():
    from novapanda.canonical import canonical_bytes
    from novapanda.hashing import sha256_hex

    deliverable = {"invoice_no": "INV-1", "lines": [{"sku": "a", "qty": 2}]}
    wrapped = hash_only_wrap(deliverable)
    assert wrapped["delivery_exposure"] == "hash_only"
    expected = "sha256:" + sha256_hex(canonical_bytes(deliverable))
    assert wrapped["content_sha256"] == expected
    # Independent check: same digest via result_hash path
    assert wrapped["content_sha256"] == result_hash_of_json(deliverable)


def test_c_priv_02_vdc_body_rejects_operator_pii_keys():
    clean = {
        "vdc_version": "1",
        "exchange_id": "ex-1",
        "result_hash": "sha256:abc",
        "signatures": {"provider_sig": "x", "client_sig": "y"},
    }
    assert assert_vdc_has_no_operator_pii(clean) == []
    dirty = {**clean, "email": "ops@example.com"}
    assert "email" in assert_vdc_has_no_operator_pii(dirty)


def test_c_priv_03_ciphertext_meta_and_public_geo_tags():
    meta = ciphertext_meta_wrap({"secret": "x"})
    assert meta["delivery_exposure"] == "ciphertext_meta"
    assert "kid" in meta
    assert validate_privacy_tags(
        {"delivery_exposure": "hash_only", "geo_precision": "region", "cross_border": "deny"}
    ) == []
    # precise is allowed as a tag value but public max is policy (city); tag validation accepts both
    assert validate_privacy_tags({"geo_precision": "precise"}) == []
