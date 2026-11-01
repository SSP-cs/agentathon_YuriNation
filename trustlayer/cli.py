"""Command-line interface for TrustLayer."""

import sys
import argparse
from trustlayer.graph import run_trustlayer

def main():
    parser = argparse.ArgumentParser(description="TrustLayer: Multi-Agent Policy Answer Verification Layer")
    parser.add_argument("question", nargs="?", help="Policy question to evaluate")
    parser.add_argument("--json", action="store_true", help="Output full JSON result")
    args = parser.parse_args()

    if not args.question:
        if not sys.stdin.isatty():
            question = sys.stdin.read().strip()
        else:
            print("Usage: python -m trustlayer.cli \"What is the minimum balance for a Nova Classic savings account?\"")
            sys.exit(1)
    else:
        question = args.question

    print(f"\n=======================================================")
    print(f"  TrustLayer Verification Engine")
    print(f"  Evaluating: \"{question}\"")
    print(f"=======================================================\n")

    result = run_trustlayer(question)

    if args.json:
        print(result.model_dump_json(indent=2))
        return

    status_color = "\033[92m" if result.status == "VERIFIED" else "\033[91m"
    reset_color = "\033[0m"

    print(f"Status: {status_color}[{result.status}]{reset_color} (Decision: {result.decision})")
    print(f"Support Scores: Agent A = {result.support_score_a:.2f} | Agent B = {result.support_score_b:.2f}")
    print(f"Agreement: {result.agreement} | Retries: {result.retry_count} | Latency: {result.latency_ms:.1f} ms\n")

    print("--- Auditor Verified Claims ---")
    for idx, c in enumerate(result.claims, 1):
        v_color = "\033[92m" if c.verdict == "SUPPORTED" else ("\033[91m" if c.verdict == "CONTRADICTED" else "\033[93m")
        print(f"{idx}. {v_color}[{c.verdict}]{reset_color} {c.claim}")
        if c.evidence_id:
            print(f"   Source [{c.evidence_id}]: \"{c.quote}\"")

    print("\n--- Output ---")
    if result.status == "VERIFIED":
        print(result.final_answer)
    else:
        print(f"REASON: {result.handoff_package.reason_code}")
        print(f"BRIEFING: {result.handoff_package.message}")
        if result.handoff_package.conflicts:
            print(f"CONFLICTS: {', '.join(result.handoff_package.conflicts)}")

    print(f"\nRun persisted to SQLite audit database (Run ID: {result.run_id})\n")

if __name__ == "__main__":
    main()

