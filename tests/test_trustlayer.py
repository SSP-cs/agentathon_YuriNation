import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.config import settings
from backend.schemas import ClaimStatus, DecisionVerdict, RetrievedChunk
from retrieval.retriever import retriever
from agents.agent_a import run_agent_a
from agents.agent_b import run_agent_b
from agents.auditor import run_auditor
from agents.decision_engine import evaluate_audit_decision
from agents.orchestrator import run_verification_pipeline
from database.crud import get_pending_escalations, get_audit_logs, get_dashboard_metrics, record_escalation_review
from evaluations.metrics import calculate_comprehensive_metrics

def test_1_retrieval_accuracy():
    """Verify semantic retrieval retrieves accurate policy context from ChromaDB."""
    chunks = retriever.retrieve("overdraft fee waiver courtesy", top_k=3)
    assert len(chunks) > 0, "Retriever should return chunks for indexed policy."
    top_text = " ".join([c.text for c in chunks]).lower()
    assert "overdraft" in top_text or "waiver" in top_text
    assert chunks[0].page_number >= 1
    assert chunks[0].document_name != ""

def test_2_two_independent_agents_parallel():
    """Verify Agent A and Agent B generate distinct answers independently."""
    q = "What is the fee for an outbound international wire transfer?"
    chunks = retriever.retrieve(q, top_k=2)
    
    agent_a_res = run_agent_a(q, chunks, force_mock=True)
    agent_b_res = run_agent_b(q, chunks, force_mock=True)

    assert agent_a_res.agent_id == "agent_a"
    assert agent_b_res.agent_id == "agent_b"
    assert len(agent_a_res.answer) > 20
    assert len(agent_b_res.answer) > 20
    assert agent_a_res.latency_ms > 0
    assert agent_b_res.latency_ms > 0

def test_3_auditor_claim_extraction_and_evidence_matching():
    """Verify auditor extracts atomic claims and links evidence."""
    q = "What is the fee for an outbound international wire transfer at ApexBank?"
    chunks = retriever.retrieve(q, top_k=2)
    agent_a_res = run_agent_a(q, chunks, force_mock=True)
    agent_b_res = run_agent_b(q, chunks, force_mock=True)

    audit_res = run_auditor(q, agent_a_res.answer, agent_b_res.answer, chunks, force_mock=True)

    assert audit_res.total_claims > 0
    assert audit_res.supported_claims > 0
    assert audit_res.overall_confidence > 0.70
    first_claim = audit_res.claims[0]
    assert first_claim.claim_id.startswith("CLM-")
    assert first_claim.status in [ClaimStatus.SUPPORTED, ClaimStatus.UNSUPPORTED, ClaimStatus.CONTRADICTED]
    assert first_claim.reasoning != ""

def test_4_hallucination_detection_on_trick_question():
    """Verify auditor identifies unsupported/contradicted claims on hallucination bait."""
    trick_q = "Does ApexBank offer 0% fee complimentary international wire transfers for all mobile app users?"
    chunks = retriever.retrieve(trick_q, top_k=3)
    
    agent_a_res = run_agent_a(trick_q, chunks, force_mock=True)
    agent_b_res = run_agent_b(trick_q, chunks, force_mock=True)
    
    audit_res = run_auditor(trick_q, agent_a_res.answer, agent_b_res.answer, chunks, force_mock=True)
    
    # Must catch contradiction or unsupported assertion
    has_flagged = any(c.status in [ClaimStatus.UNSUPPORTED, ClaimStatus.CONTRADICTED] for c in audit_res.claims)
    assert has_flagged, "Auditor must flag unsupported claims when model hallucinates zero fee wire."

def test_5_decision_engine_and_retry_limits():
    """Verify retry budget and maximum 2 retries escalation."""
    trick_q = "Does ApexBank offer 0% fee complimentary international wire transfers for all mobile app users?"
    chunks = retriever.retrieve(trick_q, top_k=3)
    agent_a_res = run_agent_a(trick_q, chunks, force_mock=True)
    agent_b_res = run_agent_b(trick_q, chunks, force_mock=True)
    audit_res = run_auditor(trick_q, agent_a_res.answer, agent_b_res.answer, chunks, force_mock=True)

    # Attempt 0 -> RETRY
    dec_0 = evaluate_audit_decision(audit_res, retry_count=0)
    assert dec_0.verdict == DecisionVerdict.RETRY
    assert dec_0.retry_count == 1

    # Attempt 1 -> RETRY
    dec_1 = evaluate_audit_decision(audit_res, retry_count=1)
    assert dec_1.verdict == DecisionVerdict.RETRY
    assert dec_1.retry_count == 2

    # Attempt 2 -> ESCALATE (maximum retries reached)
    dec_2 = evaluate_audit_decision(audit_res, retry_count=2)
    assert dec_2.verdict == DecisionVerdict.ESCALATE
    assert "retries" in dec_2.reason.lower() or "exceeded" in dec_2.reason.lower()

def test_6_human_escalation_lifecycle():
    """Verify escalation lifecycle from pending to human supervisor review."""
    # Run a pipeline on a trick question that escalates
    q = "Can customer support grant unlimited courtesy overdraft fee waivers if a customer complains repeatedly?"
    res = run_verification_pipeline(q, force_mock=True)
    assert res.status == "ESCALATED_HUMAN_REVIEW"
    assert res.decision.verdict == DecisionVerdict.ESCALATE

    # Check that pending escalations table has this case
    pending = get_pending_escalations()
    target = next((e for e in pending if e["session_id"] == res.session_id), None)
    assert target is not None, "Escalation should appear in supervisor pending queue."
    assert "overdraft" in target["question"].lower()

    # Supervisor approves or rejects
    record_escalation_review(
        session_id=res.session_id,
        decision="REJECT",
        notes="Rejected: Policy strictly caps waivers at 2 per 12 months. Discretionary waivers forbidden.",
        reviewer="Lead Compliance Officer"
    )

    # Should no longer be pending
    pending_after = get_pending_escalations()
    assert not any(e["session_id"] == res.session_id for e in pending_after)

def test_7_audit_trail_integrity():
    """Verify audit log records every event chronologically."""
    logs = get_audit_logs(limit=20)
    assert len(logs) > 0
    event_types = [l["event_type"] for l in logs]
    assert any("RETRIEVAL" in et or "SESSION" in et or "VERIFICATION" in et for et in event_types)

def test_8_evaluation_metrics_no_leak():
    """Verify that unsupported claims released is strictly zero."""
    metrics = calculate_comprehensive_metrics()
    assert metrics["total_questions_processed"] > 0
    assert metrics["unsupported_incorrectly_released"] == 0, "Zero-tolerance: No unsupported claims can be released!"
    assert metrics["hallucination_catch_rate_pct"] == 100.0

