"""
ReliefChain Append-Only Event Store (A3, A5 fix)

Provides deterministic event sourcing:
- Immutable append-only log of all simulation and operational events
- Derived state replay
- Snapshot checkpointing
"""
import json
import time
import hashlib
import sqlite3
from typing import Any
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "reliefchain_events.db"

class EventStore:
    def __init__(self, db_path: Path | str = DB_PATH):
        self.db_path = str(db_path)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS event_log (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    sim_time REAL NOT NULL,
                    ts REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    correlation_id TEXT,
                    payload TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    hash TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    seq INTEGER PRIMARY KEY,
                    sim_time REAL NOT NULL,
                    ts REAL NOT NULL,
                    state_json TEXT NOT NULL
                )
            """)
            conn.commit()

    def append(self, event_type: str, payload: dict[str, Any], sim_time: float, correlation_id: str | None = None) -> int:
        payload_str = json.dumps(payload, sort_keys=True)
        ts = time.time()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT hash FROM event_log ORDER BY seq DESC LIMIT 1")
            row = cursor.fetchone()
            prev_hash = row[0] if row else "0" * 64

            # Calculate SHA-256 over chain
            hasher = hashlib.sha256()
            hasher.update(prev_hash.encode())
            hasher.update(f"{sim_time}:{event_type}:{payload_str}".encode())
            curr_hash = hasher.hexdigest()

            cursor.execute("""
                INSERT INTO event_log (sim_time, ts, event_type, correlation_id, payload, prev_hash, hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (sim_time, ts, event_type, correlation_id, payload_str, prev_hash, curr_hash))
            seq = cursor.lastrowid
            conn.commit()
            return seq

    def get_events(self, since_seq: int = 0, limit: int = 1000) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT seq, sim_time, ts, event_type, correlation_id, payload, hash
                FROM event_log
                WHERE seq > ?
                ORDER BY seq ASC
                LIMIT ?
            """, (since_seq, limit))
            rows = cursor.fetchall()
            return [
                {
                    "seq": r[0],
                    "sim_time": r[1],
                    "ts": r[2],
                    "event_type": r[3],
                    "correlation_id": r[4],
                    "payload": json.loads(r[5]),
                    "hash": r[6],
                }
                for r in rows
            ]

    def save_snapshot(self, seq: int, sim_time: float, state: dict[str, Any]):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO snapshots (seq, sim_time, ts, state_json)
                VALUES (?, ?, ?, ?)
            """, (seq, sim_time, time.time(), json.dumps(state)))
            conn.commit()

    def get_latest_snapshot(self) -> tuple[int, float, dict[str, Any]] | None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT seq, sim_time, state_json FROM snapshots ORDER BY seq DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return None
            return row[0], row[1], json.loads(row[2])

# Default singleton instance
event_store = EventStore()
