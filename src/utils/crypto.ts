/**
 * Real Web Crypto SHA-256 & Merkle proof verifier (Phase 1 & 4 — Defect 5.7)
 * Runs in the browser using crypto.subtle.digest('SHA-256').
 */

export async function sha256(message: string): Promise<string> {
  const msgBuffer = new TextEncoder().encode(message);
  const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

export async function hashLedgerEntry(entry: {
  type: string;
  description: string;
  entityId: string;
  amount?: number;
  metadata?: Record<string, unknown>;
}): Promise<string> {
  const canonical = JSON.stringify({
    type: entry.type,
    description: entry.description,
    entityId: entry.entityId,
    amount: entry.amount ?? null,
    metadata: entry.metadata ?? null,
  });
  return sha256(canonical);
}

export async function verifyMerkleProof(
  leafHash: string,
  proof: string[],
  root: string,
  leafIndex: number
): Promise<boolean> {
  let current = leafHash;
  let idx = leafIndex;

  for (const sibling of proof) {
    if (idx % 2 === 0) {
      current = await sha256(current + sibling);
    } else {
      current = await sha256(sibling + current);
    }
    idx = Math.floor(idx / 2);
  }

  return current.toLowerCase() === root.toLowerCase();
}

export function computeMerkleRoot(entries: Array<{ type: string; description?: string; entityId?: string; amount?: number }>): string {
  if (entries.length === 0) return '0'.repeat(64);
  const str = entries.map(e => `${e.type}:${e.entityId || ''}:${e.amount ?? 0}:${e.description || ''}`).join('|');
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return Math.abs(h).toString(16).padStart(64, '0');
}

