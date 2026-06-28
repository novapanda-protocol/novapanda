"""测试辅助：contract 双签等公共流程。"""

from troodon.exchange import ExchangeEngine
from troodon.identity import Identity
from troodon.sdk import TroodonClient
from troodon.terms import sign_contract_ack


def ack_contract(engine: ExchangeEngine, exchange_id: str, party: Identity):
    ex = engine.get(exchange_id)
    return engine.contract(
        exchange_id, party=party.agent_id, signature=sign_contract_ack(party, ex),
    )


def dual_contract_engine(
    engine: ExchangeEngine, exchange_id: str, client: Identity, provider: Identity,
):
    ack_contract(engine, exchange_id, client)
    return ack_contract(engine, exchange_id, provider)


def dual_contract_sdk(client: TroodonClient, provider: TroodonClient, exchange_id: str):
    client.contract(exchange_id)
    return provider.contract(exchange_id)
