from typing import Dict, Any, List
from database.db import get_db_connection

def calculate_comprehensive_metrics() -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()

    # Total questions
    cursor.execute("SELECT COUNT(*) FROM verification_sessions")
    total_q = cursor.fetchone()[0] or 0

    # Verified released
    cursor.execute("SELECT COUNT(*) FROM verification_sessions WHERE status = 'VERIFIED_RELEASED'")
    verified_count = cursor.fetchone()[0] or 0

    # Escalated count
    cursor.execute("SELECT COUNT(*) FROM verification_sessions WHERE status = 'ESCALATED_HUMAN_REVIEW'")
    escalated_count = cursor.fetchone()[0] or 0

    # Human approved / rejected
    cursor.execute("SELECT COUNT(*) FROM verification_sessions WHERE status = 'HUMAN_APPROVED'")
    human_approved = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM verification_sessions WHERE status = 'HUMAN_REJECTED'")
    human_rejected = cursor.fetchone()[0] or 0

    # Claims breakdown
    cursor.execute("SELECT COUNT(*) FROM claims")
    total_claims = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM claims WHERE status = 'SUPPORTED'")
    supported_claims = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM claims WHERE status IN ('UNSUPPORTED', 'INSUFFICIENT_EVIDENCE')")
    unsupported_claims = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM claims WHERE status = 'CONTRADICTED'")
    contradicted_claims = cursor.fetchone()[0] or 0

    # Safety check: Unsupported claims in released answers
    # This should be 0 in a properly functioning verification system
    cursor.execute("""
    SELECT COUNT(*) FROM claims c
    JOIN verification_sessions v ON c.session_id = v.session_id
    WHERE v.status = 'VERIFIED_RELEASED' AND c.status IN ('UNSUPPORTED', 'CONTRADICTED')
    """)
    unsupported_incorrectly_released = cursor.fetchone()[0] or 0

    # Performance averages
    cursor.execute("SELECT AVG(total_latency_ms), AVG(total_tokens), SUM(total_cost_usd), AVG(retry_count) FROM verification_sessions")
    row = cursor.fetchone()
    avg_latency = round(row[0] or 0.0, 1)
    avg_tokens = round(row[1] or 0.0, 1)
    total_cost = round(row[2] or 0.0, 4)
    avg_retries = round(row[3] or 0.0, 2)

    # Escalation rate
    esc_rate = round((escalated_count / max(1, total_q)) * 100, 1) if total_q > 0 else 0.0
    
    # Catch rate
    hallucination_catch_rate = 100.0 if (unsupported_claims + contradicted_claims) > 0 and unsupported_incorrectly_released == 0 else 0.0

    conn.close()

    return {
        "total_questions_processed": total_q,
        "verified_answers_released": verified_count,
        "escalated_to_human": escalated_count,
        "human_approved": human_approved,
        "human_rejected": human_rejected,
        "total_claims_audited": total_claims,
        "supported_claims": supported_claims,
        "unsupported_claims_caught": unsupported_claims + contradicted_claims,
        "unsupported_incorrectly_released": unsupported_incorrectly_released,
        "hallucination_catch_rate_pct": hallucination_catch_rate,
        "escalation_rate_pct": esc_rate,
        "avg_response_time_ms": avg_latency,
        "avg_llm_token_usage": avg_tokens,
        "estimated_api_cost_usd": total_cost,
        "avg_retries_per_query": avg_retries
    }

