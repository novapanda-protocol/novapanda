"""NP-PRIV helpers · hash-only exposure and tag validation (body layer)."""

from __future__ import annotations

import json
from typing import Any, Optional

from .canonical import canonical_bytes
from .hashing import sha256_hex

GEO_LEVELS = ("none", "region", "city", "precise")
EXPOSURE_MODES = ("hash_only", "ciphertext_meta", "full_local")


def content_sha256(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
    elif isinstance(value, str):
        raw = value.encode("utf-8")
    else:
        raw = canonical_bytes(value)
    return "sha256:" + sha256_hex(raw)


def hash_only_wrap(deliverable: Any) -> dict:
    return {
        "delivery_exposure": "hash_only",
        "content_sha256": content_sha256(deliverable),
        "hint": "原文经授权通道获取；复验需持有原文或约定弱模式",
    }


def validate_privacy_tags(tags: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    exp = tags.get("delivery_exposure")
    if exp and exp not in EXPOSURE_MODES:
        errors.append(f"unknown delivery_exposure: {exp}")
    geo = tags.get("geo_precision")
    if geo and geo not in GEO_LEVELS:
        errors.append(f"unknown geo_precision: {geo}")
    cb = tags.get("cross_border")
    if cb and cb not in ("deny", "allow", "unknown"):
        errors.append(f"unknown cross_border: {cb}")
    return errors


def default_node_privacy() -> dict:
    return {
        "delivery_exposure": ["hash_only"],
        "geo_precision_default": "region",
        "geo_precision_max_public": "city",
        "data_minimization": True,
    }


def redact_for_log(value: Any, *, exposure: str = "hash_only") -> Any:
    if exposure != "hash_only":
        return value
    if isinstance(value, dict) and value.get("delivery_exposure") == "hash_only":
        return value
    try:
        return hash_only_wrap(value)
    except Exception:
        return {"delivery_exposure": "hash_only", "redacted": True}


def privacy_manifest_block() -> dict:
    return {
        "supported": True,
        **default_node_privacy(),
        "note": "NP-PRIV posture — not a compliance certificate",
    }


OPERATOR_PII_KEYS = frozenset({
    "email",
    "phone",
    "mobile",
    "operator_email",
    "operator_phone",
    "id_card",
    "national_id",
})


def assert_vdc_has_no_operator_pii(vdc_body: dict) -> list[str]:
    """NP-PRIV-03: Operator PII MUST NOT appear in VDC signed body."""
    hits: list[str] = []

    def walk(obj: Any, path: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                p = f"{path}.{k}" if path else k
                if str(k).lower() in OPERATOR_PII_KEYS:
                    hits.append(p)
                walk(v, p)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")

    walk(vdc_body)
    return hits


def ciphertext_meta_wrap(deliverable: Any, *, kid: str = "trial-kid") -> dict:
    """NP-PRIV ciphertext_meta exposure (informative body helper)."""
    return {
        "delivery_exposure": "ciphertext_meta",
        "alg": "aes-256-gcm",
        "kid": kid,
        "content_sha256": content_sha256(deliverable),
        "hint": "明文仅授权方；公开侧为密文元数据",
    }
