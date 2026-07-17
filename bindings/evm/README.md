# EVM Settlement Rail (NP-SETTLE)

Prototype Solidity binding for NovaPanda **settlement as adapter** ([ADR-0002](../../decisions/0002-settlement-as-adaptor-not-core.md)).

| Contract | Role |
|----------|------|
| `IVDCSettlement.sol` | Interface: `createVDC`, `fulfillVDCWithProof`, `settlePayment`, `initiateDispute`, `refundIfTimedOut` |
| `VDCSettlement.sol` | Escrow + trusted verifier gate + permissionless timeout refund |

Off-chain twin (CI without Foundry): `novapanda.verification_gateway.evm_rail.EvmSettlementRail`.

CORE exchange state machine remains in Python (`novapanda.state_machine`); this rail only moves value.
