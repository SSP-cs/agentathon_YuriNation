import time
import uuid
from typing import Dict, Any, List, Optional, TypedDict
from concurrent.futures import ThreadPoolExecutor
from langgraph.graph import StateGraph, END

from backend.config import settings
from backend.schemas import (
    RetrievedChunk, AgentResponse, AuditorResult, VerificationDecision,
    DecisionVerdict, VerificationResponse, ClaimItem, ClaimStatus
)
from retrieval.retriever import retriever
from agents.agent_a import run_agent_a
from agents.agent_b import run_agent_b
from agents.auditor import run_auditor
from agents.decision_engine import evaluate_audit_decision, construct_verified_final_answer
from database.crud import save_verification_session, create_audit_log
from backend.token_tracker import token_tracker

class TrustLayerState(TypedDict):
    session_id: str
    question: str
    category: str
    force_mock: bool
    retry_count: int
    top_k: int
    retrieved_chunks: List[RetrievedChunk]
    agent_a_response: Optional[AgentResponse]
    agent_b_response: Optional[AgentResponse]
    auditor_result: Optional[AuditorResult]
    decision: Optional[VerificationDecision]
    retry_history: List[Dict[str, Any]]
    final_answer: Optional[str]
    status: str
    total_latency_ms: float
    total_tokens: int
    estimated_cost_usd: float
    start_time: float

def retrieve_node(state: TrustLayerState) -> Dict[str, Any]:
    current_retry = state.get("retry_count", 0)
    
    # Adaptive top-k retrieval based on retry count
    if current_retry == 0:
        top_k = settings.RETRIEVAL_TOP_K
    elif current_retry == 1:
        top_k = settings.RETRY_TOP_K_STEP_1
    else:
        top_k = settings.RETRY_TOP_K_STEP_2

    chunks = retriever.retrieve(state["question"], top_k=top_k)
    
    create_audit_log(
        state["session_id"],
        "RETRIEVAL_EXECUTED",
        f"Retrieved {len(chunks)} passage(s) (top_k={top_k}, attempt={current_retry})",
        {"chunks_count": len(chunks), "top_k": top_k, "attempt": current_retry}
    )

    return {
        "retrieved_chunks": chunks,
        "top_k": top_k
    }

def parallel_agents_node(state: TrustLayerState) -> Dict[str, Any]:
    question = state["question"]
    chunks = state["retrieved_chunks"]
    retry_count = state.get("retry_count", 0)
    force_mock = state.get("force_mock", False)

    # Run Agent A and Agent B in parallel threads to optimize latency
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(run_agent_a, question, chunks, retry_count, force_mock)
        future_b = executor.submit(run_agent_b, question, chunks, retry_count, force_mock)
        
        agent_a_res = future_a.result()
        agent_b_res = future_b.result()

    create_audit_log(
        state["session_id"],
        "AGENTS_GENERATED",
        f"Agent A ({agent_a_res.provider}) and Agent B ({agent_b_res.provider}) generated answers in parallel",
        {
            "agent_a_latency_ms": agent_a_res.latency_ms,
            "agent_b_latency_ms": agent_b_res.latency_ms
        }
    )

    return {
        "agent_a_response": agent_a_res,
        "agent_b_response": agent_b_res
    }

def auditor_node(state: TrustLayerState) -> Dict[str, Any]:
    question = state["question"]
    agent_a_res = state["agent_a_response"]
    agent_b_res = state["agent_b_response"]
    chunks = state["retrieved_chunks"]
    force_mock = state.get("force_mock", False)

    auditor_res = run_auditor(
        question=question,
        agent_a_answer=agent_a_res.answer,
        agent_b_answer=agent_b_res.answer,
        chunks=chunks,
        force_mock=force_mock
    )

    create_audit_log(
        state["session_id"],
        "AUDITOR_EVALUATED",
        f"Auditor checked {auditor_res.total_claims} claims: {auditor_res.supported_claims} supported, {auditor_res.unsupported_claims} unsupported, {auditor_res.contradicted_claims} contradicted",
        {
            "confidence": auditor_res.overall_confidence,
            "total_claims": auditor_res.total_claims,
            "supported": auditor_res.supported_claims,
            "unsupported": auditor_res.unsupported_claims
        }
    )

    return {
        "auditor_result": auditor_res
    }

def decision_node(state: TrustLayerState) -> Dict[str, Any]:
    auditor_res = state["auditor_result"]
    current_retry = state.get("retry_count", 0)
    
    decision = evaluate_audit_decision(auditor_res, current_retry)
    retry_history = list(state.get("retry_history", []))

    if decision.verdict == DecisionVerdict.RETRY:
        retry_record = {
            "attempt": current_retry + 1,
            "reason": decision.reason,
            "top_k_used": state.get("top_k", 3),
            "unsupported_claims": auditor_res.unsupported_claims,
            "contradicted_claims": auditor_res.contradicted_claims
        }
        retry_history.append(retry_record)
        return {
            "decision": decision,
            "retry_count": current_retry + 1,
            "retry_history": retry_history
        }

    return {
        "decision": decision,
        "retry_history": retry_history
    }

def release_node(state: TrustLayerState) -> Dict[str, Any]:
    agent_a = state["agent_a_response"]
    auditor_res = state["auditor_result"]
    verified_answer = construct_verified_final_answer(agent_a.answer, auditor_res)
    
    return {
        "status": "VERIFIED_RELEASED",
        "final_answer": verified_answer
    }

def escalate_node(state: TrustLayerState) -> Dict[str, Any]:
    return {
        "status": "ESCALATED_HUMAN_REVIEW",
        "final_answer": None
    }

def route_decision(state: TrustLayerState) -> str:
    decision = state.get("decision")
    if not decision:
        return "escalate"
    
    if decision.verdict == DecisionVerdict.RELEASE:
        return "release"
    elif decision.verdict == DecisionVerdict.RETRY:
        return "retry"
    else:
        return "escalate"

# Build LangGraph workflow
workflow = StateGraph(TrustLayerState)

workflow.add_node("retrieve", retrieve_node)
workflow.add_node("parallel_agents", parallel_agents_node)
workflow.add_node("auditor", auditor_node)
workflow.add_node("decision", decision_node)
workflow.add_node("release", release_node)
workflow.add_node("escalate", escalate_node)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "parallel_agents")
workflow.add_edge("parallel_agents", "auditor")
workflow.add_edge("auditor", "decision")

workflow.add_conditional_edges(
    "decision",
    route_decision,
    {
        "release": "release",
        "retry": "retrieve",
        "escalate": "escalate"
    }
)

workflow.add_edge("release", END)
workflow.add_edge("escalate", END)

trustlayer_graph = workflow.compile()

def run_verification_pipeline(question: str, category: str = "Policy", force_mock: bool = False) -> VerificationResponse:
    session_id = str(uuid.uuid4())
    start_time = time.time()

    create_audit_log(session_id, "SESSION_STARTED", f"New question submitted: '{question}'", {"category": category})

    initial_state: TrustLayerState = {
        "session_id": session_id,
        "question": question,
        "category": category,
        "force_mock": force_mock,
        "retry_count": 0,
        "top_k": settings.RETRIEVAL_TOP_K,
        "retrieved_chunks": [],
        "agent_a_response": None,
        "agent_b_response": None,
        "auditor_result": None,
        "decision": None,
        "retry_history": [],
        "final_answer": None,
        "status": "PROCESSING",
        "total_latency_ms": 0.0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
        "start_time": start_time
    }

    final_state = trustlayer_graph.invoke(initial_state)
    
    total_latency = round((time.time() - start_time) * 1000, 2)
    
    agent_a = final_state["agent_a_response"]
    agent_b = final_state["agent_b_response"]
    auditor_res = final_state["auditor_result"]
    decision = final_state["decision"]
    chunks = final_state["retrieved_chunks"]
    status = final_state["status"]
    final_answer = final_state.get("final_answer")
    retry_history = final_state.get("retry_history", [])

    total_tokens = (
        agent_a.prompt_tokens + agent_a.completion_tokens +
        agent_b.prompt_tokens + agent_b.completion_tokens +
        auditor_res.prompt_tokens + auditor_res.completion_tokens
    )
    # Estimate cost
    estimated_cost = round((total_tokens / 1_000_000.0) * settings.COST_PER_M_INPUT * 1.5, 6)

    # Check if mock mode was active
    is_mock = force_mock or "Demo Simulation" in agent_a.model_name or "Demo Simulation" in agent_b.model_name

    # Persist in SQLite
    save_verification_session(
        session_id=session_id,
        question=question,
        category=category,
        status=status,
        final_answer=final_answer,
        overall_confidence=auditor_res.overall_confidence,
        retry_count=decision.retry_count,
        total_tokens=total_tokens,
        total_cost_usd=estimated_cost,
        total_latency_ms=total_latency,
        is_mock_mode=is_mock,
        agent_a=agent_a,
        agent_b=agent_b,
        auditor=auditor_res,
        claims=auditor_res.claims,
        retry_history=retry_history
    )

    return VerificationResponse(
        session_id=session_id,
        question=question,
        status=status,
        final_answer=final_answer,
        agent_a=agent_a,
        agent_b=agent_b,
        auditor=auditor_res,
        decision=decision,
        evidence=chunks,
        retry_history=retry_history,
        total_latency_ms=total_latency,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost,
        is_mock_mode=is_mock
    )

