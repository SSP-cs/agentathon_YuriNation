import re
from typing import List, Dict, Any, Tuple
from backend.schemas import RetrievedChunk, ClaimItem, ClaimStatus, AuditorResult, AgentResponse
from backend.token_tracker import token_tracker, estimate_tokens

def extract_sentences(text: str) -> List[str]:
    """Break paragraph into individual assertion sentences."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 15]

class MockIntelligenceEngine:
    """
    Intelligent policy simulation engine that analyzes real document evidence
    against customer questions, extracts atomic claims, and detects hallucinations.
    """

    def generate_agent_answers(
        self,
        question: str,
        chunks: List[RetrievedChunk],
        retry_count: int = 0
    ) -> Tuple[str, str]:
        q_lower = question.lower()
        evidence_text = " ".join([c.text for c in chunks])
        evidence_lower = evidence_text.lower()

        # Check for tricky / adversarial questions
        is_trick_zero_wire = "0%" in q_lower or "zero fee" in q_lower or "free international" in q_lower
        is_trick_overdraft = "unlimited" in q_lower or "5 times" in q_lower or "ten times" in q_lower or "waived without limit" in q_lower
        is_trick_cosmetic = "cosmetic" in q_lower and ("covered" in q_lower or "reimburs" in q_lower or "immediate" in q_lower)
        is_trick_grace = "90-day" in q_lower or "90 days" in q_lower or "grace period of 3 months" in q_lower

        if is_trick_zero_wire:
            # Agent A hallucinates zero fees (classic customer support hallucination)
            agent_a = "ApexBank offers complimentary international wire transfers with $0 fees for all standard retail checking accounts, provided the transfer is initiated via the mobile banking app."
            agent_b = "According to policy guidelines, international wire transfers are processed via SWIFT. Standard outbound international transfers incur a $45 fee, but promotional transfers might qualify for fee discounts."
            return agent_a, agent_b

        if is_trick_overdraft:
            agent_a = "Customers may receive up to five overdraft fee waivers per calendar year upon verbal request to telephone banking support."
            agent_b = "ApexBank overdraft fees are $35 per occurrence, and courtesy waivers are restricted to a maximum of two occurrences per twelve-month rolling cycle."
            return agent_a, agent_b

        if is_trick_cosmetic:
            agent_a = "Zenith Health covers elective cosmetic procedures in full if submitted within 30 days of the procedure accompanied by doctor receipts."
            agent_b = "Zenith Health policies exclude elective cosmetic treatments unless proven medically necessary for reconstructive restoration following trauma."
            return agent_a, agent_b

        if is_trick_grace:
            agent_a = "Credit card holders enjoy an extended 90-day interest-free grace period on revolving balance purchases during holiday promotional windows."
            agent_b = "The standard interest-free grace period is 21 to 25 days following billing statement generation, not 90 days."
            return agent_a, agent_b

        # General / standard questions with evidence
        if chunks:
            # Synthesize answer using top chunks
            primary_chunk = chunks[0].text
            sentences = extract_sentences(primary_chunk)
            
            summary_a = " ".join(sentences[:2]) if len(sentences) >= 2 else primary_chunk[:250]
            agent_a = f"Based on policy terms: {summary_a} (Ref: {chunks[0].document_name}, p. {chunks[0].page_number})."
            
            # Agent B phrases with compliance tone
            secondary = sentences[1:3] if len(sentences) >= 3 else sentences[:1]
            summary_b = " ".join(secondary) if secondary else primary_chunk[:250]
            agent_b = f"Compliance review indicates: {summary_b} Subject to verified customer verification and standard documentation."
            return agent_a, agent_b

        # No chunks available
        return (
            "We could not locate specific policy provisions for this inquiry in the indexed documentation.",
            "Independent review confirms no regulatory or contract clause in the current policy database covers this query."
        )

    def audit_claims(
        self,
        question: str,
        agent_a_answer: str,
        agent_b_answer: str,
        chunks: List[RetrievedChunk]
    ) -> AuditorResult:
        claims: List[ClaimItem] = []
        evidence_text = " ".join([c.text for c in chunks])
        evidence_lower = evidence_text.lower()
        
        # Extract atomic statements from Agent A
        sentences_a = extract_sentences(agent_a_answer)
        sentences_b = extract_sentences(agent_b_answer)

        claim_idx = 1
        
        for s in sentences_a:
            # Check against evidence chunks
            best_chunk = None
            highest_overlap = 0
            s_words = set(re.findall(r'\w{4,}', s.lower()))
            
            for c in chunks:
                c_words = set(re.findall(r'\w{4,}', c.text.lower()))
                overlap = len(s_words.intersection(c_words))
                if overlap > highest_overlap:
                    highest_overlap = overlap
                    best_chunk = c

            # Check if this sentence contains a hallucinated/contradictory fact
            is_unsupported = False
            contradiction_note = ""

            s_lower = s.lower()
            if "$0" in s_lower or "complimentary international" in s_lower or "free international" in s_lower:
                is_unsupported = True
                contradiction_note = "ApexBank retail policy Section 2 explicitly mandates a $45.00 outbound wire transfer fee."
            elif "five overdraft" in s_lower or "5 overdraft" in s_lower or "5 times" in s_lower:
                is_unsupported = True
                contradiction_note = "Policy limits courtesy overdraft fee waivers strictly to a maximum of two (2) occurrences per year."
            elif "cosmetic procedures in full" in s_lower:
                is_unsupported = True
                contradiction_note = "Zenith policy Section 4.2 excludes elective cosmetic treatments from coverage."
            elif "90-day interest-free" in s_lower or "90 days" in s_lower:
                is_unsupported = True
                contradiction_note = "Cardholder agreement specifies a 21-day grace period, not 90 days."
            elif highest_overlap < 2 and len(s_words) > 3:
                is_unsupported = True
                contradiction_note = "No corroborating statement found in retrieved policy context."

            if is_unsupported:
                claims.append(ClaimItem(
                    claim_id=f"CLM-{claim_idx:03d}",
                    text=s,
                    status=ClaimStatus.UNSUPPORTED if "No corroborating" in contradiction_note else ClaimStatus.CONTRADICTED,
                    source_agent="Agent A",
                    evidence_text=best_chunk.text[:200] + "..." if best_chunk else None,
                    document_name=best_chunk.document_name if best_chunk else None,
                    page_number=best_chunk.page_number if best_chunk else None,
                    confidence_score=0.25,
                    reasoning=contradiction_note or "Source policy documents do not support this factual assertion."
                ))
            else:
                snippet = best_chunk.text[:220] if best_chunk else s
                claims.append(ClaimItem(
                    claim_id=f"CLM-{claim_idx:03d}",
                    text=s,
                    status=ClaimStatus.SUPPORTED,
                    source_agent="Agent A",
                    evidence_text=snippet,
                    document_name=best_chunk.document_name if best_chunk else "Policy.pdf",
                    page_number=best_chunk.page_number if best_chunk else 1,
                    confidence_score=0.94,
                    reasoning=f"Directly substantiated by passage in {best_chunk.document_name if best_chunk else 'Policy'} page {best_chunk.page_number if best_chunk else 1}."
                ))
            claim_idx += 1

        # Evaluate unique statements from Agent B
        for s in sentences_b:
            # Check if redundant with an already evaluated sentence
            s_words = set(re.findall(r'\w{4,}', s.lower()))
            overlap_existing = any(len(s_words.intersection(set(re.findall(r'\w{4,}', c.text.lower())))) > 4 for c in claims)
            if overlap_existing and len(claims) > 1:
                continue

            best_chunk = None
            highest_overlap = 0
            for c in chunks:
                c_words = set(re.findall(r'\w{4,}', c.text.lower()))
                overlap = len(s_words.intersection(c_words))
                if overlap > highest_overlap:
                    highest_overlap = overlap
                    best_chunk = c

            if highest_overlap >= 2 and best_chunk:
                claims.append(ClaimItem(
                    claim_id=f"CLM-{claim_idx:03d}",
                    text=s,
                    status=ClaimStatus.SUPPORTED,
                    source_agent="Agent B",
                    evidence_text=best_chunk.text[:220],
                    document_name=best_chunk.document_name,
                    page_number=best_chunk.page_number,
                    confidence_score=0.91,
                    reasoning=f"Verified against clause in {best_chunk.document_name} on page {best_chunk.page_number}."
                ))
            else:
                claims.append(ClaimItem(
                    claim_id=f"CLM-{claim_idx:03d}",
                    text=s,
                    status=ClaimStatus.INSUFFICIENT_EVIDENCE,
                    source_agent="Agent B",
                    evidence_text=None,
                    document_name=None,
                    page_number=None,
                    confidence_score=0.45,
                    reasoning="Passage lacks sufficient specific details to corroborate this assertion."
                ))
            claim_idx += 1

        supported = sum(1 for c in claims if c.status == ClaimStatus.SUPPORTED)
        unsupported = sum(1 for c in claims if c.status in [ClaimStatus.UNSUPPORTED, ClaimStatus.INSUFFICIENT_EVIDENCE])
        contradicted = sum(1 for c in claims if c.status == ClaimStatus.CONTRADICTED)

        overall_conf = 0.0
        if claims:
            overall_conf = round(sum(c.confidence_score for c in claims) / len(claims), 2)

        if unsupported > 0 or contradicted > 0:
            explanation = (
                f"AUDIT WARNING: {unsupported + contradicted} claim(s) failed verification. "
                f"Agent output contained assertions contradicted by or absent from source policy. "
                f"Remember: AI agent consensus is NOT proof of correctness; source documents govern."
            )
        else:
            explanation = (
                f"AUDIT PASSED: All {supported} factual claims were successfully matched with "
                f"verifiable citations in source policy documents with an average confidence of {overall_conf}."
            )

        return AuditorResult(
            claims=claims,
            total_claims=len(claims),
            supported_claims=supported,
            unsupported_claims=unsupported,
            contradicted_claims=contradicted,
            overall_confidence=overall_conf,
            auditor_explanation=explanation,
            latency_ms=180.0,
            prompt_tokens=estimate_tokens(agent_a_answer + agent_b_answer + evidence_text),
            completion_tokens=estimate_tokens(explanation)
        )

mock_engine = MockIntelligenceEngine()

