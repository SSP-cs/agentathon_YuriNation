import sqlite3
import os
import json
from backend.config import settings

def get_db_connection():
    os.makedirs(os.path.dirname(settings.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Documents Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        filename TEXT NOT NULL,
        file_type TEXT NOT NULL,
        file_size_kb REAL DEFAULT 0,
        chunk_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Questions & Verification Sessions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS verification_sessions (
        session_id TEXT PRIMARY KEY,
        question TEXT NOT NULL,
        category TEXT DEFAULT 'Policy',
        status TEXT NOT NULL,
        final_answer TEXT,
        overall_confidence REAL DEFAULT 0,
        retry_count INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0,
        total_cost_usd REAL DEFAULT 0,
        total_latency_ms REAL DEFAULT 0,
        is_mock_mode INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Agent Outputs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_outputs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        model_name TEXT NOT NULL,
        answer TEXT NOT NULL,
        latency_ms REAL DEFAULT 0,
        prompt_tokens INTEGER DEFAULT 0,
        completion_tokens INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES verification_sessions(session_id)
    )
    """)

    # Claims Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS claims (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        claim_id TEXT NOT NULL,
        claim_text TEXT NOT NULL,
        status TEXT NOT NULL,
        source_agent TEXT NOT NULL,
        evidence_text TEXT,
        document_name TEXT,
        page_number INTEGER,
        confidence_score REAL DEFAULT 0,
        reasoning TEXT,
        FOREIGN KEY (session_id) REFERENCES verification_sessions(session_id)
    )
    """)

    # Escalations Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS escalations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT UNIQUE NOT NULL,
        reason TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING',
        retry_history_json TEXT,
        reviewer_decision TEXT,
        reviewer_notes TEXT,
        reviewed_by TEXT,
        reviewed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES verification_sessions(session_id)
    )
    """)

    # Comprehensive Audit Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        event_type TEXT NOT NULL,
        summary TEXT NOT NULL,
        details_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Retrieval Cache Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS retrieval_cache (
        cache_key TEXT PRIMARY KEY,
        result_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

init_db()

