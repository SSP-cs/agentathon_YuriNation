"""LangGraph state machine orchestration for TrustLayer multi-agent verification."""

import time
import uuid
from datetime import datetime, timezone
from typing import TypedDict, List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from langgraph.graph import StateGraph, END

from trustlayer.config import MIN_SIM, SUPPORT_THRESHOLD, MAX_RETRIES
from trustlayer.schemas import (
    EvidenceChunk,
    PlannerOutput,
    AnswerOutput,
    AuditorOutput,
    HandoffPackage,
    TrustLayerRunResult,
)
from trustlayer.retrieval import retrieve_evidence
from trustlayer.agents import (
    run_planner,
    run_agent_a,
    run_agent_b,
    run_auditor,
    run_finalizer,
    build_handoff_package,
)
from trustlayer.audit_db import log_event, save_run

class TrustLayerGraphState(TypedDict):
    """LangGraph state dictionary holding execution context."""
    run_id: str
    question: str
    sub_queries: List[str]
    evidence_chunks: List[EvidenceChunk]
    max_similarity: float
    answer_a: Optional[AnswerOutput]
    answer_b: Optional[AnswerOutput]
    auditor_output: Optional[AuditorOutput]
    retry_count: int
    decision: str
    status: str
    reason_code: Optional[str]
    final_answer: Optional[str]
    handoff_package: Optional[HandoffPackage]
    event_trace: List[Dict[str, Any]]
    unsupported_claims: List[str]
    start_time: float
    latency_ms: float

# ==================== Graph Node Functions ====================

def planner_node(state: TrustLayerGraphState) -> Dict[str, Any]:
    """Node 1: Planner decomposes query into sub-queries and needed facts."""
    t0 = time.time()
    run_id = state["run_id"]
    q = state["question"]

    event = log_event(run_id, "planner", f"Planning retrieval strategy for query: '{q}'")
    state["event_trace"].append(event)

    planner_res = run_planner(q)
    event_done = log_event(
        run_id, "planner",
        f"Generated {len(planner_res.sub_queries)} sub-queries: {planner_res.sub_queries}",
        {"required_facts": planner_res.required_facts}
    )
    state["event_trace"].append(event_done)

    return {
        "sub_queries": planner_res.sub_queries,
        "event_trace": state["event_trace"]
    }

def retriever_node(state: TrustLayerGraphState) -> Dict[str, Any]:
    """Node 2: Tiered retriever with attempt-based expansion and MMR."""
    run_id = state["run_id"]
    attempt = state.get("retry_count", 0)
    q = state["question"]
    unsupported = state.get("unsupported_claims", [])

    event = log_event(
        run_id, "retriever",
        f"Retrieving evidence (Attempt {attempt}). Using unsupported claims for rewrite: {bool(unsupported)}",
        {"attempt": attempt, "unsupported_count": len(unsupported)}
    )
    state["event_trace"].append(event)

    # Use primary question + sub-queries
    chunks: List[EvidenceChunk] = []
    seen_ids = set()

    # Search primary question with tiered strategy
    primary_chunks = retrieve_evidence(
        query=q,
        attempt=attempt,
        unsupported_claims=unsupported
    )
    for c in primary_chunks:
        if c.id not in seen_ids:
            chunks.append(c)
            seen_ids.add(c.id)

    # Search sub-queries if available
    for sq in state.get("sub_queries", [])[:2]:
        sub_chunks = retrieve_evidence(query=sq, attempt=attempt, k=4)
        for sc in sub_chunks:
            if sc.id not in seen_ids:
                chunks.append(sc)
                seen_ids.add(sc.id)

    max_sim = max((c.score for c in chunks), default=0.0)

    event_done = log_event(
        run_id, "retriever",
        f"Retrieved {len(chunks)} unique evidence chunks. Max similarity: {max_sim:.3f}",
        {"chunk_ids": [c.id for c in chunks], "max_sim": max_sim}
    )
    state["event_trace"].append(event_done)

    return {
        "evidence_chunks": chunks,
        "max_similarity": max_sim,
        "event_trace": state["event_trace"]
    }

def parallel_agents_node(state: TrustLayerGraphState) -> Dict[str, Any]:
    """Node 3: Run Agent A and Agent B in parallel via thread pool."""
    run_id = state["run_id"]
    q = state["question"]
    evidence = state.get("evidence_chunks", [])

    event = log_event(run_id, "agents", "Dispatching parallel generation to Agent A (Concise) and Agent B (Reasoned)")
    state["event_trace"].append(event)

    # Agent B gets alternative MMR retrieval view
    agent_b_evidence = retrieve_evidence(query=q, attempt=0, use_mmr=True, k=6) or evidence

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(run_agent_a, q, evidence)
        future_b = executor.submit(run_agent_b, q, agent_b_evidence)

        ans_a = future_a.result()
        ans_b = future_b.result()

    event_done = log_event(
        run_id, "agents",
        "Both agents generated answers successfully",
        {"agent_a_len": len(ans_a.answer), "agent_b_len": len(ans_b.answer)}
    )
    state["event_trace"].append(event_done)

    return {
        "answer_a": ans_a,
        "answer_b": ans_b,
        "event_trace": state["event_trace"]
    }

def auditor_node(state: TrustLayerGraphState) -> Dict[str, Any]:
    """Node 4: Auditor extracts claims, assigns verdicts, scores support, and checks agreement."""
    run_id = state["run_id"]
    q = state["question"]
    ans_a = state["answer_a"]
    ans_b = state["answer_b"]
    evidence = state.get("evidence_chunks", [])

    event = log_event(run_id, "auditor", "Executing strict independent claim verification against source evidence")
    state["event_trace"].append(event)

    auditor_res = run_auditor(q, ans_a, ans_b, evidence)

    # Extract unsupported claims for potential query rewrite in retry
    unsupported = [
        c.claim for c in auditor_res.claims_a + auditor_res.claims_b
        if c.verdict in ("UNSUPPORTED", "CONTRADICTED")
    ]

    event_done = log_event(
        run_id, "auditor",
        f"Auditor complete. Score A: {auditor_res.support_score_a:.2f}, Score B: {auditor_res.support_score_b:.2f}, Agreement: {auditor_res.agreement}",
        {
            "support_score_a": auditor_res.support_score_a,
            "support_score_b": auditor_res.support_score_b,
            "agreement": auditor_res.agreement,
            "conflicts": auditor_res.conflicting_facts,
            "unsupported_count": len(unsupported)
        }
    )
    state["event_trace"].append(event_done)

    return {
        "auditor_output": auditor_res,
        "unsupported_claims": unsupported,
        "event_trace": state["event_trace"]
    }

def prepare_retry_node(state: TrustLayerGraphState) -> Dict[str, Any]:
    """Node 5b: Explicit state mutation node for retries to guarantee retry_count increments."""
    run_id = state["run_id"]
    curr = state.get("retry_count", 0)
    new_count = curr + 1
    event = log_event(run_id, "retry", f"Initiating retry {new_count}/{MAX_RETRIES} with expanded retrieval context")
    state["event_trace"].append(event)
    return {
        "retry_count": new_count,
        "event_trace": state["event_trace"]
    }

def decide_node(state: TrustLayerGraphState) -> str:
    """Node 5: Conditional edge deciding between finalize, retry, or escalate."""
    run_id = state["run_id"]
    max_sim = state.get("max_similarity", 0.0)
    auditor_res = state["auditor_output"]
    ans_a = (state["answer_a"].answer if state.get("answer_a") else "").lower()
    ans_b = (state["answer_b"].answer if state.get("answer_b") else "").lower()
    retries = state.get("retry_count", 0)

    no_info_marker = "do not contain information"
    both_say_no_info = (no_info_marker in ans_a and no_info_marker in ans_b)

    # 1. Escalate if no evidence
    if max_sim < MIN_SIM or both_say_no_info:
        log_event(run_id, "decide", f"Decision: ESCALATE (Reason: NO_EVIDENCE, max_sim={max_sim:.3f})")
        return "escalate"

    # Identify best answer and check its claims for contradictions
    if auditor_res.support_score_a >= auditor_res.support_score_b:
        best_score = auditor_res.support_score_a
        best_claims = auditor_res.claims_a
    else:
        best_score = auditor_res.support_score_b
        best_claims = auditor_res.claims_b

    best_has_contradicted = any(c.verdict == "CONTRADICTED" for c in best_claims)

    # 2. Release if criteria met
    if best_score >= SUPPORT_THRESHOLD and not best_has_contradicted and auditor_res.agreement != "CONFLICT":
        log_event(run_id, "decide", f"Decision: RELEASE (Score: {best_score:.2f} >= {SUPPORT_THRESHOLD}, Agreement: {auditor_res.agreement})")
        return "finalize"

    # 3. Retry loop if retries remain
    if retries < MAX_RETRIES:
        log_event(run_id, "decide", f"Decision: RETRY (Current attempt: {retries}, Max: {MAX_RETRIES})")
        return "retry"

    # 4. Escalate if retries exhausted
    reason = "AGENT_CONFLICT" if auditor_res.agreement == "CONFLICT" else "LOW_SUPPORT"
    log_event(run_id, "decide", f"Decision: ESCALATE (Reason: {reason}, best_score={best_score:.2f})")
    state["reason_code"] = reason
    return "escalate"

def finalize_node(state: TrustLayerGraphState) -> Dict[str, Any]:
    """Node 6: Finalize verified release answer."""
    run_id = state["run_id"]
    q = state["question"]
    auditor_res = state["auditor_output"]
    evidence = state.get("evidence_chunks", [])

    # Pick better answer
    if auditor_res.support_score_a >= auditor_res.support_score_b:
        best_ans = state["answer_a"]
        best_claims = auditor_res.claims_a
    else:
        best_ans = state["answer_b"]
        best_claims = auditor_res.claims_b

    final_text = run_finalizer(q, best_ans, best_claims, evidence)

    event_done = log_event(run_id, "finalize", "Final verified response formulated with strict citations")
    state["event_trace"].append(event_done)

    return {
        "decision": "RELEASE",
        "status": "VERIFIED",
        "final_answer": final_text,
        "event_trace": state["event_trace"]
    }

def escalate_node(state: TrustLayerGraphState) -> Dict[str, Any]:
    """Node 7: Produce human handoff package for escalated cases."""
    run_id = state["run_id"]
    q = state["question"]
    ans_a = state.get("answer_a")
    ans_b = state.get("answer_b")
    auditor_res = state.get("auditor_output")
    evidence = state.get("evidence_chunks", [])
    max_sim = state.get("max_similarity", 0.0)

    # Determine reason code dynamically if not already established
    reason_code = state.get("reason_code")
    if not reason_code:
        no_info_marker = "do not contain information"
        a_txt = (ans_a.answer if ans_a else "").lower()
        b_txt = (ans_b.answer if ans_b else "").lower()
        if max_sim < MIN_SIM or (no_info_marker in a_txt and no_info_marker in b_txt) or not evidence:
            reason_code = "NO_EVIDENCE"
        elif auditor_res and auditor_res.agreement == "CONFLICT":
            reason_code = "AGENT_CONFLICT"
        else:
            reason_code = "LOW_SUPPORT"

    handoff = build_handoff_package(
        question=q,
        answer_a=ans_a,
        answer_b=ans_b,
        auditor_output=auditor_res if auditor_res else AuditorOutput(agreement="CONFLICT"),
        evidence=evidence,
        reason_code=reason_code
    )

    event_done = log_event(run_id, "escalate", f"Human handoff package prepared (Reason: {reason_code})")
    state["event_trace"].append(event_done)

    return {
        "decision": "ESCALATE",
        "status": "ESCALATED",
        "reason_code": reason_code,
        "handoff_package": handoff,
        "event_trace": state["event_trace"]
    }

# ==================== LangGraph Assembly ====================

def build_trustlayer_graph() -> StateGraph:
    """Build and compile the LangGraph StateGraph."""
    workflow = StateGraph(TrustLayerGraphState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("parallel_agents", parallel_agents_node)
    workflow.add_node("auditor", auditor_node)
    workflow.add_node("prepare_retry", prepare_retry_node)
    workflow.add_node("finalize", finalize_node)
    workflow.add_node("escalate", escalate_node)

    workflow.set_entry_point("planner")

    workflow.add_edge("planner", "retriever")
    workflow.add_edge("retriever", "parallel_agents")
    workflow.add_edge("parallel_agents", "auditor")

    workflow.add_conditional_edges(
        "auditor",
        decide_node,
        {
            "finalize": "finalize",
            "retry": "prepare_retry",
            "escalate": "escalate"
        }
    )

    workflow.add_edge("prepare_retry", "retriever")
    workflow.add_edge("finalize", END)
    workflow.add_edge("escalate", END)

    return workflow.compile()

# Singleton compiled app
trustlayer_app = build_trustlayer_graph()

def run_trustlayer(
    question: str,
    run_id: Optional[str] = None,
    min_sim: Optional[float] = None,
    support_threshold: Optional[float] = None,
    max_retries: Optional[int] = None,
) -> TrustLayerRunResult:
    """Execute TrustLayer verification graph end-to-end and persist to SQLite audit db."""
    t0 = time.time()
    active_run_id = run_id or f"run_{uuid.uuid4().hex[:10]}"

    initial_state: TrustLayerGraphState = {
        "run_id": active_run_id,
        "question": question,
        "sub_queries": [],
        "evidence_chunks": [],
        "max_similarity": 0.0,
        "answer_a": None,
        "answer_b": None,
        "auditor_output": None,
        "retry_count": 0,
        "decision": "RELEASE",
        "status": "VERIFIED",
        "reason_code": None,
        "final_answer": None,
        "handoff_package": None,
        "event_trace": [],
        "unsupported_claims": [],
        "start_time": t0,
        "latency_ms": 0.0,
    }

    final_state = trustlayer_app.invoke(initial_state)

    latency = round((time.time() - t0) * 1000, 2)
    auditor_res = final_state.get("auditor_output")

    all_claims = []
    if auditor_res:
        all_claims.extend(auditor_res.claims_a)
        all_claims.extend(auditor_res.claims_b)

    result = TrustLayerRunResult(
        run_id=active_run_id,
        question=question,
        decision=final_state["decision"],
        status=final_state["status"],
        final_answer=final_state.get("final_answer"),
        handoff_package=final_state.get("handoff_package"),
        support_score_a=auditor_res.support_score_a if auditor_res else 0.0,
        support_score_b=auditor_res.support_score_b if auditor_res else 0.0,
        agreement=auditor_res.agreement if auditor_res else "AGREE",
        retry_count=final_state.get("retry_count", 0),
        latency_ms=latency,
        evidence_chunks=final_state.get("evidence_chunks", []),
        claims=all_claims,
        event_trace=final_state.get("event_trace", []),
        answer_a=final_state["answer_a"].answer if final_state.get("answer_a") else None,
        answer_b=final_state["answer_b"].answer if final_state.get("answer_b") else None,
    )

    save_run(result)
    return result
