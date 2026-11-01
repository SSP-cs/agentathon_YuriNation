"""Audit trail persistence using SQLite for runs, claims, and event traces."""

import sqlite3
import json
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from trustlayer.config import SQLITE_DB_PATH
from trustlayer.schemas import TrustLayerRunResult, ClaimVerdict

def init_audit_db():
    """Create tables for persistent audit logging."""
    with sqlite3.connect(SQLITE_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                decision TEXT NOT NULL,
                status TEXT NOT NULL,
                support_score_a REAL,
                support_score_b REAL,
                agreement TEXT,
                retry_count INTEGER,
                latency_ms REAL,
                final_answer TEXT,
                reason_code TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                agent TEXT NOT NULL,
                claim_text TEXT NOT NULL,
                verdict TEXT NOT NULL,
                evidence_id TEXT,
                quote TEXT,
                reasoning TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                node TEXT NOT NULL,
                message TEXT NOT NULL,
                metadata_json TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
        """)
        conn.commit()

init_audit_db()

def log_event(run_id: str, node: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a timestamped event entry and persist it."""
    ts = datetime.now(timezone.utc).isoformat()
    meta_json = json.dumps(metadata or {})
    try:
        with sqlite3.connect(SQLITE_DB_PATH) as conn:
            conn.execute(
                "INSERT INTO events (run_id, timestamp, node, message, metadata_json) VALUES (?, ?, ?, ?, ?)",
                (run_id, ts, node, message, meta_json)
            )
            conn.commit()
    except Exception:
        pass
    return {"timestamp": ts, "node": node, "message": message, "metadata": metadata or {}}

def save_run(result: TrustLayerRunResult):
    """Persist completed run, claims, and trace into the audit database."""
    now_str = datetime.now(timezone.utc).isoformat()
    reason_code = result.handoff_package.reason_code if result.handoff_package else None

    with sqlite3.connect(SQLITE_DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO runs (
                run_id, question, decision, status,
                support_score_a, support_score_b, agreement,
                retry_count, latency_ms, final_answer, reason_code, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.run_id,
            result.question,
            result.decision,
            result.status,
            result.support_score_a,
            result.support_score_b,
            result.agreement,
            result.retry_count,
            result.latency_ms,
            result.final_answer,
            reason_code,
            now_str
        ))

        # Insert claims
        for claim in result.claims:
            cur.execute("""
                INSERT INTO claims (run_id, agent, claim_text, verdict, evidence_id, quote, reasoning)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                result.run_id,
                "Auditor",
                claim.claim,
                claim.verdict,
                claim.evidence_id,
                claim.quote,
                claim.reasoning
            ))

        # Insert events that weren't already written
        for ev in result.event_trace:
            cur.execute("""
                INSERT INTO events (run_id, timestamp, node, message, metadata_json)
                VALUES (?, ?, ?, ?, ?)
            """, (
                result.run_id,
                ev.get("timestamp", now_str),
                ev.get("node", "system"),
                ev.get("message", ""),
                json.dumps(ev.get("metadata", {}))
            ))

        conn.commit()

def get_runs(limit: int = 50, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve historical runs with optional status filtering."""
    with sqlite3.connect(SQLITE_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        if status_filter:
            cur.execute("SELECT * FROM runs WHERE status = ? ORDER BY created_at DESC LIMIT ?", (status_filter, limit))
        else:
            cur.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]

def get_run_details(run_id: str) -> Optional[Dict[str, Any]]:
    """Fetch complete run record including claims and event trace."""
    with sqlite3.connect(SQLITE_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        run_row = cur.fetchone()
        if not run_row:
            return None

        cur.execute("SELECT * FROM claims WHERE run_id = ?", (run_id,))
        claims_rows = cur.fetchall()

        cur.execute("SELECT * FROM events WHERE run_id = ? ORDER BY id ASC", (run_id,))
        events_rows = cur.fetchall()

        run_dict = dict(run_row)
        run_dict["claims"] = [dict(c) for c in claims_rows]
        run_dict["events"] = [
            {
                "timestamp": e["timestamp"],
                "node": e["node"],
                "message": e["message"],
                "metadata": json.loads(e["metadata_json"]) if e["metadata_json"] else {}
            }
            for e in events_rows
        ]
        return run_dict

