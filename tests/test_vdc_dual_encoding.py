import pytest

from novapanda import vdc as V
from novapanda.identity import Identity
from novapanda.v1.cbor_codec import cbor_available


@pytest.mark.skipif(not cbor_available(), reason="cbor2 unavailable")
def test_provider_sign_cbor_encoding_roundtrip():
    client, provider = Identity.generate(), Identity.generate()
    doc = V.build_vdc(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        result_hash="sha256:" + "a" * 64,
        rule_id="R-extract-invoice-v1",
        evidence_level="dual_signed",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        idempotency_key="cbor-sign-1",
    )
    V.provider_sign(doc, provider, encoding="cbor")
    assert doc["signatures"]["provider_payload_encoding"] == "cbor"
    assert V.verify_provider(doc) is True


def test_provider_sign_json_default_unchanged():
    client, provider = Identity.generate(), Identity.generate()
    doc = V.build_vdc(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        result_hash="sha256:" + "b" * 64,
        rule_id="R-extract-invoice-v1",
        evidence_level="dual_signed",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        idempotency_key="json-sign-1",
    )
    V.provider_sign(doc, provider)
    assert doc["signatures"].get("provider_payload_encoding", "json") == "json"
    assert V.verify_provider(doc) is True
