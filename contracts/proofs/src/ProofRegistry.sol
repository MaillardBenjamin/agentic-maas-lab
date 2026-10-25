// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

/// @notice Local demo only. Anchors attestations of data, not truth of a journey.
contract ProofRegistry {
    address public immutable publisher;
    struct Proof { bytes32 digest; uint32 schemaVersion; uint256 blockNumber; }
    mapping(bytes32 => Proof) public proofs;
    event Anchored(bytes32 indexed batchId, bytes32 digest, uint32 schemaVersion);

    constructor() { publisher = msg.sender; }

    function anchor(bytes32 batchId, bytes32 digest, uint32 schemaVersion) external {
        require(msg.sender == publisher, "publisher only");
        require(digest != bytes32(0), "empty digest");
        Proof storage existing = proofs[batchId];
        if (existing.blockNumber != 0) {
            require(existing.digest == digest && existing.schemaVersion == schemaVersion, "conflicting batch");
            return;
        }
        proofs[batchId] = Proof(digest, schemaVersion, block.number);
        emit Anchored(batchId, digest, schemaVersion);
    }
}
