import json
from pathlib import Path

import pytest

from troodon.v1.cbor_codec import cbor_available, canonical_cbor_bytes
from troodon.vdc import provider_signing_bytes, provider_signing_cbor_bytes, provider_signing_payload

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "sdk_parity_vector.json"


@pytest.mark.skipif(not cbor_available(), reason="cbor2 unavailable")
def test_vdc_provider_signing_cbor_cross_vector():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    vdc = data["unsigned_vdc"]
    json_bytes = provider_signing_bytes(vdc)
    assert json_bytes.hex() == data["provider_signing_bytes_hex"]
    cbor_bytes = provider_signing_cbor_bytes(vdc)
    assert len(cbor_bytes) > 0
    assert cbor_bytes != json_bytes
    assert provider_signing_cbor_bytes(vdc) == provider_signing_cbor_bytes(
        provider_signing_payload(vdc)
    )


@pytest.mark.skipif(not cbor_available(), reason="cbor2 unavailable")
def test_vdc_cbor_deterministic():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload = provider_signing_payload(data["unsigned_vdc"])
    a = canonical_cbor_bytes(payload)
    b = provider_signing_cbor_bytes(data["unsigned_vdc"])
    assert a == b
