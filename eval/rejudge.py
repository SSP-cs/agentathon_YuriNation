"""Re-label the saved benchmark answers with a corrected answer key and one uniform, fairer judge.
No pipelines are re-run, so the saved latency and call counts stay valid.
Optional eval/corrections.json: {"51": {"ground_truth": "..."}, "54": {"drop": true}}"""
import os, sys, json, shutil, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from trustlayer.config import AUDITOR_MODEL
from trustlayer.llm import call_llm
RES, COR = ROOT / "eval" / "results.json", ROOT / "eval" / "corrections.json"
PROV = os.getenv("JUDGE_PROVIDER", "openai").lower()   # openai (default) or gemini
MODEL, PKEY = (os.getenv("ANSWER_MODEL_B"), "b") if PROV == "gemini" else (AUDITOR_MODEL, "default")
WORKERS = int(os.getenv("JUDGE_WORKERS", "1" if PROV == "gemini" else "4"))
DELAY = float(os.getenv("JUDGE_DELAY", "4" if PROV == "gemini" else "0"))
DONE = [0]
def ask(msgs):
    for n in range(1, 9):
        try:
            time.sleep(DELAY)
            return call_llm(msgs, model=MODEL, temperature=0, provider=PKEY)
        except Exception as e:
            if not ("429" in str(e) or "RateLimit" in type(e).__name__) or n == 8:
                raise
            print(f"rate limited, waiting {20 * n}s ...", flush=True); time.sleep(20 * n)
SYS = """You grade answers from a bank/insurer support assistant against a ground truth. Reply with exactly one label: CORRECT, HALLUCINATED or ABSTAINED_OR_ESCALATED.
CORRECT: the key facts of the ground truth are stated correctly. Missing minor details is fine. Extra details are fine if they do not contradict the ground truth, including details about OTHER Nova products when the question did not name a specific product and the answer says which product each detail belongs to.
HALLUCINATED: the answer contradicts the ground truth, agrees with a false premise the ground truth rejects, or gives another product's values as the answer for the product asked about.
ABSTAINED_OR_ESCALATED: the answer declines, says the information is not in the documents, or defers to a human.
For trap questions, an answer that rejects the false premise is CORRECT, and one that declines is ABSTAINED_OR_ESCALATED."""
def judge(q, gt, ans, esc=False):
    if esc: return "ABSTAINED_OR_ESCALATED"
    r = ask([{"role": "system", "content": SYS}, {"role": "user", "content": f"Question: {q}\nGround truth: {gt}\nCandidate answer: {ans}"}]).upper()
    DONE[0] += 1
    if DONE[0] % 25 == 0: print(f"{DONE[0]} answers judged", flush=True)
    return next((l for l in ("ABSTAINED_OR_ESCALATED", "HALLUCINATED", "CORRECT") if l in r), "HALLUCINATED")
def job(a):
    r, k = a; q, gt = r["question"], r["ground_truth"]
    if k == "trustlayer":
        t = r["trustlayer"]; esc = t["status"] == "ESCALATED"
        return judge(q, gt, t["answer"] if not esc else t.get("handoff_message"), esc)
    return judge(q, gt, r[k]["answer"])
if __name__ == "__main__":
    data = json.loads(RES.read_text(encoding="utf-8")); R = data["results"]
    bk = RES.with_name("results_first_run.json")
    if not bk.exists(): shutil.copy(RES, bk)
    cor = json.loads(COR.read_text(encoding="utf-8")) if COR.exists() else {}
    R = [r for r in R if not cor.get(str(r["id"]), {}).get("drop")]
    for r in R:
        r["ground_truth"] = cor.get(str(r["id"]), {}).get("ground_truth", r["ground_truth"])
    jobs = [(r, k) for r in R for k in ("baseline", "baseline_strict", "trustlayer")]
    with ThreadPoolExecutor(WORKERS) as ex: labels = list(ex.map(job, jobs))
    for (r, k), l in zip(jobs, labels): r[k]["label"] = l
    n = len(R); tr = [r for r in R if r["type"] == "trick"]; an = [r for r in R if r["type"] != "trick"]; nt, na = max(len(tr), 1), max(len(an), 1)
    H = lambda k, rows: sum(r[k]["label"] == "HALLUCINATED" for r in rows)
    ok = lambda k, rows: sum(r[k]["label"] != "HALLUCINATED" for r in rows)
    cats = {}
    for r in R:
        c = cats.setdefault(r.get("category", "core"), {"n": 0, "baseline": 0, "strict": 0, "trustlayer": 0}); c["n"] += 1
        c["baseline"] += r["baseline"]["label"] == "HALLUCINATED"; c["strict"] += r["baseline_strict"]["label"] == "HALLUCINATED"; c["trustlayer"] += r["trustlayer"]["label"] == "HALLUCINATED"
    S = dict(total_questions=n, answerable_count=len(an), trick_count=len(tr),
             baseline_hallucination_rate=round(H("baseline", R) / n, 4), strict_hallucination_rate=round(H("baseline_strict", R) / n, 4), trustlayer_hallucination_rate=round(H("trustlayer", R) / n, 4),
             baseline_trick_caught_rate=round(ok("baseline", tr) / nt, 4), strict_trick_caught_rate=round(ok("baseline_strict", tr) / nt, 4), trustlayer_trick_caught_rate=round(ok("trustlayer", tr) / nt, 4),
             tricks_caught_by_tl_only=sum(r["baseline"]["label"] == "HALLUCINATED" and r["trustlayer"]["label"] != "HALLUCINATED" for r in tr),
             unsupported_claims_released=sum(r["trustlayer"]["status"] == "VERIFIED" and r["trustlayer"]["label"] == "HALLUCINATED" for r in R),
             escalation_rate=round(sum(r["trustlayer"]["status"] == "ESCALATED" for r in R) / n, 4), answerable_wrongly_escalated=round(sum(r["trustlayer"]["status"] == "ESCALATED" for r in an) / na, 4),
             answerable_correct_baseline=round(sum(r["baseline"]["label"] == "CORRECT" for r in an) / na, 4), answerable_correct_strict=round(sum(r["baseline_strict"]["label"] == "CORRECT" for r in an) / na, 4),
             answerable_correct_trustlayer=round(sum(r["trustlayer"]["label"] == "CORRECT" for r in an) / na, 4),
             baseline_avg_latency_ms=round(sum(r["baseline"]["latency_ms"] for r in R) / n, 1), trustlayer_avg_latency_ms=round(sum(r["trustlayer"]["latency_ms"] for r in R) / n, 1),
             baseline_avg_llm_calls=1.0, trustlayer_avg_llm_calls=round(sum(r["trustlayer"]["llm_calls"] for r in R) / n, 1), by_category=cats)
    RES.write_text(json.dumps({"summary": S, "results": R}, indent=2), encoding="utf-8")
    rows = "\n".join(f"| {k} | {v['n']} | {v['baseline']} | {v['strict']} | {v['trustlayer']} |" for k, v in cats.items())
    (ROOT / "eval" / "results.md").write_text(f"""# TrustLayer Evaluation Results (re-judged)

**{n} questions** ({len(an)} answerable, {len(tr)} trap questions). Re-judged with {len(cor)} answer-key correction(s) and one uniform LLM judge applied to all three systems. First-run labels are kept in results_first_run.json.

| Metric | Naive RAG | Strict-prompt RAG | TrustLayer |
| :--- | :---: | :---: | :---: |
| Hallucination rate | {S['baseline_hallucination_rate']*100:.1f}% | {S['strict_hallucination_rate']*100:.1f}% | {S['trustlayer_hallucination_rate']*100:.1f}% |
| Trap questions handled | {S['baseline_trick_caught_rate']*100:.0f}% | {S['strict_trick_caught_rate']*100:.0f}% | {S['trustlayer_trick_caught_rate']*100:.0f}% |
| Answerable answered correctly | {S['answerable_correct_baseline']*100:.0f}% | {S['answerable_correct_strict']*100:.0f}% | {S['answerable_correct_trustlayer']*100:.0f}% |
| Answerable sent to a human | n/a | n/a | {S['answerable_wrongly_escalated']*100:.0f}% |
| Hallucinations released as verified | n/a | n/a | {S['unsupported_claims_released']} |
| Average time per answer | {S['baseline_avg_latency_ms']/1000:.1f}s | n/a | {S['trustlayer_avg_latency_ms']/1000:.1f}s |
| LLM calls per question (TrustLayer estimated) | 1.0 | 1.0 | {S['trustlayer_avg_llm_calls']:.1f} |

Hallucinated answers by category (count):

| Category | Questions | Naive | Strict | TrustLayer |
| :--- | :---: | :---: | :---: | :---: |
{rows}
""", encoding="utf-8")
    print(json.dumps({k: v for k, v in S.items() if k != "by_category"}, indent=1))
