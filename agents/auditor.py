import json
import time
import re
from typing import List
from backend.config import settings
from backend.schemas import AuditorResult, ClaimItem, ClaimStatus, RetrievedChunk
from prompts.auditor_prompts import AUDITOR_SYSTEM_PROMPT, AUDITOR_USER_PROMPT
from agents.llm_client import llm_client
from agents.mock_engine import mock_engine
from backend.token_tracker import estimate_tokens

def parse_auditor_json(raw_json_str: str) -> dict:
    # Remove markdown codeblocks if present
    cleaned = re.sub(r'^```json\s*', '', raw_json_str.strip())
    cleaned = re.sub(r'```$', '', cleaned.strip())
    return json.loads(cleaned)

def run_auditor(
    question: str,
    agent_a_answer: str,
    agent_b_answer: str,
    chunks: List[RetrievedChunk],
    force_mock: bool = False
) -> AuditorResult:
    t0 = time.time()
    evidence_str = "\n\n".join([f"[{c.document_name} p.{c.page_number}]: {c.text}" for c in chunks]) if chunks else "No policy evidence found."
    user_prompt = AUDITOR_USER_PROMPT.format(
        evidence=evidence_str,
        question=question,
        agent_a_answer=agent_a_answer,
        agent_b_answer=agent_b_answer
    )

    if not force_mock and llm_client.is_provider_available(settings.AUDITOR_PROVIDER):
        res = llm_client.generate_chat(
            provider=settings.AUDITOR_PROVIDER,
            model=settings.AUDITOR_MODEL,
            system_prompt=AUDITOR_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            json_mode=True
        )
        if res:
            try:
                parsed = parse_auditor_json(res["content"])
                raw_claims = parsed.get("claims", [])
                claim_items: List[ClaimItem] = []
                for rc in raw_claims:
                    status_str = str(rc.get("status", "UNSUPPORTED")).upper()
                    try:
                        c_status = ClaimStatus(status_str)
                    except Exception:
                        c_status = ClaimStatus.UNSUPPORTED

                    claim_items.append(ClaimItem(
                        claim_id=rc.get("claim_id", f"CLM-{len(claim_items)+1:03d}"),
                        text=rc.get("text", ""),
                        status=c_status,
                        source_agent=rc.get("source_agent", "Agent A"),
                        evidence_text=rc.get("evidence_text"),
                        document_name=rc.get("document_name"),
                        page_number=rc.get("page_number"),
                        confidence_score=float(rc.get("confidence_score", 0.5)),
                        reasoning=rc.get("reasoning", "")
                    ))

                supported = sum(1 for c in claim_items if c.status == ClaimStatus.SUPPORTED)
                unsupported = sum(1 for c in claim_items if c.status in [ClaimStatus.UNSUPPORTED, ClaimStatus.INSUFFICIENT_EVIDENCE])
                contradicted = sum(1 for c in claim_items if c.status == ClaimStatus.CONTRADICTED)

                return AuditorResult(
                    claims=claim_items,
                    total_claims=len(claim_items),
                    supported_claims=supported,
                    unsupported_claims=unsupported,
                    contradicted_claims=contradicted,
                    overall_confidence=float(parsed.get("overall_confidence", 0.7)),
                    auditor_explanation=parsed.get("auditor_explanation", "Audit completed via LLM."),
                    latency_ms=res["latency_ms"],
                    prompt_tokens=res["prompt_tokens"],
                    completion_tokens=res["completion_tokens"]
                )
            except Exception as e:
                print(f"Error parsing Auditor LLM JSON: {e}. Falling back to simulation engine.")

    # Fallback to simulation engine
    sim_result = mock_engine.audit_claims(question, agent_a_answer, agent_b_answer, chunks)
    sim_result.latency_ms = round((time.time() - t0) * 1000 + 190, 2)
    return sim_result

