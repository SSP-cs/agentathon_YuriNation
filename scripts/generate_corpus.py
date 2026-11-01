"""Grow the policy corpus: generate extra synthetic Nova Bank / Nova Shield documents with your OpenAI key.
Usage: python scripts/generate_corpus.py [--force]   then   python scripts/ingest.py"""
import sys, argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from trustlayer.config import POLICIES_DIR, AUDITOR_MODEL, MOCK_LLM
from trustlayer.llm import call_llm

TOPICS = {
 "education_loan": ("Nova Bank Education Loan", "domestic and overseas study, moratorium, collateral thresholds, interest subsidy"),
 "two_wheeler_loan": ("Nova Bank Two-Wheeler Loan", "ex-showroom funding percentage, tenure, processing fee, prepayment"),
 "debit_card": ("Nova Bank Debit Card Terms", "card variants, ATM limits, POS limits, international use, lost card, annual fees"),
 "current_account": ("Nova Bank Current Account", "variants, average balance, cash deposit limits, transaction charges, overdraft"),
 "nri_account": ("Nova Bank NRI Accounts (NRE and NRO)", "repatriation rules, interest, documentation, tax deduction at source"),
 "senior_citizen_savings": ("Nova Bank Senior Citizen Savings Account", "age criteria, extra interest, free services, nomination"),
 "recurring_deposit": ("Nova Bank Recurring Deposit", "tenure, minimum installment, penalty for missed installments, premature closure"),
 "net_banking_security": ("Nova Bank Net Banking and Mobile Security Policy", "login limits, OTP validity, fraud reporting windows, liability rules"),
 "kyc_account_closure": ("Nova Bank KYC and Account Closure Policy", "documents, re-KYC cycles, dormant accounts, closure charges and timelines"),
 "grievance_ombudsman": ("Nova Bank Grievance Redressal and Escalation", "complaint levels, resolution timelines, compensation, ombudsman escalation"),
 "neft_rtgs_imps": ("Nova Bank NEFT, RTGS and IMPS Charges", "limits, time windows, charges by slab, failed transfer refunds"),
 "travel_insurance": ("Nova Shield Travel Insurance", "plans, medical cover limits, trip delay, baggage loss, exclusions, claim deadlines"),
 "home_insurance": ("Nova Shield Home Insurance", "structure and contents cover, perils, exclusions, claim steps, sum insured limits"),
 "two_wheeler_insurance": ("Nova Shield Two-Wheeler Insurance", "own damage and third party, no-claim bonus slabs, deductibles, add-ons"),
 "critical_illness": ("Nova Shield Critical Illness Cover", "covered illnesses, survival period, waiting period, sum insured options"),
 "personal_accident": ("Nova Shield Personal Accident Insurance", "death and disability benefit percentages, exclusions, claim documents, deadlines"),
}
PROMPT = """Write the internal policy document "{title}" for the fictional {org}. Topic details: {hint}.
Format: Markdown with one '# ' title and 6-8 '## ' sections (eligibility, fees and charges, limits, timelines, conditions and exclusions, how to apply or claim, escalation, FAQs).
Length 700-900 words. Every section must contain at least three concrete numeric facts (INR amounts, percentages, days, months, tier names). Be precise and internally consistent. No placeholders, no real company names, no disclaimers."""

def gen(item):
    key, (title, hint) = item
    out = Path(POLICIES_DIR) / f"{key}.md"
    if out.exists() and not ARGS.force:
        return f"skip {out.name}"
    org = "Nova Shield Insurance" if "Nova Shield" in title else "Nova Bank"
    text = call_llm([{"role": "system", "content": "You write precise internal policy documents."},
                     {"role": "user", "content": PROMPT.format(title=title, org=org, hint=hint)}], model=AUDITOR_MODEL, temperature=0.7)
    out.write_text(text.strip() + "\n", encoding="utf-8")
    return f"wrote {out.name} ({len(text.split())} words)"

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--force", action="store_true"); ARGS = ap.parse_args()
    if MOCK_LLM:
        sys.exit("Turn MOCK_LLM off: this script needs your real OpenAI key.")
    with ThreadPoolExecutor(4) as ex:
        for line in ex.map(gen, TOPICS.items()):
            print(line)
    print("Done. Now run: python scripts/ingest.py")
