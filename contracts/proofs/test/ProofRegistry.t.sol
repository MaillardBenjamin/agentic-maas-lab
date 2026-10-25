// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;
import "../src/ProofRegistry.sol";

contract OtherPublisher {
    function attempt(ProofRegistry r) external { r.anchor(bytes32(uint256(1)), bytes32(uint256(2)), 1); }
}

contract ProofRegistryTest {
    function testAnchorAndRead() public {
        ProofRegistry r = new ProofRegistry();
        r.anchor(bytes32(uint256(1)), bytes32(uint256(2)), 1);
        (bytes32 d, uint32 v, uint256 n) = r.proofs(bytes32(uint256(1)));
        require(d == bytes32(uint256(2)) && v == 1 && n > 0);
    }
    function testRepeatedAnchor() public {
        ProofRegistry r = new ProofRegistry();
        r.anchor(bytes32(uint256(1)), bytes32(uint256(2)), 1);
        r.anchor(bytes32(uint256(1)), bytes32(uint256(2)), 1);
    }
    function testConflictingDigestRejected() public {
        ProofRegistry r = new ProofRegistry();
        r.anchor(bytes32(uint256(1)), bytes32(uint256(2)), 1);
        (bool ok,) = address(r).call(abi.encodeCall(r.anchor,(bytes32(uint256(1)), bytes32(uint256(3)), 1)));
        require(!ok);
    }
    function testUnauthorizedRejected() public {
        ProofRegistry r = new ProofRegistry();
        OtherPublisher other = new OtherPublisher();
        (bool ok,) = address(other).call(abi.encodeCall(other.attempt,(r)));
        require(!ok);
    }
}
