"""LLM Function Calling 工具声明 + Skill 门面。

第三方 Agent 应优先调用本模块，而非直接拼 hex / 翻堆栈。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from novapanda.autonomy import (
    DynamicPricingEngine,
    HeuristicTaskDispatcher,
    PricingInput,
    SupplyChainOrchestrator,
    TaskSpec,
)
from novapanda.marketplace.types import (
    ExchangeTerminalSnapshot,
    MatchQuery,
    PriceQuote,
)
from novapanda.settlement import MockSettlement, SettlementAdapter, SettlementError

from .compact import (
    compact_graph,
    compact_orchestration,
    compact_terminal_snapshot,
    short_agent_id,
)
from .errors import AgentFault, RecoveryAction, classify_exception, fault_from_mapping


# ----- OpenAI / Claude 风格工具 schema（description 即 docstring 精华）-----

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "novapanda_list_tools",
        "description": (
            "List NovaPanda Skill tool names available to this Agent. "
            "Call first when unsure which autonomy or settlement action to use."
        ),
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "novapanda_quote_price",
        "description": (
            "Get a structured service price quote from DynamicPricingEngine. "
            "Inputs are plain numbers (amount, load_ratio, token_estimate)—never raw hex. "
            "Use before bidding or raising a TaskSpec.budget."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "resource_type": {
                    "type": "string",
                    "description": "Capability type, e.g. compute.pipeline",
                },
                "benchmark_amount": {
                    "type": "integer",
                    "description": "Market benchmark price in minor units (integer)",
                },
                "currency": {"type": "string", "description": "ISO currency, default USD"},
                "load_ratio": {
                    "type": "number",
                    "description": "Provider load in [0,1]",
                },
                "token_estimate": {"type": "integer"},
                "step_estimate": {"type": "integer"},
                "reputation": {
                    "type": "number",
                    "description": "Optional effective reputation [0,1]",
                },
                "grid_load_ratio": {
                    "type": "number",
                    "description": "DePIN grid load [0,1] for charger pricing",
                },
                "queue_length": {
                    "type": "integer",
                    "description": "Physical queue length at charger / bay",
                },
            },
            "required": ["resource_type", "benchmark_amount"],
            "additionalProperties": False,
        },
    },
    {
        "name": "novapanda_hold_auction",
        "description": (
            "Hold a parameterized auction for a goal (e.g. EV truck vs chargers). "
            "Splits via dispatcher then MarketplaceAuctioneer.hold_auction. "
            "Returns compact awards — never raw tx hex."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "string"},
                "resource_type": {"type": "string"},
                "client_agent_id": {"type": "string"},
                "budget_amount": {"type": "integer"},
                "currency": {"type": "string"},
                "payload": {"description": "Task payload"},
                "required_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "max_response_ms": {"type": "integer"},
            },
            "required": [
                "goal_id",
                "resource_type",
                "client_agent_id",
                "budget_amount",
            ],
            "additionalProperties": False,
        },
    },
    {
        "name": "novapanda_split_task",
        "description": (
            "Split a goal into a compact DAG of subtasks (chain or parallel). "
            "Returns dependency edges and resource types without bulky payloads by default."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "string"},
                "resource_type": {"type": "string"},
                "client_agent_id": {
                    "type": "string",
                    "description": "Client agent id (ed25519:…); full id OK",
                },
                "budget_amount": {"type": "integer"},
                "currency": {"type": "string"},
                "payload": {
                    "description": "Task body: object, list (parallel parts), or omit if using steps",
                },
                "steps": {
                    "type": "array",
                    "description": "Optional ordered steps → chained depends_on",
                    "items": {"type": "object"},
                },
                "include_payloads": {
                    "type": "boolean",
                    "description": "If true, include clipped payloads (costs tokens)",
                },
            },
            "required": [
                "goal_id",
                "resource_type",
                "client_agent_id",
                "budget_amount",
            ],
            "additionalProperties": False,
        },
    },
    {
        "name": "novapanda_run_supply_chain",
        "description": (
            "Run the full autonomy loop: split → auction → execute DAG legs → aggregate. "
            "Returns a TOKEN-COMPACT orchestration report (phase, awards, leg states). "
            "On failure returns structured AgentFault with recovery hint "
            "(retry_adjust / switch_provider / escalate_human)—not a stack trace."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "string"},
                "resource_type": {"type": "string"},
                "client_agent_id": {"type": "string"},
                "budget_amount": {"type": "integer"},
                "currency": {"type": "string"},
                "payload": {"description": "Task payload"},
                "steps": {"type": "array", "items": {"type": "object"}},
                "required_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "include_results": {
                    "type": "boolean",
                    "description": "Include clipped leg results (default false)",
                },
            },
            "required": [
                "goal_id",
                "resource_type",
                "client_agent_id",
                "budget_amount",
            ],
            "additionalProperties": False,
        },
    },
    {
        "name": "novapanda_settlement_escrow",
        "description": (
            "Escrow funds on the configured settlement adapter (default mock). "
            "Pass integer amount + currency + exchange_id — never raw chain hex."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "exchange_id": {"type": "string"},
                "amount": {"type": "integer", "description": "Non-negative integer"},
                "currency": {"type": "string"},
            },
            "required": ["exchange_id", "amount"],
            "additionalProperties": False,
        },
    },
    {
        "name": "novapanda_settlement_settle",
        "description": (
            "Capture/settle an escrow handle returned by novapanda_settlement_escrow. "
            "On state conflict returns SETTLEMENT_CONFLICT → escalate_human (do not blind-retry)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "handle": {
                    "type": "string",
                    "description": "Opaque escrow handle from escrow call",
                }
            },
            "required": ["handle"],
            "additionalProperties": False,
        },
    },
    {
        "name": "novapanda_settlement_refund",
        "description": "Refund an escrow handle. Same structured-error contract as settle.",
        "parameters": {
            "type": "object",
            "properties": {"handle": {"type": "string"}},
            "required": ["handle"],
            "additionalProperties": False,
        },
    },
    {
        "name": "novapanda_compact_terminal",
        "description": (
            "Shrink an exchange terminal snapshot to a token-cheap dict "
            "(ids shortened, no logs). Use when feeding Sink/reputation events to an LLM."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "exchange_id": {"type": "string"},
                "state": {"type": "string"},
                "client": {"type": "string"},
                "provider": {"type": "string"},
                "resource_type": {"type": "string"},
                "quantity": {"type": "integer"},
                "vdc_id": {"type": "string"},
                "price_amount": {"type": "integer"},
                "price_currency": {"type": "string"},
                "outcome_hint": {"type": "string"},
            },
            "required": [
                "exchange_id",
                "state",
                "client",
                "provider",
                "resource_type",
                "quantity",
                "price_amount",
            ],
            "additionalProperties": False,
        },
    },
    {
        "name": "novapanda_classify_error",
        "description": (
            "Map a raw error message (from RPC/Paymaster/Stripe/settlement) "
            "into AgentFault: code, retryable, recovery action, and hint. "
            "Call when a low-level API threw a stringy exception."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Raw error text"},
            },
            "required": ["message"],
            "additionalProperties": False,
        },
    },
    {
        "name": "novapanda_discover_providers",
        "description": (
            "Discover and rank marketplace providers for a resource_type "
            "(MatchRouter: price × SLA × reputation × tags). "
            "Returns a compact winner + ranked shortlist — never raw tx hex. "
            "Use before novapanda_run_supply_chain to validate supply exists."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "resource_type": {"type": "string"},
                "max_price_amount": {"type": "integer"},
                "currency": {"type": "string"},
                "max_response_ms": {"type": "integer"},
                "quantity": {"type": "integer"},
                "required_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "min_reputation": {"type": "number"},
                "limit": {"type": "integer"},
                "client_agent_id": {"type": "string"},
            },
            "required": ["resource_type", "max_price_amount"],
            "additionalProperties": False,
        },
    },
    {
        "name": "novapanda_estimate_gas",
        "description": (
            "Estimate native gas for a structured transfer on a wired chain adapter. "
            "Pass integer amount and addresses as plain strings — never signed-tx hex. "
            "If estimate is degraded (RPC fallback), retry_same or proceed cautiously."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "from_address": {"type": "string"},
                "to_address": {"type": "string"},
                "amount": {"type": "integer", "description": "Native amount in minor units"},
                "symbol": {"type": "string", "description": "Asset symbol, default ETH"},
            },
            "required": ["from_address", "to_address", "amount"],
            "additionalProperties": False,
        },
    },
    {
        "name": "novapanda_paymaster_sponsor",
        "description": (
            "Simulate ERC-4337-style Paymaster sponsorship: quote fee-token cost "
            "and sponsor a UserOp reference. Integer gas + fee token only; "
            "never paste raw calldata hex into the LLM context."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "payer_address": {"type": "string"},
                "gas_native": {"type": "integer"},
                "fee_token_symbol": {"type": "string", "description": "e.g. USDC"},
                "fee_token_decimals": {"type": "integer"},
                "user_op_ref": {"type": "string", "description": "Opaque UserOp id"},
            },
            "required": ["payer_address", "gas_native", "user_op_ref"],
            "additionalProperties": False,
        },
    },
    {
        "name": "novapanda_verify_proof",
        "description": (
            "Submit a deliverable to the Verification Gateway (schema/TEE/docker backends). "
            "On pass, returns a compact credential summary for VDC verify stage. "
            "Pass structured deliverable JSON — never hex blobs."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "exchange_id": {"type": "string"},
                "vdc_id": {"type": "string"},
                "rule_id": {"type": "string"},
                "deliverable": {
                    "type": "object",
                    "description": "JSON deliverable matching the verify schema",
                },
                "result_hash": {
                    "type": "string",
                    "description": "Optional; computed if omitted",
                },
                "device_id": {
                    "type": "string",
                    "description": "Hardware device id for TPM PoD",
                },
                "tpm_signature": {
                    "type": "string",
                    "description": "Simulated TPM signature string (tpm:…)",
                },
            },
            "required": ["exchange_id", "vdc_id", "deliverable"],
            "additionalProperties": False,
        },
    },
]


def tool_names() -> list[str]:
    return [t["name"] for t in TOOL_DEFINITIONS]


def _ok(result: Any) -> dict[str, Any]:
    return {"ok": True, "result": result}


def _err(fault: AgentFault) -> dict[str, Any]:
    return {"ok": False, "fault": fault.to_dict()}


@dataclass
class NovaPandaAgentSkill:
    """Skill toolbox for third-party AI Agents integrating NovaPanda.

    Wire an optional ``orchestrator`` (SupplyChainOrchestrator) and
    ``settlement`` adapter. All public methods return
    ``{ok: true, result: ...}`` or ``{ok: false, fault: AgentFault}``—
    safe to drop straight into an LLM tool-result channel.
    """

    orchestrator: Optional[SupplyChainOrchestrator] = None
    settlement: SettlementAdapter = field(default_factory=MockSettlement)
    pricing: DynamicPricingEngine = field(default_factory=DynamicPricingEngine)
    dispatcher: HeuristicTaskDispatcher = field(
        default_factory=HeuristicTaskDispatcher
    )
    auctioneer: Any = None  # MarketplaceAuctioneer.hold_auction
    # optional gas estimator: (from_address, TransferRequest) -> GasQuote-like
    estimate_gas_fn: Optional[Callable[..., Any]] = None
    # marketplace facade: .find_providers(MatchQuery) -> MatchDecision
    marketplace: Any = None
    # chain adapter with .estimate_gas / .chain / native_symbol
    chain_adapter: Any = None
    # paymaster with .quote / .sponsor
    paymaster: Any = None
    fee_token: Any = None  # AssetRef for paymaster
    # verification gateway: .submit_proof(ProofSubmission) -> VerifyOutcome
    verification_gateway: Any = None
    verify_rule: Optional[dict] = None

    def list_tools(self) -> list[dict[str, Any]]:
        """Return JSON-schema tool definitions for Function Calling registration."""
        return list(TOOL_DEFINITIONS)

    def invoke(self, name: str, arguments: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Dispatch a tool by name with a plain dict of arguments.

        Parameters
        ----------
        name:
            One of ``tool_names()`` (e.g. ``novapanda_quote_price``).
        arguments:
            JSON-serializable params matching the tool schema. No raw transaction hex.

        Returns
        -------
        dict
            ``{ok: true, result: ...}`` or ``{ok: false, fault: {...}}``.
        """
        args = dict(arguments or {})
        handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "novapanda_list_tools": lambda _a: _ok(tool_names()),
            "novapanda_quote_price": self._quote_price,
            "novapanda_hold_auction": self._hold_auction,
            "novapanda_split_task": self._split_task,
            "novapanda_run_supply_chain": self._run_supply_chain,
            "novapanda_settlement_escrow": self._escrow,
            "novapanda_settlement_settle": self._settle,
            "novapanda_settlement_refund": self._refund,
            "novapanda_compact_terminal": self._compact_terminal,
            "novapanda_classify_error": self._classify_error,
            "novapanda_discover_providers": self._discover_providers,
            "novapanda_estimate_gas": self._estimate_gas,
            "novapanda_paymaster_sponsor": self._paymaster_sponsor,
            "novapanda_verify_proof": self._verify_proof,
        }
        fn = handlers.get(name)
        if fn is None:
            return _err(
                classify_exception(
                    ValueError(f"unknown tool: {name}")
                )
            )
        try:
            return fn(args)
        except Exception as exc:  # noqa: BLE001
            return _err(classify_exception(exc))

    # ----- handlers -----

    def _quote_price(self, a: dict[str, Any]) -> dict[str, Any]:
        snap = self.pricing.quote(
            PricingInput(
                resource_type=str(a["resource_type"]),
                market_benchmark=PriceQuote(
                    amount=int(a["benchmark_amount"]),
                    currency=str(a.get("currency") or "USD"),
                ),
                load_ratio=float(a.get("load_ratio") or 0.0),
                token_estimate=int(a.get("token_estimate") or 0),
                step_estimate=int(a.get("step_estimate") or 1),
                effective_reputation=(
                    float(a["reputation"]) if a.get("reputation") is not None else None
                ),
                grid_load_ratio=float(a.get("grid_load_ratio") or 0.0),
                queue_length=int(a.get("queue_length") or 0),
            )
        )
        return _ok(
            {
                "amount": snap.price.amount,
                "currency": snap.price.currency,
                "max_response_ms": snap.sla.max_response_ms,
                "complexity_factor": round(snap.complexity_factor, 4),
                "load_factor": round(snap.load_factor, 4),
                "reputation_factor": round(snap.reputation_factor, 4),
                "rationale": snap.rationale[:160],
            }
        )

    def _hold_auction(self, a: dict[str, Any]) -> dict[str, Any]:
        if self.auctioneer is None:
            return _err(
                fault_from_mapping(
                    code="SKILL_MISCONFIGURED",
                    message="auctioneer not configured",
                    recovery=RecoveryAction.ESCALATE_HUMAN,
                    retryable=False,
                    hint="Wire MarketplaceAuctioneer into NovaPandaAgentSkill.auctioneer.",
                )
            )
        from .compact import compact_auction

        tags = tuple(a.get("required_tags") or ())
        spec = TaskSpec(
            goal_id=str(a["goal_id"]),
            resource_type=str(a["resource_type"]),
            payload=a.get("payload") if "payload" in a else {"charge": True},
            budget=PriceQuote(
                amount=int(a["budget_amount"]),
                currency=str(a.get("currency") or "USD"),
            ),
            client_agent_id=str(a["client_agent_id"]),
            max_response_ms=int(a.get("max_response_ms") or 120_000),
            required_tags=tags,
        )
        graph = self.dispatcher.split_task(spec)
        result = self.auctioneer.hold_auction(graph, spec=spec)
        return _ok(compact_auction(result))

    def _split_task(self, a: dict[str, Any]) -> dict[str, Any]:
        steps = tuple(a["steps"]) if a.get("steps") else ()
        spec = TaskSpec(
            goal_id=str(a["goal_id"]),
            resource_type=str(a["resource_type"]),
            payload=a.get("payload") if "payload" in a else {},
            budget=PriceQuote(
                amount=int(a["budget_amount"]),
                currency=str(a.get("currency") or "USD"),
            ),
            client_agent_id=str(a["client_agent_id"]),
            steps=steps,
        )
        graph = self.dispatcher.split_task(spec)
        return _ok(
            compact_graph(graph, include_payloads=bool(a.get("include_payloads")))
        )

    def _run_supply_chain(self, a: dict[str, Any]) -> dict[str, Any]:
        if self.orchestrator is None:
            from .errors import RecoveryAction, fault_from_mapping

            return _err(
                fault_from_mapping(
                    code="SKILL_MISCONFIGURED",
                    message="orchestrator not configured",
                    recovery=RecoveryAction.ESCALATE_HUMAN,
                    retryable=False,
                    hint="Human must wire SupplyChainOrchestrator into NovaPandaAgentSkill.",
                )
            )
        steps = tuple(a["steps"]) if a.get("steps") else ()
        tags = tuple(a.get("required_tags") or ())
        spec = TaskSpec(
            goal_id=str(a["goal_id"]),
            resource_type=str(a["resource_type"]),
            payload=a.get("payload") if "payload" in a else {"ok": True},
            budget=PriceQuote(
                amount=int(a["budget_amount"]),
                currency=str(a.get("currency") or "USD"),
            ),
            client_agent_id=str(a["client_agent_id"]),
            steps=steps,
            required_tags=tags,
        )
        report = self.orchestrator.run(spec)
        compact = compact_orchestration(
            report, include_results=bool(a.get("include_results"))
        )
        if not compact.get("ok"):
            fault = classify_exception(
                RuntimeError(report.error or "orchestration failed")
            )
            return {
                "ok": False,
                "fault": fault.to_dict(),
                "result": compact,
            }
        return _ok(compact)

    def _escrow(self, a: dict[str, Any]) -> dict[str, Any]:
        try:
            handle = self.settlement.escrow(
                str(a["exchange_id"]),
                int(a["amount"]),
                str(a.get("currency") or "USD"),
            )
            return _ok({"handle": handle, "status": "held"})
        except SettlementError as exc:
            return _err(classify_exception(exc))

    def _settle(self, a: dict[str, Any]) -> dict[str, Any]:
        try:
            receipt = self.settlement.settle(str(a["handle"]))
            return _ok(_clip_receipt(receipt))
        except SettlementError as exc:
            return _err(classify_exception(exc))

    def _refund(self, a: dict[str, Any]) -> dict[str, Any]:
        try:
            receipt = self.settlement.refund(str(a["handle"]))
            return _ok(_clip_receipt(receipt))
        except SettlementError as exc:
            return _err(classify_exception(exc))

    def _compact_terminal(self, a: dict[str, Any]) -> dict[str, Any]:
        snap = ExchangeTerminalSnapshot(
            exchange_id=str(a["exchange_id"]),
            state=str(a["state"]),
            client=str(a["client"]),
            provider=str(a["provider"]),
            resource_type=str(a["resource_type"]),
            quantity=int(a["quantity"]),
            vdc_id=a.get("vdc_id"),
            price_amount=int(a["price_amount"]),
            price_currency=str(a.get("price_currency") or "USD"),
            outcome_hint=a.get("outcome_hint"),  # type: ignore[arg-type]
        )
        return _ok(compact_terminal_snapshot(snap))

    def _classify_error(self, a: dict[str, Any]) -> dict[str, Any]:
        return _ok(classify_exception(RuntimeError(str(a["message"]))).to_dict())

    def _discover_providers(self, a: dict[str, Any]) -> dict[str, Any]:
        if self.marketplace is None:
            return _err(
                fault_from_mapping(
                    code="SKILL_MISCONFIGURED",
                    message="marketplace facade not configured",
                    recovery=RecoveryAction.ESCALATE_HUMAN,
                    retryable=False,
                    hint="Wire DefaultMarketplaceFacade into NovaPandaAgentSkill.marketplace.",
                )
            )
        query = MatchQuery(
            resource_type=str(a["resource_type"]),
            quantity=int(a.get("quantity") or 1),
            max_price=PriceQuote(
                amount=int(a["max_price_amount"]),
                currency=str(a.get("currency") or "USD"),
            ),
            max_response_ms=int(a.get("max_response_ms") or 60_000),
            min_reputation=float(a.get("min_reputation") or 0.0),
            required_tags=tuple(a.get("required_tags") or ()),
            client_agent_id=a.get("client_agent_id"),
            limit=int(a.get("limit") or 10),
        )
        decision = self.marketplace.find_providers(query)
        ranked = []
        for c in decision.ranked[:5]:
            ranked.append(
                {
                    "listing_id": c.listing.listing_id,
                    "provider": short_agent_id(c.listing.agent_id),
                    "amount": c.listing.price.amount,
                    "currency": c.listing.price.currency,
                    "score": round(float(c.breakdown.total), 4),
                }
            )
        winner = None
        if decision.winner is not None:
            w = decision.winner
            winner = {
                "listing_id": w.listing.listing_id,
                "provider": short_agent_id(w.listing.agent_id),
                "provider_full": w.listing.agent_id,
                "amount": w.listing.price.amount,
                "score": round(float(w.breakdown.total), 4),
            }
        return _ok(
            {
                "winner": winner,
                "ranked": ranked,
                "reason": (decision.reason or "")[:160],
                "n_ranked": len(decision.ranked),
            }
        )

    def _estimate_gas(self, a: dict[str, Any]) -> dict[str, Any]:
        from novapanda.wallet.types import AssetRef, TransferRequest

        adapter = self.chain_adapter
        fn = self.estimate_gas_fn
        if adapter is None and fn is None:
            return _err(
                fault_from_mapping(
                    code="SKILL_MISCONFIGURED",
                    message="chain adapter not configured",
                    recovery=RecoveryAction.ESCALATE_HUMAN,
                    retryable=False,
                    hint="Wire chain_adapter or estimate_gas_fn for gas estimates.",
                )
            )
        symbol = str(a.get("symbol") or "ETH")
        if adapter is not None:
            asset = AssetRef(chain=adapter.chain, symbol=symbol, decimals=18)
            req = TransferRequest(
                asset=asset,
                to_address=str(a["to_address"]),
                amount=int(a["amount"]),
            )
            quote = adapter.estimate_gas(str(a["from_address"]), req)
        else:
            quote = fn(  # type: ignore[misc]
                str(a["from_address"]),
                str(a["to_address"]),
                int(a["amount"]),
            )
        return _ok(
            {
                "chain_id": quote.chain_id,
                "native_gas_estimate": int(quote.native_gas_estimate),
                "native_symbol": quote.native_symbol,
                "degraded": bool(getattr(quote, "degraded", False)),
                "paymaster_available": bool(
                    getattr(quote, "paymaster_available", False)
                ),
            }
        )

    def _paymaster_sponsor(self, a: dict[str, Any]) -> dict[str, Any]:
        if self.paymaster is None or self.fee_token is None or self.chain_adapter is None:
            return _err(
                fault_from_mapping(
                    code="SKILL_MISCONFIGURED",
                    message="paymaster / fee_token / chain_adapter not configured",
                    recovery=RecoveryAction.ESCALATE_HUMAN,
                    retryable=False,
                    hint="Wire Paymaster + AssetRef fee_token for sponsorship shadow runs.",
                )
            )
        gas_native = int(a["gas_native"])
        q = self.paymaster.quote(
            chain=self.chain_adapter.chain,
            payer_address=str(a["payer_address"]),
            gas_native=gas_native,
            fee_token=self.fee_token,
        )
        receipt = self.paymaster.sponsor(
            chain=self.chain_adapter.chain,
            payer_address=str(a["payer_address"]),
            fee_token=self.fee_token,
            gas_native=gas_native,
            user_op_ref=str(a["user_op_ref"]),
        )
        fee_amt = None
        if getattr(q, "token_fee", None) is not None:
            fee_amt = int(q.token_fee.amount)
        tx = getattr(receipt, "tx_hash", None) or ""
        if isinstance(tx, str) and len(tx) > 18:
            tx = f"{tx[:10]}…{tx[-6:]}"
        return _ok(
            {
                "status": getattr(receipt, "status", "ok"),
                "tx_hash": tx,
                "fee_token_amount": fee_amt,
                "gas_native": gas_native,
                "paymaster_available": True,
            }
        )

    def _verify_proof(self, a: dict[str, Any]) -> dict[str, Any]:
        if self.verification_gateway is None:
            return _err(
                fault_from_mapping(
                    code="SKILL_MISCONFIGURED",
                    message="verification_gateway not configured",
                    recovery=RecoveryAction.ESCALATE_HUMAN,
                    retryable=False,
                    hint="Wire VerificationGateway into NovaPandaAgentSkill.",
                )
            )
        from novapanda.hashing import result_hash_of_json
        from novapanda.verification_gateway.gateway import ProofSubmission

        deliverable = a["deliverable"]
        result_hash = a.get("result_hash") or result_hash_of_json(deliverable)
        rule = self.verify_rule or {
            "schema": {"type": "object", "additionalProperties": True},
        }
        proof_meta = {}
        if a.get("device_id"):
            proof_meta["device_id"] = str(a["device_id"])
        if a.get("tpm_signature"):
            proof_meta["tpm_signature"] = str(a["tpm_signature"])
        outcome = self.verification_gateway.submit_proof(
            ProofSubmission(
                exchange_id=str(a["exchange_id"]),
                vdc_id=str(a["vdc_id"]),
                result_hash=str(result_hash),
                rule_id=str(a.get("rule_id") or "R-skill-default"),
                deliverable=deliverable,
                rule=rule,
                proof_meta=proof_meta or None,
            )
        )
        cred = None
        if outcome.credential is not None:
            c = outcome.credential
            cred = {
                "credential_id": getattr(c, "credential_id", None)
                or getattr(c, "id", None),
                "passed": True,
                "backend": getattr(outcome.backend, "backend_id", None),
            }
            # keep compact — drop signatures/hex
        return _ok(
            {
                "passed": bool(outcome.passed),
                "backend": getattr(outcome.backend, "backend_id", None),
                "reason": (getattr(outcome.backend, "reason", None) or outcome.error or "")[
                    :160
                ],
                "credential": cred,
            }
        )


def _clip_receipt(receipt: dict) -> dict[str, Any]:
    """Strip bulky nested blobs from settlement receipts."""
    keep = ("handle", "status", "exchange_id", "amount", "currency", "rail", "partner")
    out = {k: receipt[k] for k in keep if k in receipt}
    if "tx_hash" in receipt and isinstance(receipt["tx_hash"], str):
        h = receipt["tx_hash"]
        out["tx_hash"] = h if len(h) <= 18 else f"{h[:10]}…{h[-6:]}"
    return out or {"keys": list(receipt.keys())[:8]}
