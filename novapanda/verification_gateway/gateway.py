"""Verification Gateway：接收 Proof → 跑后端 → 签发 Credential。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from novapanda.identity import Identity

from .backends import BackendResult, LocalSchemaBackend, VerificationBackend
from .credential import VerificationCredential, build_and_sign_credential


@dataclass
class ProofSubmission:
    """Agent B 提交的任务成果。"""

    exchange_id: str
    vdc_id: str
    result_hash: str
    rule_id: str
    deliverable: Any
    rule: Optional[dict] = None
    proof_meta: Optional[dict] = None


@dataclass
class VerifyOutcome:
    passed: bool
    backend: BackendResult
    credential: Optional[VerificationCredential] = None
    error: Optional[str] = None


@dataclass
class VerificationGateway:
    """轻量链下验证网关。

    生产部署建议：
    - 多实例 + 不同 backend（schema / docker / TEE）做 quorum；
    - 网关密钥与节点运营密钥分离；
    - 超时由编排层 ``sweep_verify_deadline`` 触发退款意图。
    """

    identity: Identity
    backend: VerificationBackend = field(default_factory=LocalSchemaBackend)
    # 验证关口自身 SLA（秒）；0 = 不限
    verify_sla_seconds: int = 300
    _jobs: dict[str, dict] = field(default_factory=dict)

    def submit_proof(self, submission: ProofSubmission, *, now_ts: Optional[float] = None) -> VerifyOutcome:
        """同步验收路径（原型）。异步队列可把本方法拆成 enqueue + worker。"""
        import time

        started = now_ts if now_ts is not None else time.time()
        self._jobs[submission.exchange_id] = {
            "status": "verifying",
            "started_at": started,
            "vdc_id": submission.vdc_id,
        }
        try:
            backend_result = self.backend.run(
                deliverable=submission.deliverable,
                rule=submission.rule,
                result_hash=submission.result_hash,
                proof_meta=submission.proof_meta,
            )
        except Exception as exc:  # noqa: BLE001 — 网关必须吞掉后端崩溃并记失败
            self._jobs[submission.exchange_id]["status"] = "failed"
            return VerifyOutcome(
                passed=False,
                backend=BackendResult(
                    passed=False,
                    backend_id=getattr(self.backend, "backend_id", "unknown"),
                    reason=f"backend error: {exc}",
                    checks=[],
                ),
                error=str(exc),
            )

        cred: Optional[VerificationCredential] = None
        if backend_result.passed:
            cred = build_and_sign_credential(
                self.identity,
                exchange_id=submission.exchange_id,
                vdc_id=submission.vdc_id,
                result_hash=submission.result_hash,
                rule_id=submission.rule_id,
                backend_id=backend_result.backend_id,
                passed=True,
                reason=backend_result.reason,
                checks=backend_result.checks,
                attestation=backend_result.attestation,
            )
            self._jobs[submission.exchange_id]["status"] = "passed"
            self._jobs[submission.exchange_id]["credential_id"] = cred.credential_id
        else:
            self._jobs[submission.exchange_id]["status"] = "rejected"

        return VerifyOutcome(passed=backend_result.passed, backend=backend_result, credential=cred)

    def job_status(self, exchange_id: str) -> Optional[dict]:
        return self._jobs.get(exchange_id)

    def is_verify_overdue(self, exchange_id: str, *, now_ts: float) -> bool:
        job = self._jobs.get(exchange_id)
        if not job or self.verify_sla_seconds <= 0:
            return False
        if job.get("status") != "verifying":
            return False
        return (now_ts - float(job["started_at"])) > self.verify_sla_seconds
