from novapanda.identity import Identity
from novapanda.v1.did import agent_id_to_did, build_did_document, did_to_agent_id, validate_did_document


def test_did_roundtrip():
    identity = Identity.generate()
    did = agent_id_to_did(identity.agent_id)
    assert did_to_agent_id(did) == identity.agent_id


def test_did_document_validates():
    identity = Identity.generate()
    doc = build_did_document(identity, services=[{"type": "exchange", "id": "#ex1"}])
    assert validate_did_document(doc) == []
