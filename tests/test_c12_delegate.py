"""C12 — NP-DELEGATE constraint vectors."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from novapanda.delegate import DelegationRegistry, delegation_signing_bytes
from novapanda.identity import Identity


def _cred(issuer: Identity, subject: Identity, **kwargs) -> dict:
    exp = (datetime.now(timezone.utc) + timedelta(hours=kwargs.pop("hours", 24))).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    cred = {
        "delegate_version": "0.1",
        "issuer_agent_id": issuer.agent_id,
        "subject_agent_id": subject.agent_id,
        "scope": kwargs.get("scope", ["escrow"]),
        "constraints": kwargs.get(
            "constraints",
            {"max_amount": 10, "currency": "USD", "rails_allowlist": ["mock"]},
        ),
        "expires_at": exp,
        "issued_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    cred["issuer_sig"] = issuer.sign(delegation_signing_bytes(cred))
    return cred


def test_c12_expired_delegation_rejected():
    reg = DelegationRegistry()
    issuer, subject = Identity.generate(), Identity.generate()
    cred = _cred(issuer, subject, hours=-1)
    cred["expires_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    cred["issuer_sig"] = issuer.sign(delegation_signing_bytes(cred))
    with pytest.raises(ValueError, match="already_expired"):
        reg.register(cred)


def test_c12_rail_not_in_allowlist():
    reg = DelegationRegistry()
    issuer, subject = Identity.generate(), Identity.generate()
    dlg = reg.register(_cred(issuer, subject))
    with pytest.raises(ValueError, match="rail_not_allowed"):
        reg.validate_action(
            dlg["delegation_id"],
            subject_agent_id=subject.agent_id,
            action="escrow",
            amount=1,
            currency="USD",
            rail="x402",
        )


def test_c12_amount_exceeds_max():
    reg = DelegationRegistry()
    issuer, subject = Identity.generate(), Identity.generate()
    dlg = reg.register(_cred(issuer, subject))
    with pytest.raises(ValueError, match="amount_exceeds_max"):
        reg.validate_action(
            dlg["delegation_id"],
            subject_agent_id=subject.agent_id,
            action="escrow",
            amount=99,
            currency="USD",
            rail="mock",
        )


def test_c12_scope_denied():
    reg = DelegationRegistry()
    issuer, subject = Identity.generate(), Identity.generate()
    dlg = reg.register(_cred(issuer, subject, scope=["propose"]))
    with pytest.raises(ValueError, match="scope_denied"):
        reg.validate_action(
            dlg["delegation_id"],
            subject_agent_id=subject.agent_id,
            action="escrow",
            amount=1,
            currency="USD",
            rail="mock",
        )


def test_c12_05_revoke_then_deny():
    reg = DelegationRegistry()
    issuer, subject = Identity.generate(), Identity.generate()
    dlg = reg.register(_cred(issuer, subject))
    dlg_id = dlg["delegation_id"]
    reg.revoke(dlg_id, issuer_agent_id=issuer.agent_id)
    with pytest.raises(ValueError, match="delegation_invalid"):
        reg.validate_action(
            dlg_id,
            subject_agent_id=subject.agent_id,
            action="escrow",
            amount=1,
            currency="USD",
            rail="mock",
        )


def test_c12_06_period_quota_exceeded():
    reg = DelegationRegistry()
    issuer, subject = Identity.generate(), Identity.generate()
    dlg = reg.register(
        _cred(
            issuer,
            subject,
            constraints={
                "max_amount": 10,
                "currency": "USD",
                "period": "P1D",
                "rails_allowlist": ["mock"],
            },
        )
    )
    dlg_id = dlg["delegation_id"]
    reg.validate_action(
        dlg_id,
        subject_agent_id=subject.agent_id,
        action="escrow",
        amount=6,
        currency="USD",
        rail="mock",
    )
    with pytest.raises(ValueError, match="period_quota_exceeded"):
        reg.validate_action(
            dlg_id,
            subject_agent_id=subject.agent_id,
            action="escrow",
            amount=6,
            currency="USD",
            rail="mock",
        )


def test_c12_07_currency_mismatch():
    reg = DelegationRegistry()
    issuer, subject = Identity.generate(), Identity.generate()
    dlg = reg.register(_cred(issuer, subject))
    with pytest.raises(ValueError, match="currency_mismatch"):
        reg.validate_action(
            dlg["delegation_id"],
            subject_agent_id=subject.agent_id,
            action="escrow",
            amount=1,
            currency="EUR",
            rail="mock",
        )


def test_c12_08_http_x_delegation_id_path():
    from fastapi.testclient import TestClient

    from novapanda.node import create_app

    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    issuer, subject = Identity.generate(), Identity.generate()
    cred = _cred(issuer, subject, scope=["propose", "escrow"])
    r = tc.post("/node/delegations", json={"credential": cred})
    assert r.status_code == 201
    dlg_id = r.json()["delegation"]["delegation_id"]
    # revoke via signed issuer (auth=False still needs caller for revoke)
    app.state.auth_enabled = True
    # public get works without auth
    g = tc.get(f"/node/delegations/{dlg_id}")
    assert g.status_code == 200
    assert g.json()["delegation"]["note"]
    assert "not a balance" in g.json()["delegation"]["note"]
