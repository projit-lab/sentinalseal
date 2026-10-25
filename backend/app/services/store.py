"""
SentinelSeal storage — a small SQLite store for approvers and payments.

Payments are stored as JSON documents keyed by payment_id, so the API can
return exactly what the front end reads (see docs/FRONTEND_SPEC fields).
SQLite survives a server restart, unlike the in-memory session store.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = Path(os.environ.get("SENTINELSEAL_DATA_DIR", BACKEND_DIR / "data"))


class Store:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._lock = threading.Lock()
        self.set_path(db_path or DATA_DIR / "sentinelseal.db")

    def set_path(self, db_path: Path) -> None:
        """Point the store at a database file (tests use a temp file)."""
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS approvers (approver_id TEXT PRIMARY KEY, doc TEXT NOT NULL)"
            )
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS payments (payment_id TEXT PRIMARY KEY, created_at TEXT, doc TEXT NOT NULL)"
            )
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL)"
            )
            self._conn.commit()

    # ── approvers ──────────────────────────────────────────────────────
    def get_approver(self, approver_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT doc FROM approvers WHERE approver_id = ?", (approver_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def save_approver(self, doc: Dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO approvers (approver_id, doc) VALUES (?, ?)",
                (doc["approver_id"], json.dumps(doc)),
            )
            self._conn.commit()

    def list_approvers(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT doc FROM approvers ORDER BY approver_id").fetchall()
        return [json.loads(r[0]) for r in rows]

    # ── payments ───────────────────────────────────────────────────────
    def next_payment_id(self) -> str:
        with self._lock:
            row = self._conn.execute("SELECT value FROM counters WHERE name = 'payment'").fetchone()
            value = (row[0] if row else 1000) + 1
            self._conn.execute(
                "INSERT OR REPLACE INTO counters (name, value) VALUES ('payment', ?)", (value,)
            )
            self._conn.commit()
        return f"p-{value}"

    def get_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT doc FROM payments WHERE payment_id = ?", (payment_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def save_payment(self, doc: Dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO payments (payment_id, created_at, doc) VALUES (?, ?, ?)",
                (doc["payment_id"], doc["created_at"], json.dumps(doc)),
            )
            self._conn.commit()

    def list_payments(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT doc FROM payments ORDER BY created_at DESC"
            ).fetchall()
        return [json.loads(r[0]) for r in rows]


store = Store()
