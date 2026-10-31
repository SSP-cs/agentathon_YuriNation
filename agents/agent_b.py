import time
from typing import List
from backend.config import settings
from backend.schemas import AgentResponse, RetrievedChunk
from prompts.agent_prompts import AGENT_B_SYSTEM_PROMPT, AGENT_B_USER_PROMPT
from agents.llm_client import llm_client
from agents.mock_engine import mock_engine
from backend.token_tracker import estimate_tokens

def run_agent_b(question: str, chunks: List[RetrievedChunk], retry_count: int = 0, force_mock: bool = False) -> AgentResponse:
    t0 = time.time()
    context_str = "\n\n".join([f"[{c.document_name} p.{c.page_number}]: {c.text}" for c in chunks]) if chunks else "No policy documents found."
    user_prompt = AGENT_B_USER_PROMPT.format(context=context_str, question=question)

    if not force_mock and llm_client.is_provider_available(settings.AGENT_B_PROVIDER):
        res = llm_client.generate_chat(
            provider=settings.AGENT_B_PROVIDER,
            model=settings.AGENT_B_MODEL,
            system_prompt=AGENT_B_SYSTEM_PROMPT,
            user_prompt=user_prompt
        )
        if res:
            return AgentResponse(
                agent_id="agent_b",
                model_name=settings.AGENT_B_MODEL,
                provider=settings.AGENT_B_PROVIDER,
                answer=res["content"],
                latency_ms=res["latency_ms"],
                prompt_tokens=res["prompt_tokens"],
                completion_tokens=res["completion_tokens"]
            )

    # Deterministic simulation fallback
    _, answer_b = mock_engine.generate_agent_answers(question, chunks, retry_count)
    latency = round((time.time() - t0) * 1000 + 135, 2)
    p_tok = estimate_tokens(user_prompt)
    c_tok = estimate_tokens(answer_b)

    return AgentResponse(
        agent_id="agent_b",
        model_name=f"{settings.AGENT_B_MODEL} (Demo Simulation)",
        provider=settings.AGENT_B_PROVIDER,
        answer=answer_b,
        latency_ms=latency,
        prompt_tokens=p_tok,
        completion_tokens=c_tok
    )

