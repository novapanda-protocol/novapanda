"""NovaPanda 参考节点（v0，HTTP/JSON）。

这是「身体/可运营」层：人人可自建、可被替代。它只做编排与校验，
从不持有任何 agent 私钥；真理（VDC/签名/信誉）均可脱离本节点独立复验。
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from dataclasses import asdict
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..auth import NonceStore, verify_request
from ..exchange import ExchangeEngine, ExchangeError, NotFoundError
from ..identity import Identity
from ..registry import OntologyRegistry, RuleRegistry, load_or_seed_registries
from ..reputation import ReputationLog
from ..privacy import hash_only_wrap, privacy_manifest_block, validate_privacy_tags
from ..settlement import MockSettlement, SandboxSettlement, SettlementError
from ..bundle import validate_bundle
from ..canonical import canonical_bytes
from ..hashing import sha256_hex
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
from .operators import OperatorRegistry
from .operator_persist import load_operator_registry
from .claim_mock import ClaimMockRegistry
from .claim_registry import ClaimRegistry, make_claim_store
from .body_ops import AuditLog, NotifyInbox, alert_snapshot
from .dashboard import (
    collect_node_profile,
    collect_scenarios,
    collect_status,
    exchange_public_detail,
    list_exchanges,
    render_console,
    render_exchange_detail,
    render_operator_claims,
    render_claim_detail,
    render_operator_reconcile,
    render_operator_disputes,
    render_operator_dashboard,
    render_operator_agents_ui,
    render_operator_exchanges,
    render_operator_settings,
    render_operator_help,
    render_operator_bundles,
    render_steward_certifications,
)
from .console_data import build_node_manifest, list_exchanges, settlement_rail_stressed
from .profile_gate import check_profile_honesty
from .reconcile import build_reconcile_export, export_csv, export_claim_csv
from .rb04 import scan_settlement_health
from .dispute_tickets import DisputeTicketRegistry
from .certifications import CertificationRegistry
from .operator_bindings import OperatorBindingRegistry
from ..delegate import DelegationRegistry
from ..lite import roundtrip as lite_roundtrip
from ..trace import (
    exchange_to_dict,
    from_headers,
    set_current_trace,
    trace_enabled,
)


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
    settlement: Optional[dict] = None
    correlation_id: Optional[str] = None


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


class OperatorRegisterBody(BaseModel):
    email: str
    display_name: str = ""
    password: str
    accept_terms: bool = False


class OperatorVerifyBody(BaseModel):
    email: str
    otp: str


class OperatorLoginBody(BaseModel):
    email: str
    password: str


class ClaimIssueBody(BaseModel):
    vdc_id: str
    amount: int = 0
    currency: str = "USD"
    holder: str = "demo"


class ClaimActionBody(BaseModel):
    claim_id: str
    exchange_id: Optional[str] = None


class ClaimAssignBody(BaseModel):
    claim_id: str
    to_agent_id: str
    nonce: str
    at: str
    signature: str


class ClaimRedeemBody(BaseModel):
    claim_id: str


class OperatorBindBody(BaseModel):
    agent_id: str
    signature: str
    issued_at: str
    label: str = ""


class OperatorUnbindBody(BaseModel):
    agent_id: str


class CertificationGrantBody(BaseModel):
    level: str
    applicant: dict
    implementation: dict
    profiles: list[str]
    cases_passed: list[str]
    manifest_sample: Optional[dict] = None
    rail_disclosure: Optional[dict] = None
    cert_id: Optional[str] = None
    expires_at: Optional[str] = None


class CertificationStatusBody(BaseModel):
    status: str


class BundleValidateBody(BaseModel):
    bundle: dict[str, Any]


class CanonicalBody(BaseModel):
    value: Any


class NotifyBody(BaseModel):
    kind: str = "info"
    title: str
    body: str = ""


class SettleSimBody(BaseModel):
    amount: int = 1
    currency: str = "USD"
    exchange_id: Optional[str] = None
    rail: Optional[str] = None


class SettlementNegotiateBody(BaseModel):
    amount: int
    currency: str
    settlement: Optional[dict] = None
    client_rails: Optional[list[str]] = None
    provider_rails: Optional[list[str]] = None


class DelegationRegisterBody(BaseModel):
    credential: dict[str, Any]


class PrivacyHashBody(BaseModel):
    deliverable: Any


class PrivacyTagsBody(BaseModel):
    tags: dict[str, Any]


class LiteRoundtripBody(BaseModel):
    value: Any


class ReconcileExportQuery(BaseModel):
    format: str = "json"
    rail: Optional[str] = None


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
    rail_registry=None,
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
    witness_v2_enabled: bool = False,
    federation_v2_enabled: bool = False,
    claim_store=None,
    claim_production: Optional[bool] = None,
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
        rail_registry=rail_registry,
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
    app.state.witness_v2_enabled = witness_v2_enabled
    app.state.federation_v2_enabled = federation_v2_enabled
    app.state.operators = load_operator_registry()
    app.state.access_policy = "open_quota"
    if claim_store is None:
        claim_mode = os.environ.get("NOVAPANDA_CLAIM_MODE", "mock").lower()
        claim_db = os.environ.get("NOVAPANDA_CLAIM_DB")
        if not claim_db and os.environ.get("NOVAPANDA_DB"):
            from pathlib import Path as _Path

            claim_db = str(_Path(os.environ["NOVAPANDA_DB"]).with_suffix("")) + ".claims.json"
        claim_store, claim_production = make_claim_store(mode=claim_mode, db_path=claim_db)
    elif claim_production is None:
        claim_production = isinstance(claim_store, ClaimRegistry)
    app.state.claims = claim_store
    app.state.claim_production = bool(claim_production)
    app.state.notify = NotifyInbox()
    app.state.audit = AuditLog()
    app.state.delegations = DelegationRegistry()
    app.state.rail_registry = rail_registry
    app.state.settlement = settlement
    app.state.node_profiles = [
        "NP-MIN",
        "NP-NODE",
        "NP-BUNDLE",
        "NP-SETTLE",
        "NP-PHYS",
        "NP-DELEGATE",
        "NP-PRIV",
        "NP-LITE",
    ]
    if app.state.claim_production:
        app.state.node_profiles.append("NP-CLAIM-XFER")
    strict_profiles = os.environ.get("NOVAPANDA_STRICT_PROFILES", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    gate_errs = check_profile_honesty(
        app.state.node_profiles,
        claim_mock_only=not app.state.claim_production,
        delegation_supported=True,
    )
    if strict_profiles and gate_errs:
        raise ValueError("; ".join(gate_errs))
    app.state.profile_gate_warnings = gate_errs
    app.state.dispute_tickets = DisputeTicketRegistry()
    cert_db = os.environ.get("NOVAPANDA_CERT_DB")
    app.state.certifications = CertificationRegistry.load(cert_db)
    app.state.operator_bindings = OperatorBindingRegistry()
    app.state.steward_token = os.environ.get("NOVAPANDA_STEWARD_TOKEN")
    app.state.audit.record("node.start", node_id=app.state.node_id)

    @app.middleware("http")
    async def trace_middleware(request: Request, call_next):
        request.state.trace = None
        if trace_enabled():
            path = request.url.path
            if path.startswith("/exchanges") or path.startswith("/node"):
                request.state.trace = from_headers(request.headers)
                set_current_trace(request.state.trace)
        try:
            return await call_next(request)
        finally:
            set_current_trace(None)

    def _base_url(request: Request) -> str:
        return str(request.base_url).rstrip("/")

    def _node_profile(request: Request) -> dict:
        return collect_node_profile(
            engine=engine,
            app_state=app.state,
            ontology=ontology,
            rules=rules,
            base_url=_base_url(request),
        )

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
        return exchange_to_dict(engine.get(exchange_id))

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
    def manifest(request: Request):
        body = build_node_manifest(
            app_state=app.state,
            engine=engine,
            ontology=ontology,
            rules=rules,
            base_url=_base_url(request),
        )
        # 向后兼容：旧客户端读 resource_types + 扁平 endpoints 列表
        body["endpoints_list"] = [
            "/exchanges", "/vdc/{id}", "/reputation/{agent_id}",
            "/registry/rules", "/registry/types", "/node/info",
            "/node/scenarios", "/operator/policy",
        ]
        return body

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def dashboard_home(request: Request):
        return render_console(_node_profile(request), admin=False)

    @app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
    def dashboard_admin(request: Request):
        return render_console(_node_profile(request), admin=True)

    @app.get("/console/exchanges/{exchange_id}", response_class=HTMLResponse, include_in_schema=False)
    def console_exchange_detail(exchange_id: str):
        ticket_rec = app.state.dispute_tickets.get_by_exchange(exchange_id)
        ticket = app.state.dispute_tickets.public(ticket_rec) if ticket_rec else None
        rail_down = settlement_rail_stressed(engine=engine, settlement=app.state.settlement)
        detail = exchange_public_detail(
            engine=engine,
            exchange_id=exchange_id,
            dispute_ticket=ticket,
            settlement_rail_down=rail_down,
        )
        if detail is None:
            raise HTTPException(404, {"code": "E_NOT_FOUND", "msg": exchange_id})
        return render_exchange_detail(detail)

    @app.get("/node/info")
    def node_info(request: Request):
        return _node_profile(request)

    @app.get("/node/scenarios")
    def node_scenarios():
        return collect_scenarios()

    @app.get("/node/exchanges")
    def node_exchanges_list(limit: int = 50, offset: int = 0, state: Optional[str] = None):
        return list_exchanges(engine=engine, limit=min(limit, 200), offset=offset, state=state)

    @app.get("/node/exchanges/{exchange_id}")
    def node_exchange_summary(exchange_id: str):
        detail = exchange_public_detail(engine=engine, exchange_id=exchange_id)
        if detail is None:
            raise HTTPException(404, {"code": "E_NOT_FOUND", "msg": exchange_id})
        return detail

    @app.get("/admin/status")
    def admin_status():
        return collect_status(engine=engine, app_state=app.state)

    @app.get("/operator/policy")
    def operator_policy():
        return app.state.operators.policy_snapshot()

    @app.post("/operator/register", status_code=201)
    def operator_register(body: OperatorRegisterBody):
        try:
            op, otp = app.state.operators.register(
                email=body.email,
                display_name=body.display_name,
                password=body.password,
                accept_terms=body.accept_terms,
            )
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_OPERATOR", "msg": str(exc)}) from exc
        # Trial：返回 otp 便于本地/测试（生产只发邮件）
        return {
            "operator": app.state.operators.public_view(op),
            "otp_dev": otp,
            "hint": "调用 POST /operator/verify 完成验邮；策略 A 下匿名仍可 propose",
        }

    @app.post("/operator/verify")
    def operator_verify(body: OperatorVerifyBody):
        try:
            op = app.state.operators.verify_email(email=body.email, otp=body.otp)
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_OPERATOR", "msg": str(exc)}) from exc
        return {"operator": app.state.operators.public_view(op)}

    @app.post("/operator/login")
    def operator_login(body: OperatorLoginBody):
        try:
            op, token = app.state.operators.login(email=body.email, password=body.password)
        except ValueError as exc:
            raise HTTPException(401, {"code": "E_OPERATOR", "msg": str(exc)}) from exc
        return {
            "operator": app.state.operators.public_view(op),
            "session_token": token,
            "note": "Session 仅用于运营面；exchange 仍须 Agent 签名",
        }

    @app.get("/operator/me")
    def operator_me(request: Request):
        auth = request.headers.get("Authorization") or ""
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else None
        op = app.state.operators.resolve_session(token)
        if op is None:
            raise HTTPException(401, {"code": "E_OPERATOR", "msg": "unauthorized"})
        return {
            "operator": app.state.operators.public_view(op),
            "quota": app.state.operators.quota_remaining(operator=op),
        }

    def _parties(exchange_id: str) -> set[str]:
        ex = engine.get(exchange_id)
        return {ex.client, ex.provider}

    def _operator_from_request(request: Request):
        auth = request.headers.get("Authorization") or ""
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else None
        return app.state.operators.resolve_session(token)

    def _require_operator(request: Request):
        op = _operator_from_request(request)
        if op is None:
            raise HTTPException(401, {"code": "E_OPERATOR", "msg": "unauthorized"})
        return op

    def _steward_auth(request: Request) -> None:
        token = app.state.steward_token
        if not token:
            raise HTTPException(503, {"code": "E_STEWARD", "msg": "steward not configured"})
        header = request.headers.get("X-Steward-Token")
        if header != token:
            raise HTTPException(401, {"code": "E_STEWARD", "msg": "invalid steward token"})

    def _settlement_rail() -> str:
        reg = getattr(app.state, "rail_registry", None)
        if reg is not None:
            return reg.active_rail_id
        s = app.state.settlement
        return getattr(s, "rail", type(s).__name__.replace("Settlement", "").lower() or "mock")

    def _delegation_context(
        request: Request,
        caller: Optional[str],
        action: str,
        *,
        amount: Optional[int] = None,
        currency: Optional[str] = None,
        rail: Optional[str] = None,
    ) -> Optional[dict]:
        dlg_id = request.headers.get("X-Delegation-Id")
        if not dlg_id:
            return None
        if caller is None:
            raise AuthError(401, "E_DELEGATION", "delegation requires agent auth")
        try:
            cred = app.state.delegations.validate_action(
                dlg_id,
                subject_agent_id=caller,
                action=action,
                amount=amount,
                currency=currency,
                rail=rail,
            )
        except ValueError as exc:
            msg = str(exc)
            if msg == "period_quota_exceeded":
                raise AuthError(429, "E_DELEGATION_QUOTA", msg) from exc
            if msg in ("amount_exceeds_max", "rail_not_allowed", "currency_mismatch"):
                raise AuthError(403, "E_DELEGATION_LIMIT", msg) from exc
            raise AuthError(403, "E_DELEGATION", msg) from exc
        app.state.audit.record("delegation.use", delegation_id=dlg_id, action=action)
        return cred

    @app.post("/exchanges", status_code=201)
    def propose(body: ProposeBody, request: Request, caller: Optional[str] = Depends(authn)):
        client_id = _normalize_party(body.client)
        provider_id = _normalize_party(body.provider)
        authz(caller, {client_id})  # 只有 client 本人可发起
        price_amt = None
        price_cur = None
        if isinstance(body.price, dict):
            raw_amt = body.price.get("amount")
            if isinstance(raw_amt, (int, float)):
                price_amt = int(raw_amt)
            price_cur = body.price.get("currency")
        _delegation_context(
            request, caller, "propose", amount=price_amt, currency=price_cur,
        )
        _resolve_agent_id(provider_id, body.provider_did, "provider")
        _gate_provider(provider_id)
        if not ontology.get(body.resource_type):
            raise HTTPException(400, {"code": "E_TYPE_UNKNOWN", "msg": body.resource_type})
        if not rules.get(body.rule_id):
            raise HTTPException(400, {"code": "E_RULE_UNKNOWN", "msg": body.rule_id})
        op = _operator_from_request(request)
        anon_key = (request.client.host if request.client else "unknown") or "unknown"
        try:
            quota = app.state.operators.consume_propose(operator=op, anon_key=anon_key)
        except ValueError as exc:
            if str(exc) == "quota_exceeded":
                app.state.notify.push(
                    kind="quota",
                    title="propose 配额耗尽",
                    body="请注册/验邮提升配额，或次日再试",
                    operator_id=op.operator_id if op else None,
                )
                app.state.audit.record("quota.exceeded", anon_key=anon_key)
                raise HTTPException(
                    429,
                    {"code": "E_QUOTA", "msg": "propose quota exceeded", "hint": "register or wait"},
                )
            raise
        trace_ctx = None
        if trace_enabled():
            trace_ctx = from_headers(request.headers, body_correlation_id=body.correlation_id)
            request.state.trace = trace_ctx
            set_current_trace(trace_ctx)
        ex = engine.propose(
            client=client_id, provider=provider_id,
            resource_type=body.resource_type, quantity=body.quantity,
            rule_id=body.rule_id, price=body.price,
            idempotency_key=body.idempotency_key,
            timeouts=body.timeouts or app.state.default_timeouts,
            settlement_terms=body.settlement,
            trace_context=trace_ctx.to_storage() if trace_ctx else None,
        )
        audit_meta: dict[str, Any] = {
            "exchange_id": ex.exchange_id,
            "remaining": quota.get("remaining"),
        }
        if trace_ctx:
            audit_meta["traceparent"] = trace_ctx.traceparent
            if trace_ctx.correlation_id:
                audit_meta["correlation_id"] = trace_ctx.correlation_id
        app.state.audit.record("exchange.propose", **audit_meta)
        out = exchange_to_dict(ex)
        out["_quota"] = quota
        return out

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
        from ..rail_registry import SettlementBindingError

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
        try:
            return asdict(engine.contract(exchange_id, party=party, signature=body.signature))
        except SettlementBindingError as exc:
            raise HTTPException(400, {"code": "E_RAIL_MISMATCH", "msg": str(exc)}) from exc

    @app.post("/exchanges/{exchange_id}/escrow")
    def escrow(exchange_id: str, body: EscrowBody, request: Request, caller: Optional[str] = Depends(authn)):
        ex = engine.get(exchange_id)
        authz(caller, {ex.client})
        rail = (ex.settlement_binding or {}).get("rail") or _settlement_rail()
        _delegation_context(
            request,
            caller,
            "escrow",
            amount=body.amount,
            currency=body.currency,
            rail=rail,
        )
        _gate_provider(ex.provider)
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
        ex = engine.dispute(exchange_id, by=by, reason=body.reason)
        ticket = app.state.dispute_tickets.open_for_exchange(
            exchange_id=exchange_id,
            reason=body.reason,
            dispute_info=ex.dispute_info or {},
            client=ex.client,
            provider=ex.provider,
        )
        app.state.audit.record(
            "dispute.opened",
            exchange_id=exchange_id,
            ticket_id=ticket.ticket_id,
        )
        out = asdict(ex)
        out["dispute_ticket"] = app.state.dispute_tickets.public(ticket)
        return out

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

    # —— T01 验证工具 · T02 Bundle · T03 Claim mock · T05/T06 settle · T07 Admin · T08 Notify ——

    @app.post("/node/tools/canonical")
    def tool_canonical(body: CanonicalBody):
        raw = canonical_bytes(body.value)
        return {
            "canonical_utf8": raw.decode("utf-8"),
            "sha256": "sha256:" + sha256_hex(raw),
            "note": "私钥勿上传；本工具仅规范化与哈希",
        }

    @app.post("/node/tools/bundle/validate")
    def tool_bundle_validate(body: BundleValidateBody):
        errors = validate_bundle(body.bundle)
        return {"ok": not errors, "errors": errors, "composer": "client-side-library"}

    @app.get("/node/claims")
    def claims_list(holder: Optional[str] = None):
        items = app.state.claims.list_for_holder(holder)
        return {
            "mock": not app.state.claim_production,
            "profile": "NP-CLAIM-XFER" if app.state.claim_production else None,
            "total": len(items),
            "claims": [app.state.claims.public(c) for c in items],
        }

    def _claim_code() -> str:
        return "E_CLAIM" if app.state.claim_production else "E_CLAIM_MOCK"

    def _active_rail() -> str:
        reg = getattr(app.state, "rail_registry", None)
        if reg is not None:
            return reg.active_rail_id
        return getattr(app.state.settlement, "rail", "mock")

    @app.get("/node/claims/{claim_id}")
    def claims_get(claim_id: str):
        rec = app.state.claims.get(claim_id)
        if rec is None:
            raise HTTPException(404, {"code": "E_NOT_FOUND", "msg": claim_id})
        return {"claim": app.state.claims.public(rec)}

    @app.post("/node/claims/issue", status_code=201)
    def claims_issue(body: ClaimIssueBody):
        try:
            c = app.state.claims.issue(
                vdc_id=body.vdc_id,
                amount=body.amount,
                currency=body.currency,
                holder=body.holder,
                **({"rail": _active_rail()} if app.state.claim_production else {}),
            )
        except ValueError as exc:
            raise HTTPException(400, {"code": _claim_code(), "msg": str(exc)}) from exc
        app.state.audit.record("claim.issue", claim_id=c.claim_id, vdc_id=body.vdc_id)
        return {"claim": app.state.claims.public(c)}

    @app.post("/node/claims/assign")
    def claims_assign(body: ClaimAssignBody):
        if not app.state.claim_production:
            raise HTTPException(400, {"code": "E_CLAIM_MOCK", "msg": "assignment requires production claim mode"})
        try:
            c = app.state.claims.assign(
                body.claim_id,
                body.to_agent_id,
                signature=body.signature,
                nonce=body.nonce,
                at=body.at,
            )
        except ValueError as exc:
            raise HTTPException(400, {"code": _claim_code(), "msg": str(exc)}) from exc
        app.state.audit.record("claim.assign", claim_id=body.claim_id, to=body.to_agent_id)
        return {"claim": app.state.claims.public(c)}

    @app.post("/node/claims/redeem")
    def claims_redeem(body: ClaimRedeemBody):
        if not app.state.claim_production:
            raise HTTPException(400, {"code": "E_CLAIM_MOCK", "msg": "redeem requires production claim mode"})
        try:
            c = app.state.claims.redeem(body.claim_id)
        except ValueError as exc:
            raise HTTPException(400, {"code": _claim_code(), "msg": str(exc)}) from exc
        app.state.audit.record("claim.redeem", claim_id=body.claim_id)
        return {"claim": app.state.claims.public(c)}

    @app.post("/node/claims/reserve")
    def claims_reserve(body: ClaimActionBody):
        if not body.exchange_id:
            raise HTTPException(400, {"code": _claim_code(), "msg": "exchange_id required"})
        try:
            c = app.state.claims.reserve(body.claim_id, for_exchange_id=body.exchange_id)
        except ValueError as exc:
            raise HTTPException(400, {"code": _claim_code(), "msg": str(exc)}) from exc
        return {"claim": app.state.claims.public(c)}

    @app.post("/node/claims/capture")
    def claims_capture(body: ClaimActionBody):
        try:
            c = app.state.claims.capture(body.claim_id)
        except ValueError as exc:
            raise HTTPException(400, {"code": _claim_code(), "msg": str(exc)}) from exc
        return {"claim": app.state.claims.public(c)}

    @app.post("/node/claims/release")
    def claims_release(body: ClaimActionBody):
        try:
            c = app.state.claims.release(body.claim_id)
        except ValueError as exc:
            raise HTTPException(400, {"code": _claim_code(), "msg": str(exc)}) from exc
        return {"claim": app.state.claims.public(c)}

    @app.post("/node/settle/simulate")
    def settle_simulate(
        request: Request,
        body: SettleSimBody | None = None,
        caller: Optional[str] = Depends(authn),
    ):
        """无资金：对 MockSettlement / Sandbox 做 escrow→settle 演示。"""
        payload = body or SettleSimBody()
        rail = payload.rail or _settlement_rail()
        if request is not None and request.headers.get("X-Delegation-Id"):
            _delegation_context(
                request,
                caller,
                "escrow",
                amount=payload.amount,
                currency=payload.currency,
                rail=rail,
            )
        exchange_id = payload.exchange_id or ("sim-" + os.urandom(4).hex())
        s = app.state.settlement
        if not isinstance(s, (MockSettlement, SandboxSettlement)):
            return {
                "ok": False,
                "msg": "simulator requires MockSettlement or SandboxSettlement (trial)",
                "rail": getattr(s, "rail", type(s).__name__),
            }
        try:
            handle = s.escrow(exchange_id, payload.amount, payload.currency)
            r1 = s.settle(handle)
            r2 = s.settle(handle)  # idempotent
        except SettlementError as exc:
            raise HTTPException(400, {"code": "E_SETTLE_SIM", "msg": str(exc)}) from exc
        app.state.audit.record("settle.simulate", handle=handle)
        return {
            "ok": True,
            "mock": isinstance(s, MockSettlement),
            "sandbox": isinstance(s, SandboxSettlement),
            "handle": handle,
            "first": r1,
            "idempotent_second": r2,
            "rail": r1.get("rail", "mock"),
        }

    @app.post("/node/delegations", status_code=201)
    def delegations_register(body: DelegationRegisterBody):
        try:
            cred = app.state.delegations.register(body.credential)
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_DELEGATION", "msg": str(exc)}) from exc
        app.state.audit.record("delegation.register", delegation_id=cred["delegation_id"])
        return {"delegation": cred}

    @app.get("/node/delegations/{delegation_id}")
    def delegations_get(delegation_id: str):
        cred = app.state.delegations.get(delegation_id)
        if cred is None:
            raise HTTPException(404, {"code": "E_DELEGATION", "msg": "not found or expired"})
        return {"delegation": app.state.delegations.public(cred)}

    @app.get("/node/delegations")
    def delegations_list(subject: Optional[str] = None):
        if not subject:
            return {"items": [], "hint": "pass ?subject=ed25519:…"}
        return {"items": app.state.delegations.list_for_subject(subject)}

    @app.post("/node/delegations/{delegation_id}/revoke")
    def delegations_revoke(delegation_id: str, caller: Optional[str] = Depends(authn)):
        if caller is None:
            raise AuthError(401, "E_AUTH_MISSING", "issuer must sign request")
        try:
            cred = app.state.delegations.revoke(delegation_id, issuer_agent_id=caller)
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_DELEGATION", "msg": str(exc)}) from exc
        app.state.audit.record("delegation.revoke", delegation_id=delegation_id)
        return {"delegation": cred}

    @app.post("/node/tools/privacy/hash-only")
    def tool_privacy_hash(body: PrivacyHashBody):
        wrapped = hash_only_wrap(body.deliverable)
        return {"ok": True, "wrapped": wrapped, "profile": "NP-PRIV"}

    @app.post("/node/tools/privacy/validate-tags")
    def tool_privacy_tags(body: PrivacyTagsBody):
        errors = validate_privacy_tags(body.tags)
        return {"ok": not errors, "errors": errors}

    @app.get("/node/privacy/policy")
    def privacy_policy():
        return {"privacy": privacy_manifest_block()}

    @app.post("/node/tools/lite/roundtrip")
    def tool_lite_roundtrip(body: LiteRoundtripBody):
        try:
            result = lite_roundtrip(body.value)
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_LITE", "msg": str(exc)}) from exc
        return {"ok": result["equal"], **result, "profile": "NP-LITE"}

    @app.get("/node/settlement/quote")
    def settlement_quote(
        amount: int,
        currency: str,
        preferred_rails: Optional[str] = None,
        client_rails: Optional[str] = None,
        provider_rails: Optional[str] = None,
    ):
        from ..rail_registry import quote_settlement

        def _split(raw: Optional[str]) -> Optional[list[str]]:
            if not raw:
                return None
            return [p.strip() for p in raw.split(",") if p.strip()]

        reg = getattr(app.state, "rail_registry", None)
        if reg is None:
            s = app.state.settlement
            rid = getattr(s, "rail", "mock")
            meta = s.manifest_rail() if hasattr(s, "manifest_rail") else {"id": rid}
            node_rails = [meta]
        else:
            node_rails = reg.manifest_rails()
        try:
            return quote_settlement(
                amount=amount,
                currency=currency,
                node_rails=node_rails,
                preferred_rails=_split(preferred_rails),
                client_rails=_split(client_rails),
                provider_rails=_split(provider_rails),
            )
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_INVALID", "msg": str(exc)}) from exc

    @app.post("/node/settlement/negotiate")
    def settlement_negotiate(body: SettlementNegotiateBody):
        from ..rail_registry import SettlementBindingError, preview_settlement_binding

        reg = getattr(app.state, "rail_registry", None)
        if reg is None:
            raise HTTPException(
                501,
                {"code": "E_NOT_SUPPORTED", "msg": "multi-rail registry required"},
            )
        try:
            binding = preview_settlement_binding(
                amount=body.amount,
                currency=body.currency,
                settlement_terms=body.settlement,
                node_rails=reg.manifest_rails(),
                client_rails=body.client_rails,
                provider_rails=body.provider_rails,
            )
        except SettlementBindingError as exc:
            raise HTTPException(400, {"code": "E_RAIL_MISMATCH", "msg": str(exc)}) from exc
        quote = reg.quote(
            body.amount,
            body.currency,
            preferred_rails=(body.settlement or {}).get("preferred_rails"),
            client_rails=body.client_rails,
            provider_rails=body.provider_rails,
        )
        return {"quote": quote, "binding_preview": binding}

    @app.get("/node/settlement/rails")
    def settlement_rails():
        reg = getattr(app.state, "rail_registry", None)
        if reg is not None:
            block = reg.manifest_block()
            return {
                **block,
                "active_rail": reg.active_rail_id,
                "profiles": [p for p in app.state.node_profiles if p.startswith("NP-")],
                "profile_gate_warnings": app.state.profile_gate_warnings,
                "faq": "sandbox/mock success ≠ production funds",
            }
        s = app.state.settlement
        rail = _settlement_rail()
        if hasattr(s, "manifest_rail"):
            entry = s.manifest_rail()
        else:
            entry = {
                "id": rail,
                "currencies": ["USD"],
                "finality": "instant" if rail == "mock" else "t+1",
                "licensed": bool(getattr(s, "licensed", False)),
                "environment": getattr(
                    s, "environment", "mock" if rail == "mock" else "production"
                ),
            }
            if getattr(s, "partner", None):
                entry["partner"] = s.partner
        return {
            "rails": [entry],
            "profiles": [p for p in app.state.node_profiles if p.startswith("NP-")],
            "profile_gate_warnings": app.state.profile_gate_warnings,
            "faq": "sandbox/mock success ≠ production funds",
        }

    @app.get("/admin/reconcile/export")
    def admin_reconcile_export(
        request: Request,
        format: str = "json",
        rail: Optional[str] = None,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
    ):
        _admin_auth(request)
        package = build_reconcile_export(
            engine=request.app.state.engine,
            settlement=app.state.settlement,
            node_id=app.state.node_id,
            rail=rail,
            from_ts=from_ts,
            to_ts=to_ts,
            claims=app.state.claims,
        )
        if format.lower() == "csv":
            from fastapi.responses import PlainTextResponse

            return PlainTextResponse(export_csv(package), media_type="text/csv")
        if format.lower() == "claims_csv":
            from fastapi.responses import PlainTextResponse

            return PlainTextResponse(export_claim_csv(package), media_type="text/csv")
        return package

    @app.get("/node/profile-gate")
    def profile_gate_status():
        return {
            "profiles": list(app.state.node_profiles),
            "warnings": list(app.state.profile_gate_warnings),
            "strict_env": os.environ.get("NOVAPANDA_STRICT_PROFILES"),
        }

    @app.get("/node/notify")
    def notify_list(request: Request, limit: int = 50):
        op = _operator_from_request(request)
        oid = op.operator_id if op else None
        return {"items": app.state.notify.list(operator_id=oid, limit=min(limit, 100))}

    @app.post("/node/notify", status_code=201)
    def notify_push(body: NotifyBody, request: Request):
        op = _operator_from_request(request)
        item = app.state.notify.push(
            kind=body.kind,
            title=body.title,
            body=body.body,
            operator_id=op.operator_id if op else None,
        )
        return {"item": item}

    def _admin_auth(request: Request) -> None:
        token = app.state.admin_token
        if token:
            header = request.headers.get("X-Admin-Token")
            if header != token:
                raise AuthError(401, "E_ADMIN_UNAUTHORIZED", "invalid or missing X-Admin-Token")

    @app.get("/admin/audit")
    def admin_audit(request: Request, limit: int = 100):
        _admin_auth(request)
        return {"items": app.state.audit.list(limit=min(limit, 200))}

    @app.get("/admin/alerts")
    def admin_alerts(request: Request):
        _admin_auth(request)
        health = scan_settlement_health(
            engine=request.app.state.engine, settlement=app.state.settlement,
        )
        held = health["held_escrow_count"]
        stale = health["stale_pending_count"]
        alerts = alert_snapshot(
            held_escrows=held,
            anon_quota=app.state.operators.anonymous_propose_per_day,
            stale_pending=stale,
        )
        return {"alerts": alerts, "settlement_health": health}

    @app.get("/admin/settlement/intents")
    def admin_settlement_intents(request: Request):
        """RB-04 诊断：悬挂 intent 与 held escrow 快照。"""
        _admin_auth(request)
        return scan_settlement_health(
            engine=request.app.state.engine, settlement=app.state.settlement,
        )

    @app.post("/admin/recover")
    def admin_recover(request: Request):
        """RB-04：手动触发 recover()（幂等）。"""
        _admin_auth(request)
        recovered = request.app.state.engine.recover()
        app.state.audit.record(
            "admin.recover",
            count=len(recovered),
            exchange_ids=[e.exchange_id for e in recovered],
        )
        return {
            "ok": True,
            "recovered": [e.exchange_id for e in recovered],
            "count": len(recovered),
        }

    @app.post("/admin/baseline-reset")
    def admin_baseline_reset(request: Request):
        """试验环境回收：清 Claim mock / notify / 配额计数；不删历史 VDC 签名事实。"""
        _admin_auth(request)
        if app.state.claim_production:
            app.state.claims.clear()
            cleared = ["claims_production", "notify", "propose_counts"]
        else:
            app.state.claims = ClaimMockRegistry()
            cleared = ["claims_mock", "notify", "propose_counts"]
        app.state.notify = NotifyInbox()
        app.state.operators._propose_counts.clear()
        app.state.audit.record("admin.baseline_reset")
        return {
            "ok": True,
            "cleared": cleared,
            "note": "不改写已签 VDC；禁匿名调用本接口",
        }

    @app.get("/operator/quota")
    def operator_quota(request: Request):
        op = _operator_from_request(request)
        anon_key = (request.client.host if request.client else "unknown") or "unknown"
        return {"quota": app.state.operators.quota_remaining(operator=op, anon_key=anon_key)}

    @app.post("/operator/agents/bind", status_code=201)
    def operator_bind_agent(body: OperatorBindBody, request: Request):
        op = _require_operator(request)
        try:
            rec = app.state.operator_bindings.bind(
                operator_id=op.operator_id,
                agent_id=body.agent_id,
                node_id=app.state.node_id,
                signature=body.signature,
                issued_at=body.issued_at,
                label=body.label,
            )
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_OPERATOR", "msg": str(exc)}) from exc
        return {
            "binding": app.state.operator_bindings.public(rec),
        }

    @app.get("/operator/agents/claim-payload")
    def operator_claim_payload_endpoint(agent_id: str, request: Request):
        op = _require_operator(request)
        try:
            payload = app.state.operator_bindings.build_claim_payload(
                agent_id=agent_id,
                operator_id=op.operator_id,
                node_id=app.state.node_id,
            )
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_OPERATOR", "msg": str(exc)}) from exc
        return {"payload": payload}

    @app.post("/operator/agents/unbind")
    def operator_unbind_agent(body: OperatorUnbindBody, request: Request):
        op = _require_operator(request)
        ok = app.state.operator_bindings.unbind(
            operator_id=op.operator_id,
            agent_id=body.agent_id,
        )
        if not ok:
            raise HTTPException(404, {"code": "E_NOT_FOUND", "msg": body.agent_id})
        return {"ok": True}

    @app.get("/operator/agents")
    def operator_list_agents(request: Request):
        op = _require_operator(request)
        bindings = app.state.operator_bindings.list_for_operator(op.operator_id)
        return {
            "items": [app.state.operator_bindings.public(b) for b in bindings],
        }

    @app.get("/operator/dashboard", response_class=HTMLResponse, include_in_schema=False)
    def operator_dashboard_page(request: Request):
        op = _require_operator(request)
        anon_key = (request.client.host if request.client else "unknown") or "unknown"
        quota = app.state.operators.quota_remaining(operator=op, anon_key=anon_key)
        bindings = [
            app.state.operator_bindings.public(b)
            for b in app.state.operator_bindings.list_for_operator(op.operator_id)
        ]
        return render_operator_dashboard(
            app.state.operators.public_view(op), quota, bindings,
        )

    @app.get("/operator/agents-ui", response_class=HTMLResponse, include_in_schema=False)
    def operator_agents_ui_page(request: Request):
        op = _require_operator(request)
        bindings = [
            app.state.operator_bindings.public(b)
            for b in app.state.operator_bindings.list_for_operator(op.operator_id)
        ]
        return render_operator_agents_ui(bindings)

    @app.get("/operator/exchanges", response_class=HTMLResponse, include_in_schema=False)
    def operator_exchanges_page(request: Request):
        op = _require_operator(request)
        agents = app.state.operator_bindings.agent_ids_for_operator(op.operator_id)
        page = list_exchanges(engine=engine, limit=100, agent_ids=agents or None)
        return render_operator_exchanges(page.get("items") or [])

    @app.get("/operator/settings", response_class=HTMLResponse, include_in_schema=False)
    def operator_settings_page(request: Request):
        op = _require_operator(request)
        return render_operator_settings(app.state.operators.public_view(op))

    @app.post("/operator/settings/deletion-request")
    def operator_deletion_request(request: Request):
        op = _require_operator(request)
        try:
            updated = app.state.operators.request_deletion(op.operator_id)
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_OPERATOR", "msg": str(exc)}) from exc
        return {"operator": app.state.operators.public_view(updated)}

    @app.post("/operator/settings/deletion-cancel")
    def operator_deletion_cancel(request: Request):
        op = _require_operator(request)
        try:
            updated = app.state.operators.cancel_deletion(op.operator_id)
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_OPERATOR", "msg": str(exc)}) from exc
        return {"operator": app.state.operators.public_view(updated)}

    @app.get("/operator/help", response_class=HTMLResponse, include_in_schema=False)
    def operator_help_page(request: Request):
        _require_operator(request)
        return render_operator_help()

    @app.get("/operator/bundles", response_class=HTMLResponse, include_in_schema=False)
    def operator_bundles_page(request: Request):
        _require_operator(request)
        return render_operator_bundles()

    @app.get("/steward", response_class=HTMLResponse, include_in_schema=False)
    def steward_certifications_page():
        items = app.state.certifications.list_public(status=None)
        return render_steward_certifications(
            [app.state.certifications.public(r) for r in items],
        )

    @app.get("/operator/claims", response_class=HTMLResponse, include_in_schema=False)
    def operator_claims_page(request: Request, holder: Optional[str] = None):
        op = _require_operator(request)
        agents = app.state.operator_bindings.agent_ids_for_operator(op.operator_id)
        if holder and holder not in agents and agents:
            raise HTTPException(403, {"code": "E_OPERATOR", "msg": "holder not bound"})
        target = holder
        if not target and len(agents) == 1:
            target = agents[0]
        items = app.state.claims.list_for_holder(target) if target else []
        if not target and not agents:
            items = app.state.claims.list_for_holder(None)[:50]
        public = [app.state.claims.public(c) for c in items]
        return render_operator_claims(public, mock=not app.state.claim_production)

    @app.get("/operator/claims/{claim_id}", response_class=HTMLResponse, include_in_schema=False)
    def operator_claim_detail_page(claim_id: str, request: Request):
        _require_operator(request)
        rec = app.state.claims.get(claim_id)
        if rec is None:
            raise HTTPException(404, {"code": "E_NOT_FOUND", "msg": claim_id})
        return render_claim_detail(app.state.claims.public(rec))

    @app.get("/operator/reconcile", response_class=HTMLResponse, include_in_schema=False)
    def operator_reconcile_page(
        request: Request,
        rail: Optional[str] = None,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
    ):
        _require_operator(request)
        package = build_reconcile_export(
            engine=engine,
            settlement=app.state.settlement,
            node_id=app.state.node_id,
            rail=rail,
            from_ts=from_ts,
            to_ts=to_ts,
            claims=app.state.claims,
        )
        preview = (package.get("rows") or []) + (package.get("claim_rows") or [])
        return render_operator_reconcile(package.get("meta") or {}, preview)

    @app.get("/operator/reconcile/export")
    def operator_reconcile_export(
        request: Request,
        format: str = "csv",
        rail: Optional[str] = None,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
    ):
        _require_operator(request)
        package = build_reconcile_export(
            engine=engine,
            settlement=app.state.settlement,
            node_id=app.state.node_id,
            rail=rail,
            from_ts=from_ts,
            to_ts=to_ts,
            claims=app.state.claims,
        )
        from fastapi.responses import PlainTextResponse

        if format.lower() == "claims_csv":
            return PlainTextResponse(export_claim_csv(package), media_type="text/csv")
        return PlainTextResponse(export_csv(package), media_type="text/csv")

    @app.get("/operator/disputes")
    def operator_disputes_list(request: Request, state: Optional[str] = None, limit: int = 50):
        _require_operator(request)
        tickets = app.state.dispute_tickets.list_all(state=state, limit=min(limit, 200))
        return {"items": [app.state.dispute_tickets.public(t) for t in tickets]}

    @app.get("/operator/disputes/{ticket_id}")
    def operator_dispute_detail(ticket_id: str, request: Request):
        _require_operator(request)
        ticket = app.state.dispute_tickets.get(ticket_id)
        if ticket is None:
            raise HTTPException(404, {"code": "E_NOT_FOUND", "msg": ticket_id})
        return {"ticket": app.state.dispute_tickets.public(ticket)}

    @app.get("/operator/disputes-ui", response_class=HTMLResponse, include_in_schema=False)
    def operator_disputes_ui(request: Request):
        _require_operator(request)
        tickets = app.state.dispute_tickets.list_all(limit=100)
        return render_operator_disputes(
            [app.state.dispute_tickets.public(t) for t in tickets]
        )

    @app.get("/public/certifications")
    def public_certifications_list(status: Optional[str] = "active"):
        items = app.state.certifications.list_public(status=status)
        return {
            "items": [app.state.certifications.public(r) for r in items],
        }

    @app.get("/public/certifications/{cert_id}")
    def public_certification_detail(cert_id: str):
        rec = app.state.certifications.get(cert_id)
        if rec is None:
            raise HTTPException(404, {"code": "E_NOT_FOUND", "msg": cert_id})
        return {"certification": app.state.certifications.public(rec)}

    @app.post("/steward/certifications", status_code=201)
    def steward_grant_certification(body: CertificationGrantBody, request: Request):
        _steward_auth(request)
        try:
            rec = app.state.certifications.grant(
                level=body.level,
                applicant=body.applicant,
                implementation=body.implementation,
                profiles=body.profiles,
                cases_passed=body.cases_passed,
                manifest_sample=body.manifest_sample,
                rail_disclosure=body.rail_disclosure,
                cert_id=body.cert_id,
                expires_at=body.expires_at,
            )
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_CERT", "msg": str(exc)}) from exc
        app.state.audit.record("cert.grant", cert_id=rec.cert_id, level=rec.level)
        return {"certification": app.state.certifications.public(rec)}

    @app.patch("/steward/certifications/{cert_id}")
    def steward_patch_certification(
        cert_id: str, body: CertificationStatusBody, request: Request,
    ):
        _steward_auth(request)
        try:
            rec = app.state.certifications.set_status(cert_id, body.status)
        except ValueError as exc:
            raise HTTPException(400, {"code": "E_CERT", "msg": str(exc)}) from exc
        app.state.audit.record("cert.status", cert_id=cert_id, status=body.status)
        return {"certification": app.state.certifications.public(rec)}

    @app.post("/admin/sweep")
    def sweep(request: Request):
        """超时清扫：由外部调度器周期调用（真实部署可挂 cron 或后台任务）。"""
        _admin_auth(request)
        expired = engine.sweep()
        app.state.audit.record("admin.sweep", count=len(expired))
        return {"expired": [ex.exchange_id for ex in expired]}

    @app.get("/registry/rules")
    def list_rules():
        return rules.list()

    @app.get("/registry/types")
    def list_types():
        return ontology.list()

    brand_dir = Path(__file__).resolve().parent / "static" / "brand"
    if brand_dir.is_dir():
        app.mount(
            "/static/brand",
            StaticFiles(directory=str(brand_dir)),
            name="brand-assets",
        )

    return app


def create_app_from_config(cfg=None) -> FastAPI:
    """从 NodeConfig / 环境变量创建生产节点（uvicorn --factory 入口）。"""
    from ..config import NodeConfig

    cfg = cfg or NodeConfig.from_env()
    cfg.apply_feature_flags()
    store = cfg.make_store()
    registry = cfg.make_rail_registry()
    claim_store, claim_production = cfg.make_claim_store()
    return create_app(
        store=store,
        auth=cfg.auth,
        reputation_store=cfg.make_reputation_store(),
        settlement=registry.active_adapter,
        rail_registry=registry,
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
        witness_v2_enabled=cfg.witness_v2,
        federation_v2_enabled=cfg.federation_v2,
        claim_store=claim_store,
        claim_production=claim_production,
        seed=True,
    )
