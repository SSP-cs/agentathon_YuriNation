"""Agent implementations: Planner, Agent A, Agent B, Auditor, and Finalizer."""

import json
from typing import List, Dict, Any, Tuple, Optional
from trustlayer.config import (
    ANSWER_MODEL_A,
    ANSWER_MODEL_B,
    AUDITOR_MODEL,
)
from trustlayer.schemas import (
    PlannerOutput,
    AnswerOutput,
    ClaimVerdict,
    AuditorOutput,
    EvidenceChunk,
    HandoffPackage,
)
from trustlayer.llm import call_llm, call_llm_structured
from trustlayer.retrieval import format_evidence_block

def run_planner(question: str) -> PlannerOutput:
    """Break the user question into 1-4 retrieval sub-queries and note required facts."""
    system_prompt = (
        "You are an expert customer-support query planner for a bank and insurer. "
        "Analyze the user's question and produce 1 to 4 targeted, keyword-focused search sub-queries "
        "to retrieve the exact policy rules from the documents. Also note the essential facts required."
    )
    user_prompt = f"User Question: {question}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    return call_llm_structured(
        messages=messages,
        model=ANSWER_MODEL_A,
        schema=PlannerOutput,
        temperature=0.0
    )

def run_agent_a(question: str, evidence: List[EvidenceChunk]) -> AnswerOutput:
    """
    Agent A: Concise, direct answering strategy.
    Relies directly on evidence facts, low temperature (0.1), top-k retrieval view.
    """
    evidence_text = format_evidence_block(evidence)
    system_prompt = (
        "You are Agent A, a precise and concise customer support representative for Nova Bank & Nova Shield Insurance.\n"
        "Guidelines:\n"
        "1. Provide a direct, concise answer strictly using the provided policy evidence.\n"
        "2. Do NOT speculate or use outside knowledge.\n"
        "3. Every factual statement must cite its evidence chunk tag (e.g. [S1], [S2]).\n"
        "4. If the evidence does not contain the required information, clearly state: 'The provided policy documents do not contain information to answer this question.'\n"
        "5. Return valid JSON with keys: 'answer' (string) and 'used_evidence_ids' (list of cited tags, e.g. ['S1'])."
    )

    user_prompt = f"Policy Evidence:\n{evidence_text}\n\nCustomer Question:\n{question}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    return call_llm_structured(
        messages=messages,
        model=ANSWER_MODEL_A,
        schema=AnswerOutput,
        temperature=0.1
    )

def run_agent_b(question: str, evidence: List[EvidenceChunk]) -> AnswerOutput:
    """
    Agent B: Step-by-step reasoning strategy with quotation first.
    Extracts quotes first, reasons step-by-step, higher temperature (0.6), MMR retrieval view.
    """
    evidence_text = format_evidence_block(evidence)
    system_prompt = (
        "You are Agent B, a thorough and analytical compliance specialist for Nova Bank & Nova Shield Insurance.\n"
        "Guidelines:\n"
        "1. First identify and extract relevant supporting verbatim quotes from the evidence.\n"
        "2. Then synthesize a comprehensive, step-by-step answer explaining the rules, exceptions, and exact figures in INR.\n"
        "3. Every statement must cite its evidence source tag (e.g. [S1]).\n"
        "4. If the documents do not cover the topic, explicitly state: 'The provided policy documents do not contain information to answer this question.'\n"
        "5. Return valid JSON with keys: 'answer' (string) and 'used_evidence_ids' (list of cited tags, e.g. ['S1'])."
    )

    user_prompt = f"Policy Evidence:\n{evidence_text}\n\nCustomer Question:\n{question}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    return call_llm_structured(
        messages=messages,
        model=ANSWER_MODEL_B,
        provider="b",
        schema=AnswerOutput,
        temperature=0.6
    )

def run_auditor(
    question: str,
    answer_a: AnswerOutput,
    answer_b: AnswerOutput,
    evidence: List[EvidenceChunk]
) -> AuditorOutput:
    """
    Auditor Agent (Strongest Model, Strict Verification):
    1. Splits each answer into atomic factual claims.
    2. Verifies each claim against evidence ONLY (SUPPORTED, UNSUPPORTED, CONTRADICTED).
    3. Computes support_score per answer (supported / total).
    4. Compares A vs B: agreement (AGREE, MINOR_DIFFERENCE, CONFLICT).
    """
    evidence_text = format_evidence_block(evidence)
    system_prompt = (
        "You are the Chief Policy Auditor for Nova Financial Services.\n"
        "CRITICAL DIRECTIVE: You must evaluate claims STRICTLY AND EXCLUSIVELY against the provided Policy Evidence.\n"
        "NEVER use outside knowledge, common sense assumptions, or external facts.\n"
        "If a claim is not explicitly substantiated in the provided text, it MUST be marked UNSUPPORTED.\n"
        "If a claim directly contradicts the provided text, it MUST be marked CONTRADICTED.\n\n"
        "Tasks:\n"
        "1. Deconstruct Answer A into atomic factual claims. For each, assign verdict (SUPPORTED, UNSUPPORTED, CONTRADICTED), evidence_id (e.g. 'S1') or null, and verbatim quote or null.\n"
        "2. Deconstruct Answer B into atomic factual claims with verdicts.\n"
        "3. Compute support_score_a = (supported claims in A) / (total claims in A). Range 0.0 to 1.0.\n"
        "4. Compute support_score_b = (supported claims in B) / (total claims in B). Range 0.0 to 1.0.\n"
        "5. Assess agreement between Agent A and Agent B:\n"
        "   - 'AGREE' if both convey identical substantive conclusions.\n"
        "   - 'MINOR_DIFFERENCE' if they differ only in wording, depth, or non-conflicting details.\n"
        "   - 'CONFLICT' if they state contradictory numbers, rules, eligibility criteria, or opposite conclusions.\n"
        "6. List any conflicting facts.\n"
        "Return valid JSON conforming to the AuditorOutput schema."
    )

    user_prompt = (
        f"POLICY EVIDENCE CHUNKS:\n{evidence_text}\n\n"
        f"USER QUESTION: {question}\n\n"
        f"AGENT A DRAFT ANSWER:\n{answer_a.answer}\n\n"
        f"AGENT B DRAFT ANSWER:\n{answer_b.answer}\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    auditor_res = call_llm_structured(
        messages=messages,
        model=AUDITOR_MODEL,
        schema=AuditorOutput,
        temperature=0.0
    )

    # Re-verify and ensure mathematical consistency of support scores
    if auditor_res.claims_a:
        sup_a = sum(1 for c in auditor_res.claims_a if c.verdict == "SUPPORTED")
        auditor_res.support_score_a = round(sup_a / len(auditor_res.claims_a), 4)
    else:
        auditor_res.support_score_a = 0.0

    if auditor_res.claims_b:
        sup_b = sum(1 for c in auditor_res.claims_b if c.verdict == "SUPPORTED")
        auditor_res.support_score_b = round(sup_b / len(auditor_res.claims_b), 4)
    else:
        auditor_res.support_score_b = 0.0

    return auditor_res

def run_finalizer(
    question: str,
    best_answer: AnswerOutput,
    claims: List[ClaimVerdict],
    evidence: List[EvidenceChunk]
) -> str:
    """
    Finalize verified answer using ONLY supported claims with inline citations [S#]
    and an appended verified sources list with verbatim quotes.
    """
    supported_claims = [c for c in claims if c.verdict == "SUPPORTED"]
    supported_summary = "\n".join(f"- {c.claim} (Source: {c.evidence_id}, Quote: \"{c.quote}\")" for c in supported_claims)
    evidence_text = format_evidence_block(evidence)

    system_prompt = (
        "You are the TrustLayer Finalizer. Formulate the definitive verified response for the customer.\n"
        "STRICT RULES:\n"
        "1. Incorporate ONLY the verified SUPPORTED claims listed below.\n"
        "2. Do NOT introduce any unsupported facts or assumptions.\n"
        "3. Maintain clear inline citations like [S1], [S2] following every factual sentence.\n"
        "4. At the end, include a '### Verified Sources' section listing each cited chunk ID with its source file and exact quote."
    )

    user_prompt = (
        f"Customer Question: {question}\n\n"
        f"Draft Candidate Answer:\n{best_answer.answer}\n\n"
        f"Auditor Verified Claims:\n{supported_summary}\n\n"
        f"Available Evidence Context:\n{evidence_text}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    return call_llm(messages, model=AUDITOR_MODEL, temperature=0.1)

def build_handoff_package(
    question: str,
    answer_a: Optional[AnswerOutput],
    answer_b: Optional[AnswerOutput],
    auditor_output: AuditorOutput,
    evidence: List[EvidenceChunk],
    reason_code: Optional[str] = "LOW_SUPPORT"
) -> HandoffPackage:
    """Create human-in-the-loop escalation handoff package."""
    safe_reason = reason_code or "LOW_SUPPORT"
    all_claims = [c.model_dump() for c in (auditor_output.claims_a + auditor_output.claims_b)] if auditor_output else []
    evidence_dicts = [e.model_dump() for e in evidence]

    messages_map = {
        "NO_EVIDENCE": "No relevant policy documents match this inquiry with sufficient confidence. Manual agent review required.",
        "LOW_SUPPORT": f"The drafted responses contain claims that could not be fully substantiated against policy documents (Support Score: A={auditor_output.support_score_a:.2f}, B={auditor_output.support_score_b:.2f})." if auditor_output else "Low factual support score.",
        "AGENT_CONFLICT": f"Answering agents generated conflicting information regarding: {', '.join(auditor_output.conflicting_facts or ['policy terms'])}." if auditor_output else "Agents reached conflicting conclusions.",
    }

    briefing = messages_map.get(safe_reason, "Verification checks did not meet threshold for automated release.")

    return HandoffPackage(
        question=question,
        answer_a=answer_a.answer if answer_a else None,
        answer_b=answer_b.answer if answer_b else None,
        claim_verdicts=all_claims,
        conflicts=auditor_output.conflicting_facts if auditor_output else [],
        evidence=evidence_dicts,
        reason_code=safe_reason,
        message=briefing
    )
