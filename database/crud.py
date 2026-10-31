import json
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from database.db import get_db_connection
from backend.schemas import (
    ClaimItem, AgentResponse, AuditorResult, VerificationDecision,
    RetrievedChunk, VerificationResponse, DocumentMeta, DashboardMetrics
)

def create_audit_log(session_id: Optional[str], event_type: str, summary: str, details: Optional[Dict[str, Any]] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    details_str = json.dumps(details or {}, ensure_ascii=False)
    cursor.execute("""
    INSERT INTO audit_logs (session_id, event_type, summary, details_json)
    VALUES (?, ?, ?, ?)
    """, (session_id, event_type, summary, details_str))
    conn.commit()
    conn.close()

def save_document_record(doc_id: str, filename: str, file_type: str, file_size_kb: float, chunk_count: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO documents (id, filename, file_type, file_size_kb, chunk_count)
    VALUES (?, ?, ?, ?, ?)
    """, (doc_id, filename, file_type, file_size_kb, chunk_count))
    conn.commit()
    conn.close()
    create_audit_log(None, "DOCUMENT_INDEXED", f"Indexed document '{filename}' with {chunk_count} passages", {
        "doc_id": doc_id, "filename": filename, "chunks": chunk_count
    })

def delete_document_record(doc_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT filename FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    filename = row["filename"] if row else doc_id
    cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()
    create_audit_log(None, "DOCUMENT_DELETED", f"Deleted document '{filename}'", {"doc_id": doc_id})

def list_documents() -> List[DocumentMeta]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents ORDER BY created_at DESC")
    rows = cursor.fetchall()
    docs = [
        DocumentMeta(
            id=row["id"],
            filename=row["filename"],
            file_type=row["file_type"],
            file_size_kb=float(row["file_size_kb"]),
            chunk_count=int(row["chunk_count"]),
            upload_time=str(row["created_at"])
        )
        for row in rows
    ]
    conn.close()
    return docs

def save_verification_session(
    session_id: str,
    question: str,
    category: str,
    status: str,
    final_answer: Optional[str],
    overall_confidence: float,
    retry_count: int,
    total_tokens: int,
    total_cost_usd: float,
    total_latency_ms: float,
    is_mock_mode: bool,
    agent_a: AgentResponse,
    agent_b: AgentResponse,
    auditor: AuditorResult,
    claims: List[ClaimItem],
    retry_history: List[dict]
):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO verification_sessions (
        session_id, question, category, status, final_answer, overall_confidence,
        retry_count, total_tokens, total_cost_usd, total_latency_ms, is_mock_mode
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id, question, category, status, final_answer, overall_confidence,
        retry_count, total_tokens, total_cost_usd, total_latency_ms, 1 if is_mock_mode else 0
    ))

    # Save Agent A output
    cursor.execute("""
    INSERT INTO agent_outputs (session_id, agent_id, provider, model_name, answer, latency_ms, prompt_tokens, completion_tokens)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (session_id, agent_a.agent_id, agent_a.provider, agent_a.model_name, agent_a.answer, agent_a.latency_ms, agent_a.prompt_tokens, agent_a.completion_tokens))

    # Save Agent B output
    cursor.execute("""
    INSERT INTO agent_outputs (session_id, agent_id, provider, model_name, answer, latency_ms, prompt_tokens, completion_tokens)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (session_id, agent_b.agent_id, agent_b.provider, agent_b.model_name, agent_b.answer, agent_b.latency_ms, agent_b.prompt_tokens, agent_b.completion_tokens))

    # Save Claims
    for c in claims:
        cursor.execute("""
        INSERT INTO claims (
            session_id, claim_id, claim_text, status, source_agent, evidence_text,
            document_name, page_number, confidence_score, reasoning
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, c.claim_id, c.text, c.status.value if hasattr(c.status, 'value') else str(c.status),
            c.source_agent, c.evidence_text, c.document_name, c.page_number, c.confidence_score, c.reasoning
        ))

    # If Escalated, create escalation record
    if status == "ESCALATED_HUMAN_REVIEW":
        cursor.execute("""
        INSERT OR IGNORE INTO escalations (session_id, reason, retry_history_json, status)
        VALUES (?, ?, ?, 'PENDING')
        """, (session_id, auditor.auditor_explanation or "Unsupported claims or agent disagreement after retries", json.dumps(retry_history)))

    conn.commit()
    conn.close()

    # Log verification event
    create_audit_log(session_id, "VERIFICATION_COMPLETED", f"Question verdict: {status} (Claims: {len(claims)}, Retries: {retry_count})", {
        "status": status,
        "confidence": overall_confidence,
        "supported_claims": auditor.supported_claims,
        "unsupported_claims": auditor.unsupported_claims,
        "total_tokens": total_tokens
    })

def record_escalation_review(session_id: str, decision: str, notes: str, reviewer: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cursor.execute("""
    UPDATE escalations
    SET status = ?, reviewer_decision = ?, reviewer_notes = ?, reviewed_by = ?, reviewed_at = ?
    WHERE session_id = ?
    """, (decision, decision, notes, reviewer, now, session_id))

    # Also update verification session status if approved or rejected
    new_session_status = "HUMAN_APPROVED" if decision == "APPROVE" else "HUMAN_REJECTED"
    if decision == "REQUEST_EVIDENCE":
        new_session_status = "EVIDENCE_REQUESTED"

    cursor.execute("""
    UPDATE verification_sessions
    SET status = ?
    WHERE session_id = ?
    """, (new_session_status, session_id))

    conn.commit()
    conn.close()

    create_audit_log(session_id, "HUMAN_REVIEW_DECIDED", f"Supervisor '{reviewer}' set escalation verdict to {decision}", {
        "decision": decision,
        "notes": notes,
        "reviewer": reviewer
    })

def get_pending_escalations() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT e.session_id, e.reason, e.status as esc_status, e.retry_history_json, e.created_at,
           v.question, v.overall_confidence, v.retry_count, v.is_mock_mode
    FROM escalations e
    JOIN verification_sessions v ON e.session_id = v.session_id
    WHERE e.status = 'PENDING'
    ORDER BY e.created_at DESC
    """)
    rows = cursor.fetchall()
    
    escalations = []
    for r in rows:
        session_id = r["session_id"]
        # Fetch agents
        cursor.execute("SELECT agent_id, model_name, answer FROM agent_outputs WHERE session_id = ?", (session_id,))
        agents = cursor.fetchall()
        agent_a = next((a["answer"] for a in agents if a["agent_id"] == "agent_a"), "")
        agent_b = next((a["answer"] for a in agents if a["agent_id"] == "agent_b"), "")

        # Fetch unsupported claims
        cursor.execute("SELECT claim_id, claim_text, status, source_agent, reasoning, confidence_score, evidence_text, document_name, page_number FROM claims WHERE session_id = ?", (session_id,))
        claims = [dict(c) for c in cursor.fetchall()]

        escalations.append({
            "session_id": session_id,
            "question": r["question"],
            "reason": r["reason"],
            "created_at": str(r["created_at"]),
            "retry_count": r["retry_count"],
            "confidence": r["overall_confidence"],
            "agent_a_answer": agent_a,
            "agent_b_answer": agent_b,
            "claims": claims,
            "retry_history": json.loads(r["retry_history_json"] or "[]")
        })

    conn.close()
    return escalations

def get_audit_logs(limit: int = 100, search: Optional[str] = None, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM audit_logs WHERE 1=1"
    params = []

    if event_type and event_type != "ALL":
        query += " AND event_type = ?"
        params.append(event_type)

    if search:
        query += " AND (summary LIKE ? OR session_id LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "session_id": r["session_id"],
            "event_type": r["event_type"],
            "summary": r["summary"],
            "details": json.loads(r["details_json"] or "{}"),
            "created_at": str(r["created_at"])
        })
    conn.close()
    return results

def get_session_details(session_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM verification_sessions WHERE session_id = ?", (session_id,))
    v_row = cursor.fetchone()
    if not v_row:
        conn.close()
        return None

    # Agents
    cursor.execute("SELECT * FROM agent_outputs WHERE session_id = ?", (session_id,))
    agents = [dict(a) for a in cursor.fetchall()]

    # Claims
    cursor.execute("SELECT * FROM claims WHERE session_id = ?", (session_id,))
    claims = [dict(c) for c in cursor.fetchall()]

    # Escalation
    cursor.execute("SELECT * FROM escalations WHERE session_id = ?", (session_id,))
    esc = cursor.fetchone()
    esc_dict = dict(esc) if esc else None

    conn.close()
    return {
        "session": dict(v_row),
        "agents": agents,
        "claims": claims,
        "escalation": esc_dict
    }

def get_dashboard_metrics() -> DashboardMetrics:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM verification_sessions")
    total_q = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM verification_sessions WHERE status IN ('VERIFIED_RELEASED', 'HUMAN_APPROVED')")
    verified_q = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM verification_sessions WHERE status IN ('ESCALATED_HUMAN_REVIEW', 'HUMAN_REJECTED', 'EVIDENCE_REQUESTED')")
    escalated_q = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM claims WHERE status IN ('UNSUPPORTED', 'CONTRADICTED')")
    unsupported_claims = cursor.fetchone()[0] or 0

    cursor.execute("SELECT AVG(total_latency_ms), AVG(total_tokens), SUM(total_cost_usd) FROM verification_sessions")
    stats = cursor.fetchone()
    avg_latency = round(stats[0] or 0, 1)
    avg_tokens = round(stats[1] or 0, 1)
    total_cost = round(stats[2] or 0.0, 4)

    # Hallucination prevention rate = unsupported claims successfully caught / total questions
    prevention_rate = round((unsupported_claims / max(1, total_q)) * 100, 1)

    conn.close()
    return DashboardMetrics(
        total_questions=total_q,
        verified_answers=verified_q,
        escalated_questions=escalated_q,
        unsupported_claims_caught=unsupported_claims,
        avg_response_time_ms=avg_latency,
        avg_token_usage=avg_tokens,
        total_cost_usd=total_cost,
        hallucination_prevention_rate=prevention_rate
    )
