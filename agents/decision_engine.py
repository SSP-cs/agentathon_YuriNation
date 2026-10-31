from typing import Optional, Tuple
from backend.config import settings
from backend.schemas import AuditorResult, DecisionVerdict, VerificationDecision, ClaimStatus

def evaluate_audit_decision(
    auditor_result: AuditorResult,
    retry_count: int
) -> VerificationDecision:
    """
    Evaluates auditor findings and determines whether to RELEASE, RETRY, or ESCALATE.
    """
    total = auditor_result.total_claims
    supported = auditor_result.supported_claims
    unsupported = auditor_result.unsupported_claims
    contradicted = auditor_result.contradicted_claims
    confidence = auditor_result.overall_confidence

    # Empty claim edge-case
    if total == 0:
        if retry_count < settings.MAX_RETRIES:
            return VerificationDecision(
                verdict=DecisionVerdict.RETRY,
                reason="No factual claims could be extracted or verified from context. Retrying with broader retrieval.",
                retry_count=retry_count + 1
            )
        else:
            return VerificationDecision(
                verdict=DecisionVerdict.ESCALATE,
                reason="No factual claims substantiated by policy documents after maximum retries.",
                retry_count=retry_count
            )

    # Condition 1: All claims fully supported with high confidence
    if supported == total and contradicted == 0 and unsupported == 0 and confidence >= settings.CONFIDENCE_THRESHOLD:
        return VerificationDecision(
            verdict=DecisionVerdict.RELEASE,
            reason=f"All {total} claims substantiated with verifiable citations (confidence {confidence:.2f}). Verified answer approved for release.",
            retry_count=retry_count
        )

    # Condition 2: Insufficient evidence / unsupported claims but retry budget available
    if retry_count < settings.MAX_RETRIES:
        return VerificationDecision(
            verdict=DecisionVerdict.RETRY,
            reason=f"Evidence insufficient: {unsupported} unsupported claim(s), {contradicted} contradiction(s). Expanding retrieval window (Attempt {retry_count + 1}/{settings.MAX_RETRIES}).",
            retry_count=retry_count + 1
        )

    # Condition 3: Retry limit reached, or unresolved contradictions
    return VerificationDecision(
        verdict=DecisionVerdict.ESCALATE,
        reason=f"Verification failed after {retry_count} retries. Detected {unsupported} unsupported and {contradicted} contradictory claim(s). Escalating to human reviewer.",
        retry_count=retry_count
    )

def construct_verified_final_answer(agent_a_answer: str, auditor_result: AuditorResult) -> str:
    """
    Constructs the final released answer with official source citations appended.
    """
    citations = []
    seen = set()
    for c in auditor_result.claims:
        if c.status == ClaimStatus.SUPPORTED and c.document_name and c.page_number:
            cite_str = f"[{c.document_name}, p. {c.page_number}]"
            if cite_str not in seen:
                citations.append(cite_str)
                seen.add(cite_str)

    citation_block = "\n\n**Verified Citations:** " + ", ".join(citations) if citations else ""
    return f"{agent_a_answer.strip()}{citation_block}"

