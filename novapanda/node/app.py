"""NovaPanda 参考节点（v0，HTTP/JSON）。

这是「身体/可运营」层：人人可自建、可被替代。它只做编排与校验，
从不持有任何 agent 私钥；真理（VDC/签名/信誉）均可脱离本节点独立复验。
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..auth import NonceStore, verify_request
from ..exchange import ExchangeEngine, ExchangeError, NotFoundError
from ..identity import Identity
from ..registry import OntologyRegistry, RuleRegistry, load_or_seed_registries
from ..reputation import ReputationLog
from ..settlement import MockSettlement, SettlementError
from ..state_machine import StateError
from ..store import InMemoryStore
from ..key_history import validate_key_history
from ..terms import verify_contract_ack
from ..v2.federation import FederationV2NotEnabledError
from ..v2.witness import WitnessV2NotEnabledError
from ..verifier import SchemaVerifier, make_verifier
from ..reputation_gate import check_reputation_gate
from ..v1.did import did_to_agent_id, is_novapanda_did, normalize_party_ref
from ..v1.did_registry import DidRegistry


class AuthError(Exception):
    def __init__(self, status: int, code: str, msg: str) -> None:
        self.status = status
        self.code = code
        self.msg = msg


class ProposeBody(BaseModel):
    client: str
    provider: str
    resource_type: str
    quantity: int
    rule_id: str
    price: dict
    idempotency_key: str
    timeouts: Optional[dict] = None
    provider_did: Optional[str] = None


class EscrowBody(BaseModel):
    amount: int
    currency: str


class DeliverBody(BaseModel):
    vdc: dict
    deliverable: Any


class DeliverableVerifyBody(BaseModel):
    deliverable: Any


class ConfirmBody(BaseModel):
    vdc: dict


class ContractBody(BaseModel):
    signature: str
    party_did: Optional[str] = None


class DisputeBody(BaseModel):
    reason: str


class ResolveBody(BaseModel):
    outcome: str
    note: Optional[str] = None


class WitnessValidateBody(BaseModel):
    attestation: dict


class StakeValidateBody(BaseModel):
    stake: dict


class StakeSlashBody(BaseModel):
    stake: dict
    reason: str
    slashed_by: str


class ReputationBundleBody(BaseModel):
    bundle: dict


class ReputationAggregateBody(BaseModel):
    bundles: list[dict]
    weights: Optional[dict[str, float]] = None


class PhysicalValidateBody(BaseModel):
    resource_type: str
    deliverable: Any


class StakeLockBody(BaseModel):
    agent_id: str
    amount: int
    currency: str
    purpose: str
    exchange_id: Optional[str] = None
    vdc_id: Optional[str] = None


class KeyHistoryBody(BaseModel):
    key_history: dict


class DidDocumentBody(BaseModel):
    document: dict


class CborEncodeBody(BaseModel):
    value: Any


class Iso15118CompleteBody(BaseModel):
    kwh_delivered: str


class Iso15118DeliverableBody(BaseModel):
    session_id: str
    kwh_delivered: str


def create_app(
    node_identity: Optional[Identity] = None, *, seed: bool = True, store=None,
    auth: bool = True, reputation_store=None, settlement=None,
    blob_store=None,
    arbitrator_id: Optional[str] = None,
    ontology: Optional[OntologyRegistry] = None,
    rules: Optional[RuleRegistry] = None,
    ontology_path=None,
    rules_path=None,
    default_timeouts: Optional[dict] = None,
    verifier=None,
    reputation_weights: Optional[dict] = None,
    reputation_min_score: Optional[float] = None,
    reputation_gate_strict: bool = False,
    witness_require_stake: bool = False,
    rep_witness_bonus_per_stake: float = 0.05,
    rep_witness_bonus_cap: float = 0.25,
) -> FastAPI:
    node_identity = node_identity or Identity.generate()
    store = store if store is not None else InMemoryStore()
    settlement = settlement or MockSettlement()
    if ontology is None or rules is None:
        if seed:
            loaded_onto, loaded_rules = load_or_seed_registries(
                store, ontology_path, rules_path,
            )
            ontology = ontology or loaded_onto
            rules = rules or loaded_rules
        else:
            ontology = ontology or OntologyRegistry()
            rules = rules or RuleRegistry()

    reputation = ReputationLog(node_identity, store=reputation_store)
    v = verifier if verifier is not None else SchemaVerifier()
    from ..v2 import stake as stake_mod

    if hasattr(store, "stake_upsert"):
        stake_mod.bind_stake_store(store)
    else:
        stake_mod.bind_stake_store(None)
    engine = ExchangeEngine(
        settlement, verifier=v, reputation=reputation,
        store=store, blob_store=blob_store,
    )

    if hasattr(store, "nonce_check_and_add"):
        nonce_store = store
    else:
        nonce_store = NonceStore()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine.recover()
        yield

    app = FastAPI(title="NovaPanda Node", version="0.0.1", lifespan=lifespan)
    app.state.engine = engine
    app.state.rules = rules
    app.state.ontology = ontology
    app.state.reputation = reputation
    app.state.node_id = node_identity.agent_id
    app.state.auth_enabled = auth
    app.state.arbitrator_id = arbitrator_id
    from ..config import DEFAULT_TIMEOUTS

    app.state.default_timeouts = default_timeouts or dict(DEFAULT_TIMEOUTS)
    app.state.reputation_weights = reputation_weights or {}
    app.state.reputation_min_score = reputation_min_score
    app.state.reputation_gate_strict = reputation_gate_strict
    app.state.witness_require_stake = witness_require_stake
    app.state.rep_witness_bonus_per_stake = rep_witness_bonus_per_stake
    app.state.rep_witness_bonus_cap = rep_witness_bonus_cap
    app.state.did_registry = DidRegistry()
    app.state.admin_token = os.environ.get("NOVAPANDA_ADMIN_TOKEN")

    def _normalize_party(ref: str) -> str:
        try:
            return normalize_party_ref(ref, app.state.did_registry)
        except ValueError as exc:
            raise AuthError(400, "E_DID_INVALID", str(exc)) from exc

    def _resolve_agent_id(agent_id: str, did: Optional[str], field_name: str) -> None:
        if not did:
            return
        try:
            resolved = did_to_agent_id(did)
        except ValueError as exc:
            raise AuthError(400, "E_DID_INVALID", str(exc)) from exc
        normalized = _normalize_party(agent_id)
        if resolved != normalized:
            raise AuthError(400, "E_DID_MISMATCH", f"{field_name} 与 did 不一致")

    def _gate_provider(provider_id: str) -> None:
        from ..v2 import stake as stake_mod

        witness_stakes = 0
        try:
            witness_stakes = stake_mod.count_locked_stakes(agent_id=provider_id)
        except Exception:
            witness_stakes = 0
        gate = check_reputation_gate(
            reputation,
            provider_id,
            min_score=app.state.reputation_min_score,
            weights=app.state.reputation_weights,
            strict_no_history=app.state.reputation_gate_strict,
            witness_stake_count=witness_stakes,
            witness_bonus_per_stake=app.state.rep_witness_bonus_per_stake,
            witness_bonus_cap=app.state.rep_witness_bonus_cap,
        )
        if not gate["allowed"]:
            raise AuthError(403, "E_REPUTATION_LOW", gate["reason"])

    async def authn(request: Request) -> Optional[str]:
        """认证：返回调用者 agent_id；未启用鉴权时返回 None。"""
        if not auth:
            return None
        aid = request.headers.get("X-Agent-Id")
        nonce = request.headers.get("X-Nonce")
        sig = request.headers.get("X-Signature")
        if not (aid and nonce and sig):
            raise AuthError(401, "E_AUTH_MISSING", "缺少 X-Agent-Id/X-Nonce/X-Signature")
        body = await request.body()
        if not verify_request(aid, sig, request.method, request.url.path, nonce, body):
            raise AuthError(401, "E_SIG_INVALID", "请求签名验证失败")
        ok = (
            nonce_store.nonce_check_and_add(aid, nonce)
            if hasattr(nonce_store, "nonce_check_and_add")
            else nonce_store.check_and_add(aid, nonce)
        )
        if not ok:
            raise AuthError(409, "E_REPLAY", "nonce 已被使用（重放）")
        return aid

    def authz(caller: Optional[str], allowed: set[str]) -> None:
        """授权：未启用鉴权时跳过；否则 caller 必须属于 allowed。"""
        if caller is None:
            return
        if caller not in allowed:
            raise AuthError(403, "E_FORBIDDEN", "调用者无权执行该操作")

    def _ex(exchange_id: str) -> dict:
        return asdict(engine.get(exchange_id))

    def _err(status: int, code: str, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status, content={"code": code, "msg": str(exc)})

    @app.exception_handler(AuthError)
    async def _auth_err(_: Request, exc: AuthError):
        return JSONResponse(status_code=exc.status, content={"code": exc.code, "msg": exc.msg})

    @app.exception_handler(StateError)
    async def _state_err(_: Request, exc: StateError):
        return _err(409, "E_STATE_INVALID", exc)

    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError):
        return _err(404, "E_NOT_FOUND", exc)

    @app.exception_handler(SettlementError)
    async def _settle_err(_: Request, exc: SettlementError):
        return _err(402, "E_SETTLEMENT_FAILED", exc)

    @app.exception_handler(ExchangeError)
    async def _exchange_err(_: Request, exc: ExchangeError):
        return _err(400, "E_INVALID", exc)

    @app.get("/.well-known/novapanda.json")
    def manifest():
        return {
            "protocol": "novapanda",
            "version": "0.0.1",
            "node_id": app.state.node_id,
            "endpoints": ["/exchanges", "/vdc/{id}", "/reputation/{agent_id}", "/registry/rules"],
            "resource_types": [t["type_id"] for t in ontology.list()],
        }

    def _parties(exchange_id: str) -> set[str]:
        ex = engine.get(exchange_id)
        return {ex.client, ex.provider}

    @app.post("/exchanges", status_code=201)
    def propose(body: ProposeBody, caller: Optional[str] = Depends(authn)):
        client_id = _normalize_party(body.client)
        provider_id = _normalize_party(body.provider)
        authz(caller, {client_id})  # 只有 client 本人可发起
        _resolve_agent_id(provider_id, body.provider_did, "provider")
        _gate_provider(provider_id)
        if not ontology.get(body.resource_type):
            raise HTTPException(400, {"code": "E_TYPE_UNKNOWN", "msg": body.resource_type})
        if not rules.get(body.rule_id):
            raise HTTPException(400, {"code": "E_RULE_UNKNOWN", "msg": body.rule_id})
        ex = engine.propose(
            client=client_id, provider=provider_id,
            resource_type=body.resource_type, quantity=body.quantity,
            rule_id=body.rule_id, price=body.price,
            idempotency_key=body.idempotency_key,
            timeouts=body.timeouts or app.state.default_timeouts,
        )
        return asdict(ex)

    @app.get("/exchanges/{exchange_id}")
    def get_exchange(exchange_id: str):
        return _ex(exchange_id)

    def _resolve_contract_party(exchange_id: str, signature: str,
                                caller: Optional[str]) -> str:
        ex = engine.get(exchange_id)
        if caller is not None:
            return caller
        for candidate in (ex.client, ex.provider):
            if verify_contract_ack(candidate, signature, terms_hash=ex.terms_hash,
                                   exchange_id=exchange_id):
                return candidate
        raise ExchangeError("contract 签名无效")

    @app.post("/exchanges/{exchange_id}/contract")
    def contract(exchange_id: str, body: ContractBody, caller: Optional[str] = Depends(authn)):
        ex = engine.get(exchange_id)
        if body.party_did:
            party = _normalize_party(body.party_did)
            if party not in (ex.client, ex.provider):
                raise AuthError(403, "E_FORBIDDEN", "party_did 不是交换方")
            if not verify_contract_ack(
                party, body.signature, terms_hash=ex.terms_hash, exchange_id=exchange_id,
            ):
                raise AuthError(401, "E_SIG_INVALID", "contract 签名与 party_did 不匹配")
        else:
            authz(caller, _parties(exchange_id))
            party = _resolve_contract_party(exchange_id, body.signature, caller)
            _resolve_agent_id(party, body.party_did, "party")
        return asdict(engine.contract(exchange_id, party=party, signature=body.signature))

    @app.post("/exchanges/{exchange_id}/escrow")
    def escrow(exchange_id: str, body: EscrowBody, caller: Optional[str] = Depends(authn)):
        authz(caller, {engine.get(exchange_id).client})
        _gate_provider(engine.get(exchange_id).provider)
        return asdict(engine.escrow(exchange_id, amount=body.amount, currency=body.currency))

    @app.post("/exchanges/{exchange_id}/deliver")
    def deliver(exchange_id: str, body: DeliverBody, caller: Optional[str] = Depends(authn)):
        authz(caller, {engine.get(exchange_id).provider})
        return asdict(engine.ingest_delivery(
            exchange_id, vdc=body.vdc, deliverable=body.deliverable
        ))

    @app.post("/exchanges/{exchange_id}/verify")
    def verify(exchange_id: str, caller: Optional[str] = Depends(authn)):
        authz(caller, _parties(exchange_id))
        ex = engine.get(exchange_id)
        rule = rules.get(ex.rule_id)
        return asdict(engine.verify(exchange_id, rule=rule))

    @app.post("/exchanges/{exchange_id}/confirm")
    def confirm(exchange_id: str, body: ConfirmBody, caller: Optional[str] = Depends(authn)):
        authz(caller, {engine.get(exchange_id).client})
        return asdict(engine.ingest_confirmation(exchange_id, vdc=body.vdc))

    @app.post("/exchanges/{exchange_id}/dispute")
    def dispute(exchange_id: str, body: DisputeBody, caller: Optional[str] = Depends(authn)):
        parties = _parties(exchange_id)
        authz(caller, parties)
        by = caller if caller is not None else next(iter(parties))
        return asdict(engine.dispute(exchange_id, by=by, reason=body.reason))

    @app.post("/exchanges/{exchange_id}/resolve")
    def resolve(exchange_id: str, body: ResolveBody, caller: Optional[str] = Depends(authn)):
        if app.state.arbitrator_id:
            if caller is None:
                raise AuthError(403, "E_FORBIDDEN", "争议裁决需仲裁者身份")
            authz(caller, {app.state.arbitrator_id})
        else:
            authz(caller, _parties(exchange_id))
        return asdict(engine.resolve(exchange_id, outcome=body.outcome,
                                     resolver=caller, note=body.note))

    @app.get("/exchanges/{exchange_id}/deliverable")
    def get_deliverable(exchange_id: str, caller: Optional[str] = Depends(authn)):
        authz(caller, _parties(exchange_id))
        try:
            return engine.get_deliverable(exchange_id)
        except NotFoundError as e:
            raise HTTPException(404, {"code": "E_NOT_FOUND", "msg": str(e)}) from e
        except KeyError as e:
            raise HTTPException(404, {"code": "E_NOT_FOUND", "msg": str(e)}) from e

    @app.post("/exchanges/{exchange_id}/deliverable/verify")
    def verify_deliverable_hash(exchange_id: str, body: DeliverableVerifyBody):
        """公开 hash 验证：任何人可提交 candidate deliverable，无需读取存储 blob。"""
        try:
            return engine.verify_deliverable_candidate(exchange_id, body.deliverable)
        except NotFoundError as e:
            raise HTTPException(404, {"code": "E_NOT_FOUND", "msg": str(e)}) from e
        except ExchangeError as e:
            raise HTTPException(400, {"code": "E_INVALID", "msg": str(e)}) from e

    @app.post("/exchanges/{exchange_id}/cancel")
    def cancel(exchange_id: str, caller: Optional[str] = Depends(authn)):
        authz(caller, _parties(exchange_id))
        return asdict(engine.cancel(exchange_id))

    @app.post("/exchanges/{exchange_id}/expire")
    def expire(exchange_id: str, caller: Optional[str] = Depends(authn)):
        authz(caller, _parties(exchange_id))
        return asdict(engine.expire(exchange_id))

    @app.get("/exchanges/{exchange_id}/export")
    def export_exchange(exchange_id: str, caller: Optional[str] = Depends(authn)):
        parties = _parties(exchange_id)
        include_deliverable = caller in parties if caller is not None else False
        if auth and caller is None:
            include_deliverable = False
        try:
            return engine.export_exchange(
                exchange_id, include_deliverable=include_deliverable
            )
        except NotFoundError as e:
            raise HTTPException(404, {"code": "E_NOT_FOUND", "msg": str(e)}) from e

    @app.get("/reputation/export")
    def export_reputation(agent_id: Optional[str] = None):
        """导出可携带信誉 bundle（公开只读；链本身可独立复验）。"""
        return app.state.reputation.export_bundle(agent_id)

    @app.post("/v2/reputation/validate")
    def validate_reputation_bundle(body: ReputationBundleBody):
        return app.state.reputation.validate_external_bundle(body.bundle)

    @app.post("/v2/reputation/import")
    def import_reputation_bundle(body: ReputationBundleBody):
        try:
            imported = app.state.reputation.import_external_bundle(body.bundle)
            return {"imported_count": len(imported)}
        except FederationV2NotEnabledError as exc:
            return JSONResponse(
                status_code=501,
                content={"code": "E_NOT_IMPLEMENTED", "msg": str(exc)},
            )
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_INVALID", "msg": str(exc)}) from exc

    @app.post("/v2/reputation/aggregate")
    def aggregate_reputation(body: ReputationAggregateBody):
        from ..v2.reputation_agg import aggregate_reputation_bundles

        return aggregate_reputation_bundles(body.bundles, weights=body.weights)

    @app.post("/v3/physical/validate")
    def validate_physical_deliverable(body: PhysicalValidateBody):
        from ..v3.physical import validate_physical_deliverable

        errors = validate_physical_deliverable(body.resource_type, body.deliverable)
        return {"valid": len(errors) == 0, "errors": errors}

    @app.post("/v2/identity/key-history/validate")
    def validate_key_history_endpoint(body: KeyHistoryBody):
        errors = validate_key_history(body.key_history)
        return {"valid": len(errors) == 0, "errors": errors}

    @app.get("/vdc/{vdc_id}")
    def get_vdc(vdc_id: str):
        vdc = engine.find_vdc(vdc_id)
        if vdc is None:
            raise HTTPException(404, {"code": "E_NOT_FOUND", "msg": vdc_id})
        return vdc

    @app.post("/v2/witness/validate")
    def validate_witness_v2(body: WitnessValidateBody):
        """v2 占位：仅校验见证声明结构/签名，不写入存储。"""
        return engine.validate_witness_v2(body.attestation)

    @app.post("/exchanges/{exchange_id}/v2/witness/attach")
    def attach_witness_v2(exchange_id: str, body: WitnessValidateBody,
                          caller: Optional[str] = Depends(authn)):
        authz(caller, _parties(exchange_id))
        try:
            return asdict(engine.attach_witness_v2(
                exchange_id,
                body.attestation,
                require_stake=app.state.witness_require_stake,
            ))
        except ExchangeError as exc:
            raise HTTPException(400, {"code": "E_INVALID", "msg": str(exc)}) from exc
        except WitnessV2NotEnabledError as exc:
            return JSONResponse(
                status_code=501,
                content={"code": "E_NOT_IMPLEMENTED", "msg": str(exc)},
            )

    @app.post("/v2/stake/validate")
    def validate_stake_v2(body: StakeValidateBody):
        return engine.validate_stake_v2(body.stake)

    @app.post("/v2/stake/lock")
    def lock_stake_v2(body: StakeLockBody):
        try:
            return engine.lock_stake_v2(
                agent_id=body.agent_id,
                amount=body.amount,
                currency=body.currency,
                purpose=body.purpose,
                exchange_id=body.exchange_id,
                vdc_id=body.vdc_id,
            )
        except WitnessV2NotEnabledError as exc:
            return JSONResponse(
                status_code=501,
                content={"code": "E_NOT_IMPLEMENTED", "msg": str(exc)},
            )
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_INVALID", "msg": str(exc)}) from exc

    @app.post("/v2/stake/release")
    def release_stake_v2(stake_id: str):
        try:
            from ..v2.stake import release_stake
            return release_stake(stake_id)
        except WitnessV2NotEnabledError as exc:
            return JSONResponse(
                status_code=501,
                content={"code": "E_NOT_IMPLEMENTED", "msg": str(exc)},
            )
        except KeyError as exc:
            raise HTTPException(404, {"code": "E_NOT_FOUND", "msg": str(exc)}) from exc
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_INVALID", "msg": str(exc)}) from exc

    @app.post("/v2/stake/slash")
    def slash_stake_v2(body: StakeSlashBody):
        try:
            return engine.slash_stake_v2(
                body.stake, reason=body.reason, slashed_by=body.slashed_by
            )
        except WitnessV2NotEnabledError as exc:
            return JSONResponse(
                status_code=501,
                content={"code": "E_NOT_IMPLEMENTED", "msg": str(exc)},
            )

    @app.post("/v1/did/register")
    def register_did(body: DidDocumentBody):
        try:
            return app.state.did_registry.register(body.document)
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_INVALID", "msg": str(exc)}) from exc

    @app.post("/v1/did/validate")
    def validate_did_document(body: DidDocumentBody):
        from ..v1.did import validate_did_document
        errors = validate_did_document(body.document)
        return {"valid": len(errors) == 0, "errors": errors}

    @app.get("/v1/did/resolve/{did:path}")
    def resolve_did(did: str):
        if not is_novapanda_did(did):
            raise HTTPException(400, {"code": "E_INVALID", "msg": "非 novapanda DID"})
        try:
            return app.state.did_registry.resolve(did)
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_INVALID", "msg": str(exc)}) from exc

    @app.post("/v3/iso15118/sessions")
    def iso15118_create_session(evse_id: str = "EVSE-001"):
        from ..v3.iso15118_adapter import create_session
        return create_session(evse_id=evse_id)

    @app.post("/v3/iso15118/sessions/{session_id}/complete")
    def iso15118_complete_session(session_id: str, body: Iso15118CompleteBody):
        from ..v3.iso15118_adapter import build_energy_deliverable
        try:
            return build_energy_deliverable(session_id, kwh_delivered=body.kwh_delivered)
        except KeyError as exc:
            raise HTTPException(404, {"code": "E_NOT_FOUND", "msg": str(exc)}) from exc
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_INVALID", "msg": str(exc)}) from exc

    @app.get("/v3/iso15118/adapter")
    def iso15118_adapter_info():
        from ..v3.iso15118_adapter import adapter_info
        return adapter_info()

    @app.post("/v3/iso15118/deliverable")
    def iso15118_build_deliverable(body: Iso15118DeliverableBody):
        from ..v3.iso15118_adapter import build_energy_deliverable
        try:
            return build_energy_deliverable(body.session_id, kwh_delivered=body.kwh_delivered)
        except KeyError as exc:
            raise HTTPException(404, {"code": "E_NOT_FOUND", "msg": str(exc)}) from exc
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_INVALID", "msg": str(exc)}) from exc

    @app.post("/v1/cbor/canonical")
    def cbor_canonical(body: CborEncodeBody):
        from ..v1.cbor_codec import canonical_cbor_bytes, cbor_available
        if not cbor_available():
            return JSONResponse(
                status_code=501,
                content={"code": "E_NOT_IMPLEMENTED", "msg": "cbor2 未安装"},
            )
        import base64
        raw = canonical_cbor_bytes(body.value)
        return {"encoding": "cbor", "canonical": True, "bytes_b64": base64.b64encode(raw).decode("ascii")}

    @app.get("/reputation/{agent_id}")
    def reputation_of(agent_id: str, since: int = 0):
        return {"node_id": app.state.node_id, "entries": app.state.reputation.entries(agent_id, since)}

    @app.get("/v2/reputation/{agent_id}/score")
    def reputation_score(agent_id: str, weights: Optional[str] = None):
        """本地账本加权 score（含 mirror 导入条目）。"""
        import json

        parsed: dict[str, float] = dict(app.state.reputation_weights or {})
        if weights:
            parsed.update(json.loads(weights))
        return app.state.reputation.weighted_score(agent_id, weights=parsed)

    @app.get("/health")
    def health():
        """负载均衡 / 容器探活。"""
        return {"status": "ok", "service": "novapanda-node"}

    @app.post("/admin/sweep")
    def sweep(request: Request):
        """超时清扫：由外部调度器周期调用（真实部署可挂 cron 或后台任务）。"""
        token = app.state.admin_token
        if token:
            header = request.headers.get("X-Admin-Token")
            if header != token:
                raise AuthError(401, "E_ADMIN_UNAUTHORIZED", "invalid or missing X-Admin-Token")
        expired = engine.sweep()
        return {"expired": [ex.exchange_id for ex in expired]}

    @app.get("/registry/rules")
    def list_rules():
        return rules.list()

    @app.get("/registry/types")
    def list_types():
        return ontology.list()

    return app


def create_app_from_config(cfg=None) -> FastAPI:
    """从 NodeConfig / 环境变量创建生产节点（uvicorn --factory 入口）。"""
    from ..config import NodeConfig

    cfg = cfg or NodeConfig.from_env()
    cfg.apply_feature_flags()
    store = cfg.make_store()
    return create_app(
        store=store,
        auth=cfg.auth,
        reputation_store=cfg.make_reputation_store(),
        settlement=cfg.make_settlement(),
        blob_store=cfg.make_blob_store(store),
        arbitrator_id=cfg.arbitrator_id,
        ontology_path=cfg.ontology_path,
        rules_path=cfg.rules_path,
        default_timeouts=cfg.default_timeouts,
        verifier=cfg.make_verifier(),
        reputation_weights=cfg.reputation_weights,
        reputation_min_score=cfg.reputation_min_score,
        reputation_gate_strict=cfg.reputation_gate_strict,
        witness_require_stake=cfg.witness_require_stake,
        rep_witness_bonus_per_stake=cfg.rep_witness_bonus_per_stake,
        rep_witness_bonus_cap=cfg.rep_witness_bonus_cap,
        seed=True,
    )
