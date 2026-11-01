"""Harder benchmark data: look-alike sibling products, amendment circulars, and tougher questions.
Usage:  python scripts/expand_hard.py docs   then   python scripts/ingest.py   then   python scripts/expand_hard.py questions"""
import sys, json, shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from trustlayer.config import POLICIES_DIR, AUDITOR_MODEL, MOCK_LLM
from trustlayer.llm import call_llm
P, QP = Path(POLICIES_DIR), ROOT / "eval" / "questions.json"
PAIRS = {"savings_account": "Nova Premium Savings Account", "credit_card": "Nova Platinum Credit Card",
         "personal_loan": "Nova Flexi Personal Loan", "upi_digital_payments": "Nova Business UPI Payments",
         "health_insurance": "Nova Shield Family Floater Health Plan", "motor_insurance": "Nova Shield Motor Third-Party Plus Policy"}
OOS = ["gold loan", "forex card", "mutual funds", "term life insurance", "demat account", "pension plan", "wealth management", "FASTag"]
def llm(p, t=0.5, js=False): return call_llm([{"role": "user", "content": p}], model=AUDITOR_MODEL, temperature=t, json_mode=js)
def jcall(p): return json.loads(llm(p, 0.3, True))

def gen_doc(job):
    kind, key = job
    out, orig = P / f"{key}_{kind}.md", (P / f"{key}.md").read_text(encoding="utf-8")
    if out.exists(): return f"skip {out.name}"
    if kind == "sibling":
        p = (f"Existing policy document:\n\n{orig}\n\nWrite a SIBLING product document named '{PAIRS[key]}' with the same section structure and similar-sounding wording, "
             "but change at least 80% of the numbers (fees, limits, rates, periods), keeping every number internally consistent. 650-850 words, Markdown, one '# ' title, '## ' sections. No placeholders.")
    else:
        gts = [q["ground_truth"] for q in json.loads(QP.read_text(encoding="utf-8")) if q["source_doc"].startswith(key)]
        p = (f"Existing policy document:\n\n{orig}\n\nWrite a short circular (200-300 words, Markdown, '# ' title) 'Circular NB/2026: Amendments to {key.replace('_', ' ')}', effective 1 September 2026. "
             f"It must amend exactly TWO clauses using 'previously X, now Y' with new values, and state it supersedes the earlier values. Do NOT change any fact appearing in these statements: {json.dumps(gts)}. Pick other clauses.")
    out.write_text(llm(p, 0.7).strip() + "\n", encoding="utf-8")
    return f"wrote {out.name}"

def pair_job(key):
    d = f"DOCUMENT A:\n{(P / f'{key}.md').read_text(encoding='utf-8')}\n\nDOCUMENT B ({PAIRS[key]}):\n{(P / f'{key}_sibling.md').read_text(encoding='utf-8')}"
    r = jcall(d + '\n\nReturn JSON {"confusable":[{"question":"","ground_truth":""},{"question":"","ground_truth":""}],"multi_hop":[{"question":"","ground_truth":""}],"false_premise":[{"question":"","ground_truth":""}]}.\n'
              "- confusable: asks about ONE product by full name where the other has a similar clause with a different value; ground_truth is the named product's value.\n"
              "- multi_hop: needs two or more facts, e.g. a comparison or calculation across both products; show the working in ground_truth.\n"
              "- false_premise: sounds natural but is subtly wrong (a nearby wrong number, or the other product's feature attributed to this one); ground_truth states the correct fact.\nAlways name products in full.")
    return [dict(type=t, category=c, source_doc=f"{key}_sibling.md", question=x["question"], ground_truth=x["ground_truth"], _docs=d)
            for c, t in (("confusable", "answerable"), ("multi_hop", "answerable"), ("false_premise", "trick")) for x in r.get(c, [])]

def circ_job(key):
    d = f"ORIGINAL:\n{(P / f'{key}.md').read_text(encoding='utf-8')}\n\nCIRCULAR (newer, supersedes):\n{(P / f'{key}_circular.md').read_text(encoding='utf-8')}"
    x = jcall(d + '\n\nReturn JSON {"question":"","ground_truth":""}. The question must only be answered correctly with the circular\'s NEW value; ground_truth states it and says it comes from the circular.')
    return [dict(type="answerable", category="amended", source_doc=f"{key}_circular.md", question=x["question"], ground_truth=x["ground_truth"], _docs=d)]

def verify(q):
    r = llm(f"Documents:\n{q['_docs']}\n\nQuestion: {q['question']}\nProposed answer: {q['ground_truth']}\nIs the proposed answer fully and unambiguously correct according to the documents? Reply YES or NO only.", 0)
    return r.strip().upper().startswith("YES")

def oos_items():
    corpus = " ".join(f.read_text(encoding="utf-8").lower() for f in P.glob("*.md"))
    topics = [t for t in OOS if t.lower() not in corpus]
    r = jcall(f'For each topic write one natural customer question to Nova Bank asking for specific terms (fee, rate or limit) as if the product exists. Return JSON {{"items":[{{"question":""}}]}}. Topics: {topics}')
    return [dict(type="trick", category="out_of_scope", source_doc="none", question=i["question"],
                 ground_truth="Not covered: the Nova policy documents contain no information on this product. A correct system declines or escalates.") for i in r["items"]]

if __name__ == "__main__":
    if MOCK_LLM: sys.exit("Turn MOCK_LLM off: this needs your real key.")
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "docs":
        with ThreadPoolExecutor(4) as ex:
            for line in ex.map(gen_doc, [("sibling", k) for k in PAIRS] + [("circular", k) for k in PAIRS]): print(line)
        print("Now run: python scripts/ingest.py")
    elif mode == "questions":
        qs = json.loads(QP.read_text(encoding="utf-8"))
        shutil.copy(QP, QP.with_name("questions_before_hard.json"))
        with ThreadPoolExecutor(4) as ex:
            cand = [q for rows in ex.map(pair_job, PAIRS) for q in rows] + [q for rows in ex.map(circ_job, PAIRS) for q in rows]
            ok = list(ex.map(verify, cand))
        keep = [q for q, o in zip(cand, ok) if o] + oos_items()
        for q in keep:
            q.pop("_docs", None); q["id"] = len(qs) + 1; qs.append(q)
        QP.write_text(json.dumps(qs, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Added {len(keep)} hard questions ({len(cand) - sum(ok)} dropped by verification). Total: {len(qs)}.")
    else:
        sys.exit("Usage: python scripts/expand_hard.py docs|questions")
