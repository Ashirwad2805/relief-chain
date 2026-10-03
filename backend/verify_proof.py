#!/usr/bin/env python3
"""
Independent Standalone Merkle Proof Verifier CLI
Usage:
    python verify_proof.py --leaf <hash> --proof <json_path_or_string> --root <hash>
    python verify_proof.py --demo
"""
import sys
import json
import argparse
import hashlib

def sha256(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def verify_proof(leaf_hash: str, proof_path: list[dict], expected_root: str) -> bool:
    current = leaf_hash
    for step in proof_path:
        sibling = step["hash"]
        pos = step.get("position", "right")
        if pos == "left":
            current = sha256(sibling + current)
        else:
            current = sha256(current + sibling)
    return current.lower() == expected_root.lower()

def run_self_test():
    print("=== RELIEFCHAIN MERKLE PROOF SELF-TEST ===")
    # Construct a 4-leaf Merkle Tree
    leaf_a = sha256("TX_1: PLEDGE 50,000,000 INR")
    leaf_b = sha256("TX_2: ALLOCATE AMB-01 -> INC-001 -> KEM")
    leaf_c = sha256("TX_3: CONFIRM DELIVERY 500 IV FLUIDS")
    leaf_d = sha256("TX_4: ICU ADMISSION CONFIRMED")

    node_ab = sha256(leaf_a + leaf_b)
    node_cd = sha256(leaf_c + leaf_d)
    root = sha256(node_ab + node_cd)

    print(f"Merkle Root: {root}")
    print(f"Testing Leaf B: {leaf_b}")

    # Proof for leaf B: sibling is leaf_a on left, next sibling is node_cd on right
    proof_for_b = [
        {"position": "left", "hash": leaf_a},
        {"position": "right", "hash": node_cd}
    ]

    is_valid = verify_proof(leaf_b, proof_for_b, root)
    print(f"Proof Verification Result: {'PASS (Cryptographically Valid)' if is_valid else 'FAIL'}")

    # Adversarial test
    tampered_leaf = sha256("TX_2: CORRUPTED DATA")
    is_tampered_valid = verify_proof(tampered_leaf, proof_for_b, root)
    print(f"Tampered Payload Rejection: {'PASS (Rejected as expected)' if not is_tampered_valid else 'FAIL'}")

    return 0 if (is_valid and not is_tampered_valid) else 1

def main():
    parser = argparse.ArgumentParser(description="ReliefChain Independent Merkle Proof Verifier")
    parser.add_argument("--demo", action="store_true", help="Run cryptographic self-test")
    parser.add_argument("--leaf", type=str, help="Leaf SHA-256 hash")
    parser.add_argument("--proof", type=str, help="JSON string or file path containing proofPath array")
    parser.add_argument("--root", type=str, help="Expected Merkle root hash")

    args = parser.parse_args()

    if args.demo or not (args.leaf and args.proof and args.root):
        sys.exit(run_self_test())

    try:
        if args.proof.startswith("["):
            path = json.loads(args.proof)
        else:
            with open(args.proof, 'r') as f:
                path = json.load(f)

        valid = verify_proof(args.leaf, path, args.root)
        if valid:
            print(json.dumps({"status": "SUCCESS", "verified": True, "message": "Cryptographic proof matches root"}))
            sys.exit(0)
        else:
            print(json.dumps({"status": "FAILURE", "verified": False, "message": "Hash does not resolve to Merkle root"}))
            sys.exit(2)
    except Exception as e:
        print(json.dumps({"status": "ERROR", "error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
