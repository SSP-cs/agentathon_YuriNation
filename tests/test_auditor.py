"""Unit tests for auditor logic, claim verification, and scoring."""

from trustlayer.schemas import AnswerOutput, EvidenceChunk
from trustlayer.agents import run_auditor

def test_auditor_computes_scores():
    """Verify that the auditor computes support scores accurately."""
    evidence = [
        EvidenceChunk(
            id="S1",
            content="Nova Classic Savings Account requires a Monthly Average Balance (MAB) of INR 10,000 in metro areas.",
            source="savings_account.md",
            section="Account Variants",
            score=0.9
        )
    ]
    ans_a = AnswerOutput(
        answer="The Nova Classic Savings Account requires an MAB of INR 10,000 in metro branches [S1].",
        used_evidence_ids=["S1"]
    )
    ans_b = AnswerOutput(
        answer="In metro cities, Nova Classic requires a balance of INR 10,000 [S1].",
        used_evidence_ids=["S1"]
    )

    auditor_res = run_auditor("What is the MAB for Nova Classic in metros?", ans_a, ans_b, evidence)

    assert auditor_res.support_score_a >= 0.8
    assert auditor_res.support_score_b >= 0.8
    assert auditor_res.agreement in ("AGREE", "MINOR_DIFFERENCE")
    assert len(auditor_res.claims_a) > 0
    assert len(auditor_res.claims_b) > 0

