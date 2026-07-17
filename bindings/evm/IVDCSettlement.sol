// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @title IVDCSettlement — NovaPanda NP-SETTLE EVM rail (interface)
/// @notice On-chain escrow + timeout refund. CORE exchange SM stays off-chain (ADR-0002).
/// @dev Maps loosely to Create / Verify / Settle / Archive narrative:
///      createVDC → FUNDED; fulfillVDCWithProof → FULFILLED; settlePayment → SETTLED;
///      initiateDispute → DISPUTED; refundIfTimedOut → REFUNDED.
interface IVDCSettlement {
    enum Status {
        None,
        Funded,
        Fulfilled,
        Settled,
        Disputed,
        Refunded
    }

    struct VDCRecord {
        bytes32 exchangeId;
        address client;
        address provider;
        uint256 amount;
        uint64 deliverDeadline;
        uint64 verifyDeadline;
        bytes32 resultHash;
        bytes32 credentialId;
        address verifier;
        Status status;
    }

    event VDCCreated(bytes32 indexed exchangeId, address client, address provider, uint256 amount);
    event VDCFulfilled(bytes32 indexed exchangeId, bytes32 resultHash, bytes32 credentialId, address verifier);
    event VDCSettled(bytes32 indexed exchangeId, address provider, uint256 amount);
    event VDCDisputed(bytes32 indexed exchangeId, address by, string reason);
    event VDCRefunded(bytes32 indexed exchangeId, address client, uint256 amount);

    function createVDC(
        bytes32 exchangeId,
        address provider,
        uint64 deliverDeadline,
        uint64 verifyDeadline
    ) external payable;

    function fulfillVDCWithProof(
        bytes32 exchangeId,
        bytes32 resultHash,
        bytes32 credentialId,
        address verifier
    ) external;

    function settlePayment(bytes32 exchangeId, bytes32 credentialId) external;

    function initiateDispute(bytes32 exchangeId, string calldata reason) external;

    function resolveDispute(bytes32 exchangeId, bool payProvider) external;

    /// @notice Permissionless timeout release when still Funded past deadlines.
    function refundIfTimedOut(bytes32 exchangeId) external;

    function getVDC(bytes32 exchangeId) external view returns (VDCRecord memory);
}
