import hashlib
import json
from typing import Any

def sha256(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def hash_entry(entry: dict) -> str:
    """Computes deterministic canonical SHA-256 hash of a ledger entry."""
    canonical_json = json.dumps(entry, sort_keys=True, separators=(',', ':'))
    return sha256(canonical_json)

def build_merkle_tree(leaf_hashes: list[str]) -> tuple[str, list[list[str]]]:
    """
    Constructs a binary Merkle tree from a list of leaf hashes.
    Returns (merkle_root, tree_levels)
    """
    if not leaf_hashes:
        empty_root = sha256("EMPTY_TREE")
        return empty_root, [[empty_root]]

    levels = [leaf_hashes]
    current_level = leaf_hashes

    while len(current_level) > 1:
        next_level = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            if i + 1 < len(current_level):
                right = current_level[i + 1]
            else:
                right = left # duplicate odd node
            combined_hash = sha256(left + right)
            next_level.append(combined_hash)
        levels.append(next_level)
        current_level = next_level

    return current_level[0], levels

def generate_merkle_proof(leaf_hashes: list[str], leaf_index: int) -> dict:
    """
    Generates a cryptographic Merkle audit path for leaf at index leaf_index.
    """
    if leaf_index < 0 or leaf_index >= len(leaf_hashes):
        raise ValueError("Invalid leaf index")

    root, levels = build_merkle_tree(leaf_hashes)
    proof_path = []
    idx = leaf_index

    for level in levels[:-1]:
        is_right = (idx % 2 == 1)
        sibling_idx = idx - 1 if is_right else idx + 1
        if sibling_idx < len(level):
            sibling_hash = level[sibling_idx]
        else:
            sibling_hash = level[idx] # duplicate
        proof_path.append({
            "position": "left" if is_right else "right",
            "hash": sibling_hash
        })
        idx = idx // 2

    return {
        "leafHash": leaf_hashes[leaf_index],
        "merkleRoot": root,
        "leafIndex": leaf_index,
        "proofPath": proof_path
    }

def verify_merkle_proof(leaf_hash: str, proof_path: list[dict], expected_root: str) -> bool:
    """
    Verifies a Merkle proof path against expected root.
    """
    current_hash = leaf_hash
    for step in proof_path:
        sibling = step["hash"]
        if step["position"] == "left":
            current_hash = sha256(sibling + current_hash)
        else:
            current_hash = sha256(current_hash + sibling)
    return current_hash.lower() == expected_root.lower()
