"""Benchmark evaluation runner: Baseline RAG vs TrustLayer multi-agent verification."""

import os
import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Any
import matplotlib.pyplot as plt

# Ensure project root in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from trustlayer.config import (
    ANSWER_MODEL_A,
    AUDITOR_MODEL,
    MOCK_LLM,
)
from trustlayer.llm import call_llm
from trustlayer.retrieval import retrieve_evidence, format_evidence_block
from trustlayer.graph import run_trustlayer

def run_baseline_rag(question: str, strict: bool = False) -> Dict[str, Any]:
    """Single-agent standard RAG baseline: retrieves top-4 chunks and generates directly."""
    t0 = time.time()
    evidence = retrieve_evidence(question, attempt=0, k=4)
    evidence_text = format_evidence_block(evidence)

    system_prompt = (
        "You are a helpful customer support AI for Nova Bank and Nova Shield Insurance. "
        "Answer the user question based on the provided policy context."
    )
    if strict:
        system_prompt += (" Answer ONLY from the policy context. If the context does not contain the answer, or the question's "
                          "premise conflicts with it, say so clearly instead of answering.")
    user_prompt = f"Policy Context:\n{evidence_text}\n\nCustomer Question:\n{question}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    answer = call_llm(messages, model=ANSWER_MODEL_A, temperature=0.2)
    latency_ms = (time.time() - t0) * 1000

    return {
        "answer": answer,
        "latency_ms": round(latency_ms, 2),
        "llm_calls": 1
    }

def judge_answer(question: str, ground_truth: str, answer: str, is_escalated: bool = False) -> str:
    """
    LLM-as-a-judge (Auditor model) classifying the response into:
    - CORRECT: Matches ground truth facts accurately.
    - HALLUCINATED: Asserts false facts, adopts false premises, or invents terms.
    - ABSTAINED_OR_ESCALATED: System properly declined, escalated, or stated information is absent.
    """
    if is_escalated:
        return "ABSTAINED_OR_ESCALATED"

    lower_ans = answer.lower()
    if any(phrase in lower_ans for phrase in [
        "do not contain information", "not covered in the policy", "cannot be answered",
        "human operator", "escalated", "not substantiated"
    ]):
        return "ABSTAINED_OR_ESCALATED"

    judge_system = (
        "You are an impartial regulatory evaluation judge for banking and insurance AI systems.\n"
        "Evaluate the candidate answer against the provided ground truth.\n"
        "Classify into exactly one of three categories:\n"
        "1. 'CORRECT': The answer accurately conveys the true facts specified in ground truth.\n"
        "2. 'HALLUCINATED': The answer states false numbers, affirms a false trick premise, or invents rules not supported by ground truth.\n"
        "3. 'ABSTAINED_OR_ESCALATED': The answer explicitly abstains, admits lack of information, or defers to a human.\n\n"
        "Respond with ONLY the category label: CORRECT, HALLUCINATED, or ABSTAINED_OR_ESCALATED."
    )

    judge_user = (
        f"Question: {question}\n\n"
        f"Ground Truth:\n{ground_truth}\n\n"
        f"Candidate Answer:\n{answer}"
    )

    messages = [
        {"role": "system", "content": judge_system},
        {"role": "user", "content": judge_user}
    ]

    resp = call_llm(messages, model=AUDITOR_MODEL, temperature=0.0).strip().upper()
    for cat in ["CORRECT", "HALLUCINATED", "ABSTAINED_OR_ESCALATED"]:
        if cat in resp:
            return cat
    return "HALLUCINATED"

def generate_comparison_charts(summary: Dict[str, Any], output_path: Path):
    """Generate professional comparative performance charts."""
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.patch.set_facecolor('#0F172A')

    colors = ['#EF4444', '#10B981']

    # 1. Hallucination Rate
    ax1 = axes[0]
    ax1.set_facecolor('#1E293B')
    bars1 = ax1.bar(['Baseline RAG', 'TrustLayer'],
                    [summary['baseline_hallucination_rate'] * 100, summary['trustlayer_hallucination_rate'] * 100],
                    color=colors, width=0.55)
    ax1.set_title('Hallucination Rate (%) [Lower is Better]', color='#F8FAFC', fontsize=12, pad=12, fontweight='bold')
    ax1.set_ylim(0, 100)
    ax1.tick_params(colors='#CBD5E1', labelsize=10)
    for bar in bars1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 2, f"{yval:.1f}%", ha='center', va='bottom', color='#F8FAFC', fontweight='bold')

    # 2. Trick Questions Caught
    ax2 = axes[1]
    ax2.set_facecolor('#1E293B')
    bars2 = ax2.bar(['Baseline RAG', 'TrustLayer'],
                    [summary['baseline_trick_caught_rate'] * 100, summary['trustlayer_trick_caught_rate'] * 100],
                    color=['#64748B', '#3B82F6'], width=0.55)
    ax2.set_title('Trick Questions Caught / Handled (%) [Higher is Better]', color='#F8FAFC', fontsize=12, pad=12, fontweight='bold')
    ax2.set_ylim(0, 105)
    ax2.tick_params(colors='#CBD5E1', labelsize=10)
    for bar in bars2:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2.0, yval + 2, f"{yval:.1f}%", ha='center', va='bottom', color='#F8FAFC', fontweight='bold')

    # 3. Latency & Calls Comparison
    ax3 = axes[2]
    ax3.set_facecolor('#1E293B')
    bars3 = ax3.bar(['Baseline RAG', 'TrustLayer'],
                    [summary['baseline_avg_latency_ms'], summary['trustlayer_avg_latency_ms']],
                    color=['#06B6D4', '#8B5CF6'], width=0.55)
    ax3.set_title('Average Latency (ms)', color='#F8FAFC', fontsize=12, pad=12, fontweight='bold')
    ax3.tick_params(colors='#CBD5E1', labelsize=10)
    for bar in bars3:
        yval = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2.0, yval + (max(summary['baseline_avg_latency_ms'], summary['trustlayer_avg_latency_ms']) * 0.02),
                 f"{yval:.0f} ms", ha='center', va='bottom', color='#F8FAFC', fontweight='bold')

    for ax in axes:
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#475569')
        ax.spines['bottom'].set_color('#475569')
        ax.grid(axis='y', linestyle='--', alpha=0.2, color='#94A3B8')

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    print(f"[+] Saved comparative evaluation chart to {output_path}")

def run_evaluation():
    """Main benchmark execution loop across 30 questions."""
    questions_file = ROOT_DIR / "eval" / "questions.json"
    if not questions_file.exists():
        raise FileNotFoundError(f"Missing evaluation file: {questions_file}")

    with open(questions_file, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print(f"\n=======================================================", flush=True)
    print(f"  TrustLayer vs Baseline RAG Benchmark Evaluation", flush=True)
    print(f"  Total Questions: {len(questions)} (answerable + trap questions)", flush=True)
    print(f"=======================================================\n", flush=True)

    results = []
    baseline_latencies = []
    trustlayer_latencies = []
    baseline_calls = []
    trustlayer_calls = []

    for idx, q in enumerate(questions, 1):
        q_id = q["id"]
        q_type = q["type"]
        q_text = q["question"]
        gt = q["ground_truth"]

        print(f"[{idx}/{len(questions)}] ({q_type.upper()}) {q_text[:60]}...", flush=True)

        # 1. Run Baseline RAG
        b_res = run_baseline_rag(q_text)
        b_label = judge_answer(q_text, gt, b_res["answer"])
        baseline_latencies.append(b_res["latency_ms"])
        baseline_calls.append(b_res["llm_calls"])
        b2_res = run_baseline_rag(q_text, strict=True)
        b2_label = judge_answer(q_text, gt, b2_res["answer"])

        # 2. Run TrustLayer Pipeline
        tl_res = run_trustlayer(q_text)
        is_escalated = (tl_res.status == "ESCALATED")
        ans_text = tl_res.final_answer if not is_escalated else tl_res.handoff_package.message
        tl_label = judge_answer(q_text, gt, ans_text, is_escalated=is_escalated)

        # Estimate LLM calls for TrustLayer: planner(1) + agent_a(1) + agent_b(1) + auditor(1) + [retry * 3] + [finalize(1)]
        est_calls = 4 + (tl_res.retry_count * 3) + (1 if tl_res.status == "VERIFIED" else 0)
        trustlayer_latencies.append(tl_res.latency_ms)
        trustlayer_calls.append(est_calls)

        results.append({
            "id": q_id,
            "type": q_type,
            "question": q_text,
            "ground_truth": gt,
            "category": q.get("category", "core"),
            "baseline_strict": {"answer": b2_res["answer"], "label": b2_label},
            "baseline": {
                "answer": b_res["answer"],
                "label": b_label,
                "latency_ms": b_res["latency_ms"],
                "llm_calls": b_res["llm_calls"],
            },
            "trustlayer": {
                "decision": tl_res.decision,
                "status": tl_res.status,
                "answer": tl_res.final_answer,
                "handoff_message": tl_res.handoff_package.message if tl_res.handoff_package else None,
                "label": tl_label,
                "support_score_a": tl_res.support_score_a,
                "support_score_b": tl_res.support_score_b,
                "agreement": tl_res.agreement,
                "retry_count": tl_res.retry_count,
                "latency_ms": tl_res.latency_ms,
                "llm_calls": est_calls,
            }
        })

    # Metric Computations
    total_q = len(questions)
    trick_q = [r for r in results if r["type"] == "trick"]
    total_tricks = len(trick_q)

    # Baseline stats
    baseline_hallucinations = sum(1 for r in results if r["baseline"]["label"] == "HALLUCINATED")
    baseline_hallucination_rate = baseline_hallucinations / total_q
    baseline_trick_caught = sum(1 for r in trick_q if r["baseline"]["label"] in ("CORRECT", "ABSTAINED_OR_ESCALATED"))
    baseline_trick_caught_rate = baseline_trick_caught / total_tricks if total_tricks else 0.0

    # TrustLayer stats
    trustlayer_hallucinations = sum(1 for r in results if r["trustlayer"]["label"] == "HALLUCINATED")
    trustlayer_hallucination_rate = trustlayer_hallucinations / total_q
    trustlayer_trick_caught = sum(1 for r in trick_q if r["trustlayer"]["status"] == "ESCALATED" or r["trustlayer"]["label"] in ("CORRECT", "ABSTAINED_OR_ESCALATED"))
    trustlayer_trick_caught_rate = trustlayer_trick_caught / total_tricks if total_tricks else 0.0

    # Trick questions where baseline hallucinated but TrustLayer caught it
    tricks_caught_by_tl_only = sum(
        1 for r in trick_q
        if r["baseline"]["label"] == "HALLUCINATED" and (r["trustlayer"]["status"] == "ESCALATED" or r["trustlayer"]["label"] != "HALLUCINATED")
    )

    escalations = sum(1 for r in results if r["trustlayer"]["status"] == "ESCALATED")
    escalation_rate = escalations / total_q
    unsupported_released = sum(
        1 for r in results
        if r["trustlayer"]["status"] == "VERIFIED" and r["trustlayer"]["label"] == "HALLUCINATED"
    )

    ans_q = [r for r in results if r["type"] != "trick"]
    na = max(len(ans_q), 1)
    cats = {}
    for r in results:
        c = cats.setdefault(r.get("category", "core"), {"n": 0, "baseline": 0, "strict": 0, "trustlayer": 0})
        c["n"] += 1
        c["baseline"] += r["baseline"]["label"] == "HALLUCINATED"
        c["strict"] += r["baseline_strict"]["label"] == "HALLUCINATED"
        c["trustlayer"] += r["trustlayer"]["label"] == "HALLUCINATED"
    extra = {
        "answerable_correct_baseline": round(sum(r["baseline"]["label"] == "CORRECT" for r in ans_q) / na, 4),
        "answerable_correct_strict": round(sum(r["baseline_strict"]["label"] == "CORRECT" for r in ans_q) / na, 4),
        "answerable_correct_trustlayer": round(sum(r["trustlayer"]["label"] == "CORRECT" for r in ans_q) / na, 4),
        "answerable_wrongly_escalated": round(sum(r["trustlayer"]["status"] == "ESCALATED" for r in ans_q) / na, 4),
        "strict_hallucination_rate": round(sum(r["baseline_strict"]["label"] == "HALLUCINATED" for r in results) / total_q, 4),
        "strict_trick_caught_rate": round(sum(r["baseline_strict"]["label"] != "HALLUCINATED" for r in trick_q) / max(total_tricks, 1), 4),
        "by_category": cats,
    }
    summary = {
        "total_questions": total_q,
        "answerable_count": total_q - total_tricks,
        "trick_count": total_tricks,
        "baseline_hallucination_rate": round(baseline_hallucination_rate, 4),
        "trustlayer_hallucination_rate": round(trustlayer_hallucination_rate, 4),
        "baseline_trick_caught_rate": round(baseline_trick_caught_rate, 4),
        "trustlayer_trick_caught_rate": round(trustlayer_trick_caught_rate, 4),
        "tricks_caught_by_tl_only": tricks_caught_by_tl_only,
        "unsupported_claims_released": unsupported_released,
        "escalation_rate": round(escalation_rate, 4),
        "baseline_avg_latency_ms": round(sum(baseline_latencies) / total_q, 1),
        "trustlayer_avg_latency_ms": round(sum(trustlayer_latencies) / total_q, 1),
        "baseline_avg_llm_calls": round(sum(baseline_calls) / total_q, 1),
        "trustlayer_avg_llm_calls": round(sum(trustlayer_calls) / total_q, 1),
    }
    summary.update(extra)

    # Save results.json
    out_json = ROOT_DIR / "eval" / "results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)
    print(f"[+] Saved evaluation data to {out_json}")

    # Generate Chart
    chart_png = ROOT_DIR / "eval" / "eval_comparison.png"
    generate_comparison_charts(summary, chart_png)

    # Save results.md
    out_md = ROOT_DIR / "eval" / "results.md"
    cat_rows = "\n".join(f"| {k} | {v['n']} | {v['baseline']} | {v['strict']} | {v['trustlayer']} |" for k, v in summary["by_category"].items())
    md_content = f"""# TrustLayer Evaluation Results

Measured on **{total_q} questions** ({total_q - total_tricks} answerable, {total_tricks} trap questions with false premises or topics missing from the documents). Labels come from an LLM judge, so spot-check a sample before quoting exact figures.

| Metric | Naive RAG | Strict-prompt RAG | TrustLayer |
| :--- | :---: | :---: | :---: |
| Hallucination rate (all questions) | {summary['baseline_hallucination_rate']*100:.1f}% | {summary['strict_hallucination_rate']*100:.1f}% | {summary['trustlayer_hallucination_rate']*100:.1f}% |
| Trap questions handled | {summary['baseline_trick_caught_rate']*100:.0f}% | {summary['strict_trick_caught_rate']*100:.0f}% | {summary['trustlayer_trick_caught_rate']*100:.0f}% |
| Answerable questions answered correctly | {summary['answerable_correct_baseline']*100:.0f}% | {summary['answerable_correct_strict']*100:.0f}% | {summary['answerable_correct_trustlayer']*100:.0f}% |
| Answerable questions escalated to a human | n/a | n/a | {summary['answerable_wrongly_escalated']*100:.0f}% |
| Hallucinated answers released as verified | n/a | n/a | {summary['unsupported_claims_released']} |
| Average time per answer | {summary['baseline_avg_latency_ms']/1000:.1f}s | n/a | {summary['trustlayer_avg_latency_ms']/1000:.1f}s |
| LLM calls per question (TrustLayer estimated) | {summary['baseline_avg_llm_calls']:.1f} | 1.0 | {summary['trustlayer_avg_llm_calls']:.1f} |

Hallucinated answers by question category (count):

| Category | Questions | Naive | Strict | TrustLayer |
| :--- | :---: | :---: | :---: | :---: |
{cat_rows}

Notes: differences of one or two questions are within noise. A TrustLayer escalation counts as correct handling for a trap question but as a miss for an answerable one (see the escalated row).
"""
    out_md.write_text(md_content, encoding="utf-8")
    print(f"[+] Saved evaluation report to {out_md}")

    print("\n[+] Benchmark complete successfully!")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    run_evaluation()

