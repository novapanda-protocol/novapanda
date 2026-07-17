// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {IVDCSettlement} from "./IVDCSettlement.sol";

/// @title VDCSettlement — prototype escrow rail for NovaPanda Agent networks
/// @notice Funds are locked until: (a) verifier-attested fulfill + settle, or
///         (b) arbitrator dispute resolution, or (c) permissionless timeout refund.
/// @dev Verification Gateway runs off-chain; only its attestation id + trusted verifier
///      address are anchored here to avoid putting deliverable bytes on-chain.
contract VDCSettlement is IVDCSettlement {
    address public immutable arbitrator;
    mapping(address => bool) public trustedVerifiers;
    mapping(bytes32 => VDCRecord) private _vdcs;

    error Exists();
    error BadAmount();
    error BadStatus();
    error Unauthorized();
    error UntrustedVerifier();
    error MissingProof();
    error CredentialMismatch();
    error NotTimedOut();

    constructor(address arbitrator_, address[] memory initialVerifiers) {
        require(arbitrator_ != address(0), "arb");
        arbitrator = arbitrator_;
        for (uint256 i = 0; i < initialVerifiers.length; i++) {
            trustedVerifiers[initialVerifiers[i]] = true;
        }
    }

    function setTrustedVerifier(address verifier, bool trusted) external {
        if (msg.sender != arbitrator) revert Unauthorized();
        trustedVerifiers[verifier] = trusted;
    }

    function createVDC(
        bytes32 exchangeId,
        address provider,
        uint64 deliverDeadline,
        uint64 verifyDeadline
    ) external payable override {
        if (_vdcs[exchangeId].status != Status.None) revert Exists();
        if (msg.value == 0 || provider == address(0)) revert BadAmount();

        _vdcs[exchangeId] = VDCRecord({
            exchangeId: exchangeId,
            client: msg.sender,
            provider: provider,
            amount: msg.value,
            deliverDeadline: deliverDeadline,
            verifyDeadline: verifyDeadline,
            resultHash: bytes32(0),
            credentialId: bytes32(0),
            verifier: address(0),
            status: Status.Funded
        });

        emit VDCCreated(exchangeId, msg.sender, provider, msg.value);
    }

    function fulfillVDCWithProof(
        bytes32 exchangeId,
        bytes32 resultHash,
        bytes32 credentialId,
        address verifier
    ) external override {
        VDCRecord storage r = _vdcs[exchangeId];
        if (r.status != Status.Funded) revert BadStatus();
        if (msg.sender != r.provider && msg.sender != arbitrator) revert Unauthorized();
        if (!trustedVerifiers[verifier]) revert UntrustedVerifier();
        if (resultHash == bytes32(0) || credentialId == bytes32(0)) revert MissingProof();

        r.resultHash = resultHash;
        r.credentialId = credentialId;
        r.verifier = verifier;
        r.status = Status.Fulfilled;

        emit VDCFulfilled(exchangeId, resultHash, credentialId, verifier);
    }

    function settlePayment(bytes32 exchangeId, bytes32 credentialId) external override {
        VDCRecord storage r = _vdcs[exchangeId];
        if (r.status != Status.Fulfilled && r.status != Status.Disputed) revert BadStatus();
        if (credentialId != bytes32(0) && r.credentialId != credentialId) revert CredentialMismatch();
        // Client, provider, or arbitrator may trigger release after fulfill/dispute-settle path.
        if (msg.sender != r.client && msg.sender != r.provider && msg.sender != arbitrator) {
            revert Unauthorized();
        }
        // If Disputed, only arbitrator may settle via resolveDispute — keep settlePayment for Fulfilled.
        if (r.status == Status.Disputed) revert BadStatus();

        uint256 amount = r.amount;
        address provider = r.provider;
        r.status = Status.Settled;
        r.amount = 0;

        (bool ok, ) = provider.call{value: amount}("");
        require(ok, "pay");
        emit VDCSettled(exchangeId, provider, amount);
    }

    function initiateDispute(bytes32 exchangeId, string calldata reason) external override {
        VDCRecord storage r = _vdcs[exchangeId];
        if (r.status != Status.Fulfilled) revert BadStatus();
        if (msg.sender != r.client && msg.sender != r.provider) revert Unauthorized();
        r.status = Status.Disputed;
        emit VDCDisputed(exchangeId, msg.sender, reason);
    }

    function resolveDispute(bytes32 exchangeId, bool payProvider) external override {
        VDCRecord storage r = _vdcs[exchangeId];
        if (r.status != Status.Disputed) revert BadStatus();
        if (msg.sender != arbitrator) revert Unauthorized();

        uint256 amount = r.amount;
        address payee = payProvider ? r.provider : r.client;
        r.status = payProvider ? Status.Settled : Status.Refunded;
        r.amount = 0;

        (bool ok, ) = payee.call{value: amount}("");
        require(ok, "pay");
        if (payProvider) {
            emit VDCSettled(exchangeId, payee, amount);
        } else {
            emit VDCRefunded(exchangeId, payee, amount);
        }
    }

    function refundIfTimedOut(bytes32 exchangeId) external override {
        VDCRecord storage r = _vdcs[exchangeId];
        if (r.status != Status.Funded) revert BadStatus();

        bool overdue = false;
        if (r.deliverDeadline != 0 && block.timestamp > r.deliverDeadline) overdue = true;
        if (r.verifyDeadline != 0 && block.timestamp > r.verifyDeadline) overdue = true;
        if (!overdue) revert NotTimedOut();

        uint256 amount = r.amount;
        address client = r.client;
        r.status = Status.Refunded;
        r.amount = 0;

        (bool ok, ) = client.call{value: amount}("");
        require(ok, "refund");
        emit VDCRefunded(exchangeId, client, amount);
    }

    function getVDC(bytes32 exchangeId) external view override returns (VDCRecord memory) {
        return _vdcs[exchangeId];
    }
}
