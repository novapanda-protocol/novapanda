"""物理交付凭证（PoD）+ 模拟 TPM 硬件签名验收后端。"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from novapanda.verification_gateway.backends import BackendResult, LocalSchemaBackend


def simulate_tpm_sign(device_id: str, payload: dict[str, Any], *, secret: str = "tpm-sim") -> str:
    """模拟 TPM quote：HMAC(device_id || canonical_json(payload)).

    生产应替换为真实 TPM / secure element；此处仅供 DePIN 演练。
    """
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    key = f"{secret}:{device_id}".encode()
    return "tpm:" + hmac.new(key, body.encode(), hashlib.sha256).hexdigest()


def verify_tpm_pod(
    *,
    device_id: str,
    payload: dict[str, Any],
    signature: str,
    secret: str = "tpm-sim",
) -> bool:
    expected = simulate_tpm_sign(device_id, payload, secret=secret)
    return hmac.compare_digest(expected, signature or "")


@dataclass
class HardwarePodBackend:
    """验收带硬件签名的物理交付（如充电 kWh、无人机航点完成）。

    先校验 TPM 签名，再委托 LocalSchemaBackend 做结构化字段校验。
    ``backend_id`` 标明物理路径，便于 VDC 凭证审计。
    """

    backend_id: str = "backend:hardware-pod-tpm/v1"
    tpm_secret: str = "tpm-sim"
    _schema: LocalSchemaBackend = field(default_factory=LocalSchemaBackend)

    def run(
        self,
        *,
        deliverable: Any,
        rule: Optional[dict],
        result_hash: str,
        proof_meta: Optional[dict] = None,
    ) -> BackendResult:
        meta = proof_meta or {}
        if not isinstance(deliverable, dict):
            return BackendResult(
                passed=False,
                backend_id=self.backend_id,
                reason="PoD deliverable must be an object",
                checks=[{"field": "deliverable", "msg": "not object"}],
            )
        device_id = str(meta.get("device_id") or deliverable.get("device_id") or "")
        sig = str(meta.get("tpm_signature") or deliverable.get("tpm_signature") or "")
        pod = deliverable.get("pod") if isinstance(deliverable.get("pod"), dict) else deliverable
        if not device_id or not sig:
            return BackendResult(
                passed=False,
                backend_id=self.backend_id,
                reason="missing device_id or tpm_signature",
                checks=[{"field": "tpm", "msg": "missing"}],
            )
        if not verify_tpm_pod(
            device_id=device_id, payload=pod, signature=sig, secret=self.tpm_secret
        ):
            return BackendResult(
                passed=False,
                backend_id=self.backend_id,
                reason="TPM signature invalid",
                checks=[{"field": "tpm_signature", "msg": "invalid"}],
                attestation={"device_id": device_id, "tpm_ok": False},
            )
        # 结构化字段（度数 / 航点等）走 schema
        schema_result = self._schema.run(
            deliverable=pod,
            rule=rule,
            result_hash="",  # PoD 以 TPM 为完整性根；schema 只校验形状
            proof_meta=meta,
        )
        if not schema_result.passed:
            return BackendResult(
                passed=False,
                backend_id=self.backend_id,
                reason=f"PoD schema failed: {schema_result.reason}",
                checks=schema_result.checks,
                attestation={"device_id": device_id, "tpm_ok": True},
            )
        return BackendResult(
            passed=True,
            backend_id=self.backend_id,
            reason="TPM PoD verified",
            checks=[{"field": "tpm", "msg": "ok"}, *schema_result.checks],
            attestation={
                "device_id": device_id,
                "tpm_ok": True,
                "kwh": pod.get("kwh") or pod.get("energy_kwh") or pod.get("energy_wh"),
                "unit": pod.get("unit"),
            },
        )
