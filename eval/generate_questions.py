"""Extend eval/questions.json with questions for newly added documents.
Usage: python eval/generate_questions.py   (spot-check the new ground truths before trusting the numbers)"""
import sys, json, shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from trustlayer.config import POLICIES_DIR, AUDITOR_MODEL, MOCK_LLM
from trustlayer.llm import call_llm

QP = ROOT / "eval" / "questions.json"
PROMPT = """Policy document:
{doc}

Return JSON: {{"answerable":[{{"question":..,"ground_truth":..}},{{..}}],"trick":[{{"question":..,"ground_truth":..}}]}}
- 2 answerable questions: need specific numbers from the document; ground_truth restates the exact figures.
- 1 trick question: sounds natural but contains a FALSE premise (wrong figure or a benefit the document does not give); ground_truth states the correct fact from the document.
Name the product explicitly in each question."""

def make(fp):
    raw = call_llm([{"role": "user", "content": PROMPT.format(doc=fp.read_text(encoding='utf-8'))}], model=AUDITOR_MODEL, temperature=0.4, json_mode=True)
    d = json.loads(raw)
    return [(fp.name, "answerable", x) for x in d.get("answerable", [])[:2]] + [(fp.name, "trick", x) for x in d.get("trick", [])[:1]]

if __name__ == "__main__":
    if MOCK_LLM:
        sys.exit("Turn MOCK_LLM off first.")
    qs = json.loads(QP.read_text(encoding="utf-8"))
    used = {q["source_doc"] for q in qs}
    new = [f for f in sorted(Path(POLICIES_DIR).glob("*.md")) if f.name not in used]
    if not new:
        sys.exit("No new documents without questions.")
    shutil.copy(QP, QP.with_name("questions_backup.json"))
    with ThreadPoolExecutor(4) as ex:
        for rows in ex.map(make, new):
            for src, typ, x in rows:
                qs.append({"id": len(qs) + 1, "type": typ, "source_doc": src, "question": x["question"], "ground_truth": x["ground_truth"]})
    QP.write_text(json.dumps(qs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Questions now: {len(qs)}. Run: python eval/run_eval.py")
