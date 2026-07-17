"""可插拔验收后端：本地 Schema → Docker 沙箱 → TEE 证明。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from novapanda.verifier import SchemaVerifier


@dataclass(frozen=True)
class BackendResult:
    passed: bool
    backend_id: str
    reason: str
    checks: list[dict]
    # 扩展点：TEE 报价、容器镜像 digest、重放引用等
    attestation: Optional[dict] = None


class VerificationBackend(Protocol):
    backend_id: str

    def run(
        self,
        *,
        deliverable: Any,
        rule: Optional[dict],
        result_hash: str,
        proof_meta: Optional[dict] = None,
    ) -> BackendResult: ...


class LocalSchemaBackend:
    """轻量默认：JSON Schema / 物理交付校验（确定性、可离线复算）。"""

    backend_id = "backend:local-schema/v1"

    def __init__(self) -> None:
        self._verifier = SchemaVerifier()

    def run(
        self,
        *,
        deliverable: Any,
        rule: Optional[dict],
        result_hash: str,
        proof_meta: Optional[dict] = None,
    ) -> BackendResult:
        # 先核对 content-addressed hash，防止「提交物与声明哈希不一致」
        expected = _hash_deliverable(deliverable)
        if result_hash and result_hash != expected:
            return BackendResult(
                passed=False,
                backend_id=self.backend_id,
                reason=f"result_hash mismatch: declared={result_hash} computed={expected}",
                checks=[{"field": "result_hash", "msg": "mismatch"}],
            )
        vr = self._verifier.verify(deliverable, rule)
        return BackendResult(
            passed=bool(vr["passed"]),
            backend_id=self.backend_id,
            reason=str(vr.get("reason") or ""),
            checks=list(vr.get("checks") or []),
        )


class DockerSandboxBackend:
    """Docker 隔离验收桩：生产中应 `docker run --network=none` 执行 rule.verifier_image。

    原型不拉真实容器；用本地 Schema 结果 + 固定镜像 digest 占位，
    保证接口与未来硬件扩展路径一致。
    """

    backend_id = "backend:docker-sandbox/v1"

    def __init__(self, *, image_digest: str = "sha256:prototype-verifier-image") -> None:
        self.image_digest = image_digest
        self._local = LocalSchemaBackend()

    def run(
        self,
        *,
        deliverable: Any,
        rule: Optional[dict],
        result_hash: str,
        proof_meta: Optional[dict] = None,
    ) -> BackendResult:
        inner = self._local.run(
            deliverable=deliverable,
            rule=rule,
            result_hash=result_hash,
            proof_meta=proof_meta,
        )
        attestation = {
            "isolation": "docker",
            "network": "none",
            "image_digest": (rule or {}).get("verifier_image_digest") or self.image_digest,
            "note": "prototype: schema run inside logical sandbox envelope",
        }
        return BackendResult(
            passed=inner.passed,
            backend_id=self.backend_id,
            reason=inner.reason,
            checks=inner.checks,
            attestation=attestation,
        )


class TEEAttestedBackend:
    """TEE（如 AWS Nitro Enclaves）验收桩。

    生产路径：
    1. 把 (deliverable, rule) 送入 enclave；
    2. enclave 内跑确定性 verifier；
    3. 返回 NSM attestation document（PCR0=verifier 测量值）。

    原型用 HMAC 风格 stub attestation，便于联调编排层。
    """

    backend_id = "backend:tee-nitro/v1"

    def __init__(self, *, pcr0: str = "pcr0:prototype-verifier-v1") -> None:
        self.pcr0 = pcr0
        self._local = LocalSchemaBackend()

    def run(
        self,
        *,
        deliverable: Any,
        rule: Optional[dict],
        result_hash: str,
        proof_meta: Optional[dict] = None,
    ) -> BackendResult:
        inner = self._local.run(
            deliverable=deliverable,
            rule=rule,
            result_hash=result_hash,
            proof_meta=proof_meta,
        )
        measurement = hashlib.sha256(
            json.dumps(
                {"result_hash": result_hash, "passed": inner.passed, "pcr0": self.pcr0},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        attestation = {
            "isolation": "tee",
            "platform": "aws-nitro-enclaves",
            "pcr0": self.pcr0,
            "enclave_measurement": measurement,
            "note": "prototype: replace with real NSM attestation document",
        }
        return BackendResult(
            passed=inner.passed,
            backend_id=self.backend_id,
            reason=inner.reason,
            checks=inner.checks,
            attestation=attestation,
        )


def _hash_deliverable(deliverable: Any) -> str:
    from novapanda.hashing import result_hash, result_hash_of_json

    if isinstance(deliverable, (bytes, bytearray)):
        return result_hash(bytes(deliverable))
    return result_hash_of_json(deliverable)
