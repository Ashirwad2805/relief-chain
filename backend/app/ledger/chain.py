import json
import time
from app.ledger.merkle import sha256, hash_entry, build_merkle_tree

def create_block(
    previous_block: dict | None,
    entries: list[dict],
    sim_time: float = 0.0
) -> dict:
    """
    Creates a new immutable cryptographic block with previous block hash chaining and Merkle root.
    """
    index = (previous_block["index"] + 1) if previous_block else 0
    prev_hash = previous_block["hash"] if previous_block else "0" * 64

    entry_hashes = [hash_entry(e) for e in entries]
    merkle_root, _ = build_merkle_tree(entry_hashes)

    block_header = {
        "index": index,
        "timestamp": sim_time,
        "previousHash": prev_hash,
        "merkleRoot": merkle_root
    }
    header_str = json.dumps(block_header, sort_keys=True, separators=(',', ':'))
    current_hash = sha256(header_str)

    return {
        "index": index,
        "timestamp": sim_time,
        "previousHash": prev_hash,
        "hash": current_hash,
        "merkleRoot": merkle_root,
        "entries": entries,
        "verified": True,
        "tampered": False
    }

def verify_blockchain(chain: list[dict]) -> dict:
    """
    Cryptographically validates the entire SHA-256 chain and Merkle roots.
    Identifies exact corrupted block if tampering has occurred.
    """
    if not chain:
        return {"valid": True, "corruptedBlock": None, "reason": "Empty chain is valid"}

    # 1. Validate Genesis block
    genesis = chain[0]
    if genesis["index"] != 0 or genesis["previousHash"] != "0" * 64:
        return {"valid": False, "corruptedBlock": 0, "reason": "Invalid genesis block parameters"}

    for i, block in enumerate(chain):
        # A. Check Merkle root recalculation
        entry_hashes = [hash_entry(e) for e in block.get("entries", [])]
        recomputed_root, _ = build_merkle_tree(entry_hashes)
        if recomputed_root.lower() != block["merkleRoot"].lower():
            return {
                "valid": False,
                "corruptedBlock": i,
                "reason": f"Merkle root mismatch in Block #{i}. Payload modified."
            }

        # B. Check block header hash
        header = {
            "index": block["index"],
            "timestamp": block["timestamp"],
            "previousHash": block["previousHash"],
            "merkleRoot": block["merkleRoot"]
        }
        header_str = json.dumps(header, sort_keys=True, separators=(',', ':'))
        recomputed_hash = sha256(header_str)
        if recomputed_hash.lower() != block["hash"].lower():
            return {
                "valid": False,
                "corruptedBlock": i,
                "reason": f"Hash mismatch in Block #{i}. Expected {recomputed_hash[:16]}..., found {block['hash'][:16]}..."
            }

        # C. Check previous hash pointer
        if i > 0:
            prev_block = chain[i - 1]
            if block["previousHash"].lower() != prev_block["hash"].lower():
                return {
                    "valid": False,
                    "corruptedBlock": i,
                    "reason": f"Broken chain link between Block #{i-1} and #{i}."
                }

    return {"valid": True, "corruptedBlock": None, "reason": "All blocks and cryptographic hashes fully verified."}

def tamper_blockchain(chain: list[dict], block_index: int) -> list[dict]:
    """
    Simulates deliberate adversarial tampering of a block to demonstrate detection.
    """
    if not chain or block_index < 0 or block_index >= len(chain):
        return chain

    mutated_chain = [dict(b) for b in chain]
    target = dict(mutated_chain[block_index])

    entries = [dict(e) for e in target.get("entries", [])]
    if entries:
        entries[0]["description"] = "MALICIOUS OVERWRITE: Unauthorized fund redirect to offshore shell entity"
        if "amount" in entries[0]:
            entries[0]["amount"] = 999999999.0
    else:
        entries.append({
            "type": "fund_release",
            "description": "MALICIOUS OVERWRITE: Phantom payment",
            "amount": 50000000.0,
            "entityId": "ATTACKER"
        })

    target["entries"] = entries
    target["tampered"] = True
    target["verified"] = False
    mutated_chain[block_index] = target
    return mutated_chain
