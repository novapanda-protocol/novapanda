from troodon.identity import Identity, b58decode, b58encode, pubkey_from_agent_id, verify


def test_agent_id_format_and_roundtrip():
    ident = Identity.generate()
    assert ident.agent_id.startswith("ed25519:")
    assert pubkey_from_agent_id(ident.agent_id) == ident.public_bytes


def test_sign_verify_roundtrip():
    ident = Identity.generate()
    msg = b"hello world"
    sig = ident.sign(msg)
    assert verify(ident.agent_id, sig, msg) is True


def test_verify_fails_on_tampered_message():
    ident = Identity.generate()
    sig = ident.sign(b"original")
    assert verify(ident.agent_id, sig, b"tampered") is False


def test_verify_fails_on_wrong_identity():
    a = Identity.generate()
    b = Identity.generate()
    sig = a.sign(b"msg")
    assert verify(b.agent_id, sig, b"msg") is False


def test_deterministic_identity_from_private_bytes():
    ident = Identity.generate()
    raw = ident.private_bytes()
    restored = Identity.from_private_bytes(raw)
    assert restored.agent_id == ident.agent_id


def test_base58_roundtrip():
    data = b"\x00\x00\x01\x02\xff\xfe"
    assert b58decode(b58encode(data)) == data
