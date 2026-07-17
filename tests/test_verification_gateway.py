"""VDC 自动验证+结算编排与 EVM rail 语义测试。"""

from __future__ import annotations

import time

from novapanda import state_machine as sm
from novapanda.exchange import ExchangeEngine
from novapanda.hashing import result_hash_of_json
from novapanda.identity import Identity
from novapanda.settlement import MockSettlement
from novapanda.verification_gateway import (
    AutoSettleOrchestrator,
    DockerSandboxBackend,
    LifecyclePhase,
    LocalSchemaBackend,
    TEEAttestedBackend,
    VerificationGateway,
)
from novapanda.verification_gateway.credential import verify_credential
from novapanda.verification_gateway.evm_rail import EvmSettlementRail, OnChainStatus
from novapanda.verification_gateway.orchestrator import phase_of
from novapanda.verifier import SchemaVerifier


RULE = {
    "schema": {
        "type": "object",
        "required": ["answer"],
        "properties": {"answer": {"type": "string", "minLength": 1}},
        "additionalProperties": False,
    }
}


def _orch(*, chain=None, sla=300, backend=None):
    client, provider, gw_id = Identity.generate(), Identity.generate(), Identity.generate()
    engine = ExchangeEngine(MockSettlement(), verifier=SchemaVerifier())
    gateway = VerificationGateway(
        identity=gw_id,
        backend=backend or LocalSchemaBackend(),
        verify_sla_seconds=sla,
    )
    if chain is not None:
        chain.trusted_verifiers.add(gw_id.agent_id)
    return AutoSettleOrchestrator(
        engine=engine,
        gateway=gateway,
        client=client,
        provider=provider,
        chain=chain,
    )


def test_happy_path_create_verify_settle_archive():
    orch = _orch()
    deliverable = {"answer": "42"}
    ex = orch.create(
        resource_type="compute.qa",
        quantity=1,
        rule_id="R-qa",
        price={"amount": 100, "currency": "USD"},
        idempotency_key="auto-1",
        timeouts={"deliver": 3600},
        rule=RULE,
    )
    assert ex.state == sm.ESCROWED
    assert phase_of(ex.state) == LifecyclePhase.CREATE

    ex, outcome = orch.fulfill_with_proof(ex.exchange_id, deliverable)
    assert outcome.passed
    assert outcome.credential is not None
    assert verify_credential(outcome.credential)
    assert ex.state == sm.VERIFIED
    assert outcome.credential.result_hash == result_hash_of_json(deliverable)

    ex = orch.settle(ex.exchange_id)
    assert ex.state == sm.SETTLED
    arch = orch.archive_record(ex.exchange_id)
    assert arch["phase"] == LifecyclePhase.ARCHIVE.value
    assert arch["vdc"]["state"] == sm.SETTLED
    assert arch["verification_credential"]["passed"] is True


def test_reject_bad_deliverable_refunds():
    orch = _orch()
    ex = orch.create(
        resource_type="compute.qa",
        quantity=1,
        rule_id="R-qa",
        price={"amount": 50, "currency": "USD"},
        idempotency_key="auto-bad",
        rule=RULE,
    )
    ex, outcome = orch.fulfill_with_proof(ex.exchange_id, {"answer": ""})
    assert not outcome.passed
    assert ex.state == sm.REJECTED
    assert orch.engine._settlement.status(ex.escrow_handle) == "refunded"


def test_docker_and_tee_backends_issue_attestation():
    for backend in (DockerSandboxBackend(), TEEAttestedBackend()):
        orch = _orch(backend=backend)
        ex = orch.create(
            resource_type="compute.qa",
            quantity=1,
            rule_id="R-qa",
            price={"amount": 10, "currency": "USD"},
            idempotency_key=f"bk-{backend.backend_id}",
            rule=RULE,
        )
        _, outcome = orch.fulfill_with_proof(ex.exchange_id, {"answer": "ok"})
        assert outcome.passed
        assert outcome.backend.attestation is not None
        assert outcome.credential.attestation is not None


def test_verify_gateway_sla_expire_refunds():
    orch = _orch(sla=10)
    ex = orch.create(
        resource_type="compute.qa",
        quantity=1,
        rule_id="R-qa",
        price={"amount": 20, "currency": "USD"},
        idempotency_key="sla-1",
        rule=RULE,
    )
    # 交付后卡住「验证中」：手动置 job 为 verifying 并回拨 started_at
    orch.engine.deliver(ex.exchange_id, orch.provider, {"answer": "x"})
    orch.gateway._jobs[ex.exchange_id] = {
        "status": "verifying",
        "started_at": time.time() - 100,
        "vdc_id": "x",
    }
    expired = orch.sweep_timeouts(now_ts=time.time())
    assert ex.exchange_id in expired
    assert orch.engine.get(ex.exchange_id).state == sm.EXPIRED_REFUNDED


def test_evm_rail_full_cycle_and_timeout():
    chain = EvmSettlementRail(arbitrator="arb:1")
    orch = _orch(chain=chain)
    ex = orch.create(
        resource_type="compute.qa",
        quantity=1,
        rule_id="R-qa",
        price={"amount": 77, "currency": "USD"},
        idempotency_key="evm-1",
        timeouts={"deliver": 100},
        rule=RULE,
    )
    on = chain.records[ex.exchange_id]
    assert on.status == OnChainStatus.FUNDED

    orch.fulfill_with_proof(ex.exchange_id, {"answer": "yes"})
    assert chain.records[ex.exchange_id].status == OnChainStatus.FULFILLED

    orch.settle(ex.exchange_id)
    assert chain.records[ex.exchange_id].status == OnChainStatus.SETTLED

    # 超时退款：新单卡在 FUNDED
    orch2 = _orch(chain=chain)
    ex2 = orch2.create(
        resource_type="compute.qa",
        quantity=1,
        rule_id="R-qa",
        price={"amount": 5, "currency": "USD"},
        idempotency_key="evm-to",
        timeouts={"deliver": 1},
        rule=RULE,
    )
    # 强制 deadline 已过
    chain.records[ex2.exchange_id].deliver_deadline_ts = 1.0
    chain.refund_if_timed_out(exchange_id=ex2.exchange_id, now_ts=99.0)
    assert chain.records[ex2.exchange_id].status == OnChainStatus.REFUNDED


def test_evm_dispute_resolve_refund():
    chain = EvmSettlementRail(arbitrator="arb:x")
    gw = Identity.generate()
    chain.trusted_verifiers.add(gw.agent_id)
    chain.create_vdc(
        exchange_id="e1",
        client="c",
        provider="p",
        amount=10,
        deliver_deadline_ts=None,
        verify_deadline_ts=None,
    )
    chain.fulfill_vdc_with_proof(
        exchange_id="e1",
        result_hash="sha256:ab",
        credential_id="cred1",
        verifier=gw.agent_id,
    )
    chain.initiate_dispute(exchange_id="e1", by="c", reason="quality")
    assert chain.records["e1"].status == OnChainStatus.DISPUTED
    chain.resolve_dispute(exchange_id="e1", pay_provider=False, by="arb:x")
    assert chain.records["e1"].status == OnChainStatus.REFUNDED


def test_result_hash_mismatch_fails_gateway():
    orch = _orch()
    from novapanda.verification_gateway.gateway import ProofSubmission

    ex = orch.create(
        resource_type="compute.qa",
        quantity=1,
        rule_id="R-qa",
        price={"amount": 1, "currency": "USD"},
        idempotency_key="hash-1",
        rule=RULE,
    )
    orch.engine.deliver(ex.exchange_id, orch.provider, {"answer": "ok"})
    bad = orch.gateway.submit_proof(
        ProofSubmission(
            exchange_id=ex.exchange_id,
            vdc_id="v",
            result_hash="sha256:deadbeef",
            rule_id="R-qa",
            deliverable={"answer": "ok"},
            rule=RULE,
        )
    )
    assert not bad.passed
    assert "mismatch" in bad.backend.reason
