"""Integration tests for LangGraph state machine routes in TrustLayer."""

import pytest
from trustlayer.graph import run_trustlayer
from trustlayer.schemas import EvidenceChunk, AnswerOutput, AuditorOutput, ClaimVerdict
from trustlayer.graph import decide_node

def test_graph_verified_release():
    """Test standard flow routing to finalize (RELEASE / VERIFIED)."""
    question = "What is the Monthly Average Balance for a Nova Classic Savings Account?"
    result = run_trustlayer(question)
    
    assert result.decision in ("RELEASE", "ESCALATE")
    assert result.status in ("VERIFIED", "ESCALATED")
    assert result.run_id is not None
    assert len(result.event_trace) > 0

def test_graph_escalate_on_no_evidence():
    """Test escalation when query is completely outside the knowledge corpus."""
    unrelated_question = "What is the policy for converting Bitcoin to Ethereum on the Mars crypto exchange?"
    result = run_trustlayer(unrelated_question)
    
    # Should escalate because no matching policy exists
    assert result.decision == "ESCALATE"
    assert result.status == "ESCALATED"
    assert result.handoff_package is not None
    assert result.handoff_package.reason_code in ("NO_EVIDENCE", "LOW_SUPPORT")

def test_decide_node_release():
    """Unit test for decide_node under strong support and agreement."""
    state = {
        "run_id": "test_release",
        "question": "test",
        "max_similarity": 0.85,
        "answer_a": AnswerOutput(answer="Valid answer A [S1]", used_evidence_ids=["S1"]),
        "answer_b": AnswerOutput(answer="Valid answer B [S1]", used_evidence_ids=["S1"]),
        "auditor_output": AuditorOutput(
            claims_a=[ClaimVerdict(claim="Fact 1", verdict="SUPPORTED", evidence_id="S1", quote="Q")],
            claims_b=[ClaimVerdict(claim="Fact 1", verdict="SUPPORTED", evidence_id="S1", quote="Q")],
            support_score_a=1.0,
            support_score_b=1.0,
            agreement="AGREE",
            conflicting_facts=[]
        ),
        "retry_count": 0,
        "event_trace": []
    }
    decision = decide_node(state)
    assert decision == "finalize"

def test_decide_node_retry():
    """Unit test for decide_node triggering retry when support is low but retries remain."""
    state = {
        "run_id": "test_retry",
        "question": "test",
        "max_similarity": 0.70,
        "answer_a": AnswerOutput(answer="Answer A [S1]", used_evidence_ids=["S1"]),
        "answer_b": AnswerOutput(answer="Answer B [S1]", used_evidence_ids=["S1"]),
        "auditor_output": AuditorOutput(
            claims_a=[ClaimVerdict(claim="Fact 1", verdict="UNSUPPORTED", evidence_id=None, quote=None)],
            claims_b=[ClaimVerdict(claim="Fact 2", verdict="UNSUPPORTED", evidence_id=None, quote=None)],
            support_score_a=0.5,
            support_score_b=0.5,
            agreement="AGREE",
            conflicting_facts=[]
        ),
        "retry_count": 0,
        "event_trace": []
    }
    decision = decide_node(state)
    assert decision == "retry"

def test_decide_node_escalate_on_conflict():
    """Unit test for decide_node escalating when agents conflict and retries exhausted."""
    state = {
        "run_id": "test_conflict",
        "question": "test",
        "max_similarity": 0.75,
        "answer_a": AnswerOutput(answer="Fee is INR 500 [S1]", used_evidence_ids=["S1"]),
        "answer_b": AnswerOutput(answer="Fee is INR 1500 [S1]", used_evidence_ids=["S1"]),
        "auditor_output": AuditorOutput(
            claims_a=[ClaimVerdict(claim="Fee is 500", verdict="SUPPORTED", evidence_id="S1", quote="Q")],
            claims_b=[ClaimVerdict(claim="Fee is 1500", verdict="UNSUPPORTED", evidence_id=None, quote=None)],
            support_score_a=1.0,
            support_score_b=0.0,
            agreement="CONFLICT",
            conflicting_facts=["Disagreement on fee amount"]
        ),
        "retry_count": 2,  # Max retries reached
        "event_trace": []
    }
    decision = decide_node(state)
    assert decision == "escalate"
    assert state["reason_code"] == "AGENT_CONFLICT"

