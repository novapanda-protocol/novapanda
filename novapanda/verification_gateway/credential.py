"""验收凭证（Verification Credential）：网关对「已通过验收」的密码学声明。

与 VDC 双签正交：
- VDC provider_sig / client_sig = 交割事实与双方认可
- VerificationCredential = 独立验收方对 rule 达标的见证（可多网关 quorum）
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

from novapanda.canonical import canonical_bytes
from novapanda.identity import Identity, verify as verify_sig
from novapanda.vdc import now_iso


@dataclass
class VerificationCredential:
    credential_id: str
    exchange_id: str
    vdc_id: str
    result_hash: str
    rule_id: str
    verifier_agent_id: str
    backend_id: str
    passed: bool
    reason: str
    checks: list[dict]
    attestation: Optional[dict]
    issued_at: str
    signature: str = ""

    def signing_payload(self) -> dict:
        return {
            "attestation": self.attestation,
            "backend_id": self.backend_id,
            "checks": self.checks,
            "credential_id": self.credential_id,
            "exchange_id": self.exchange_id,
            "issued_at": self.issued_at,
            "passed": self.passed,
            "reason": self.reason,
            "result_hash": self.result_hash,
            "rule_id": self.rule_id,
            "vdc_id": self.vdc_id,
            "verifier_agent_id": self.verifier_agent_id,
        }

    def to_dict(self) -> dict:
        return asdict(self)


def build_and_sign_credential(
    identity: Identity,
    *,
    exchange_id: str,
    vdc_id: str,
    result_hash: str,
    rule_id: str,
    backend_id: str,
    passed: bool,
    reason: str,
    checks: list[dict],
    attestation: Optional[dict] = None,
    credential_id: Optional[str] = None,
) -> VerificationCredential:
    from novapanda.vdc import new_id

    cred = VerificationCredential(
        credential_id=credential_id or new_id(),
        exchange_id=exchange_id,
        vdc_id=vdc_id,
        result_hash=result_hash,
        rule_id=rule_id,
        verifier_agent_id=identity.agent_id,
        backend_id=backend_id,
        passed=passed,
        reason=reason,
        checks=checks,
        attestation=attestation,
        issued_at=now_iso(),
    )
    sig = identity.sign(canonical_bytes(cred.signing_payload()))
    cred.signature = sig
    return cred


def verify_credential(cred: VerificationCredential | dict) -> bool:
    if isinstance(cred, dict):
        cred = VerificationCredential(**{k: cred[k] for k in VerificationCredential.__dataclass_fields__})
    payload = cred.signing_payload()
    return verify_sig(cred.verifier_agent_id, cred.signature, canonical_bytes(payload))
