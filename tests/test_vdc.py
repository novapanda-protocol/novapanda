import pytest

from troodon.hashing import result_hash_of_json
from troodon.identity import Identity
from troodon import vdc as V


def _fresh_vdc(client: Identity, provider: Identity) -> dict:
    deliverable = {"invoice_no": "A-001", "total": "100.00"}
    return V.build_vdc(
        client=client.agent_id,
        provider=provider.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        result_hash=result_hash_of_json(deliverable),
        rule_id="R-extract-schema-v1",
        evidence_level="dual_signed",
        started_at="2026-06-28T03:00:00Z",
        finished_at="2026-06-28T03:00:04Z",
        idempotency_key="task-7741",
    )


def test_provider_then_client_sign_and_validate():
    client, provider = Identity.generate(), Identity.generate()
    doc = _fresh_vdc(client, provider)

    V.provider_sign(doc, provider)
    assert V.verify_provider(doc) is True

    V.client_sign(doc, client)
    assert V.verify_client(doc) is True

    doc["state"] = "SETTLED"
    assert V.is_valid_settled(doc) is True


def test_state_transition_does_not_break_provider_sig():
    """DELIVERED→SETTLED 改 state 不应使 provider_sig 失效（state 不进签名）。"""
    client, provider = Identity.generate(), Identity.generate()
    doc = _fresh_vdc(client, provider)
    V.provider_sign(doc, provider)
    assert V.verify_provider(doc) is True
    doc["state"] = "SETTLED"
    assert V.verify_provider(doc) is True


def test_tamper_field_breaks_provider_sig():
    client, provider = Identity.generate(), Identity.generate()
    doc = _fresh_vdc(client, provider)
    V.provider_sign(doc, provider)
    doc["quantity"] = 999
    assert V.verify_provider(doc) is False


def test_tamper_breaks_client_sig():
    client, provider = Identity.generate(), Identity.generate()
    doc = _fresh_vdc(client, provider)
    V.provider_sign(doc, provider)
    V.client_sign(doc, client)
    doc["result_hash"] = "sha256:deadbeef"
    assert V.verify_client(doc) is False


def test_client_cannot_sign_before_provider():
    client, provider = Identity.generate(), Identity.generate()
    doc = _fresh_vdc(client, provider)
    with pytest.raises(ValueError):
        V.client_sign(doc, client)


def test_wrong_identity_cannot_sign():
    client, provider = Identity.generate(), Identity.generate()
    other = Identity.generate()
    doc = _fresh_vdc(client, provider)
    with pytest.raises(ValueError):
        V.provider_sign(doc, other)


def test_not_settled_until_state_set():
    client, provider = Identity.generate(), Identity.generate()
    doc = _fresh_vdc(client, provider)
    V.provider_sign(doc, provider)
    V.client_sign(doc, client)
    # 双签齐了，但 state 还是 DELIVERED
    assert V.is_valid_settled(doc) is False
