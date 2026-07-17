"""真实结算轨 Runner：对接 ExchangeEngine（不改状态机转移表）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from novapanda import state_machine as sm
from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.terms import sign_contract_ack

DeliverFn = Callable[[Any], Any]  # sub.payload -> deliverable


@dataclass
class RealExchangeRunner:
    """Production/testnet ExchangeRunner wrapping ``ExchangeEngine``.

    With local client+provider keys and ``auto_complete=True``, runs
    propose→contract→escrow→deliver→verify→confirm through to SETTLED.
    Client-only mode stops at escrow; poll via ``poll_leg``.

    Agents should not feed raw signed-tx hex here—settlement/wallet adapters
    own broadcast. Prefer ``NovaPandaAgentSkill`` for LLM-facing results.
    """

    engine: ExchangeEngine
    client: Identity
    providers: dict[str, Identity] = field(default_factory=dict)
    rule_id: str = "R-autonomy-default"
    resource_type_default: str = "compute.pipeline"
    auto_complete: bool = True
    verify_rule: Optional[dict] = None
    make_deliverable: Optional[DeliverFn] = None
    # 可选：腿启动后钩子（如链上 escrow 旁路）
    on_leg_started: Optional[Callable[[dict], None]] = None

    def start_leg(
        self,
        *,
        sub,
        provider_agent_id: str,
        client_agent_id: str,
        price: dict,
        correlation_id: str,
    ) -> dict:
        if client_agent_id != self.client.agent_id:
            raise ValueError("client_agent_id mismatch with runner.client")
        provider = self.providers.get(provider_agent_id)
        if provider is None and self.auto_complete:
            raise ValueError(
                f"provider identity not registered for {provider_agent_id[:24]}… "
                "(auto_complete requires local provider key)"
            )

        rtype = getattr(sub, "resource_type", None) or self.resource_type_default
        rule = getattr(sub, "rule_id_hint", None) or self.rule_id
        amount = int(price["amount"])
        currency = str(price.get("currency") or "USD")

        ex = self.engine.propose(
            client=self.client.agent_id,
            provider=provider_agent_id,
            resource_type=rtype,
            quantity=1,
            rule_id=rule,
            price={"amount": amount, "currency": currency},
            idempotency_key=f"{correlation_id}:{sub.sub_id}",
        )
        # 双签合同（provider 密钥可用时）
        self.engine.contract(
            ex.exchange_id,
            party=self.client.agent_id,
            signature=sign_contract_ack(self.client, ex),
        )
        if provider is not None:
            self.engine.contract(
                ex.exchange_id,
                party=provider.agent_id,
                signature=sign_contract_ack(provider, ex),
            )
            self.engine.escrow(ex.exchange_id, amount=amount, currency=currency)
        else:
            # 无 provider 密钥：仅 client ack，等待对端；状态停在 PROPOSED/半合同
            out = {
                "exchange_id": ex.exchange_id,
                "state": self.engine.get(ex.exchange_id).state,
                "provider": provider_agent_id,
                "result": None,
            }
            if self.on_leg_started:
                self.on_leg_started(out)
            return out

        if not self.auto_complete:
            out = {
                "exchange_id": ex.exchange_id,
                "state": sm.ESCROWED,
                "provider": provider_agent_id,
                "result": None,
            }
            if self.on_leg_started:
                self.on_leg_started(out)
            return out

        deliverable = self._deliverable(sub)
        self.engine.deliver(ex.exchange_id, provider, deliverable)
        rule_doc = self.verify_rule or {
            "schema": {"type": "object", "additionalProperties": True},
        }
        self.engine.verify(ex.exchange_id, rule=rule_doc)
        ex2 = self.engine.get(ex.exchange_id)
        if ex2.state == sm.VERIFIED:
            self.engine.confirm(ex.exchange_id, self.client)
        ex3 = self.engine.get(ex.exchange_id)
        vdc_id = ex3.vdc.get("vdc_id") if ex3.vdc else None
        out = {
            "exchange_id": ex3.exchange_id,
            "state": ex3.state,
            "vdc_id": vdc_id,
            "result": deliverable,
            "provider": provider_agent_id,
        }
        if self.on_leg_started:
            self.on_leg_started(out)
        return out

    def poll_leg(self, exchange_id: str) -> dict:
        ex = self.engine.get(exchange_id)
        return {
            "exchange_id": exchange_id,
            "state": ex.state,
            "vdc_id": (ex.vdc or {}).get("vdc_id") if ex.vdc else None,
            "result": ex.deliverable,
        }

    def _deliverable(self, sub) -> Any:
        if self.make_deliverable is not None:
            return self.make_deliverable(sub.payload)
        payload = sub.payload
        if isinstance(payload, dict):
            return dict(payload)
        return {"ok": True, "payload": payload}
