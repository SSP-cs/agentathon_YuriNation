import os
import sys
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.config import settings
from retrieval.document_processor import process_file
from retrieval.retriever import retriever
from database.crud import save_document_record
from agents.orchestrator import run_verification_pipeline
from evaluations.metrics import calculate_comprehensive_metrics

def seed_sample_documents():
    """Index sample policy documents into ChromaDB and SQLite."""
    print("Indexing sample policy documents...")
    sample_files = [
        ("ApexBank_Retail_Policy_2026.pdf", os.path.join(settings.BASE_DIR, "sample_data", "ApexBank_Retail_Policy_2026.pdf")),
        ("Zenith_Health_Insurance_Policy.pdf", os.path.join(settings.BASE_DIR, "sample_data", "Zenith_Health_Insurance_Policy.pdf")),
    ]

    for filename, filepath in sample_files:
        if os.path.exists(filepath):
            file_size_kb = round(os.path.getsize(filepath) / 1024.0, 2)
            chunks = process_file(filepath, filename)
            retriever.add_chunks(chunks)
            save_document_record(
                doc_id=f"sample_{filename.replace('.', '_')}",
                filename=filename,
                file_type="PDF",
                file_size_kb=file_size_kb,
                chunk_count=len(chunks)
            )
            print(f"Indexed '{filename}' with {len(chunks)} chunks.")
        else:
            print(f"Warning: File not found {filepath}")

def run_benchmark_suite(sample_count: int = 6):
    """Executes a benchmark run across sample questions and logs results."""
    seed_sample_documents()
    
    questions_file = os.path.join(settings.BASE_DIR, "sample_data", "sample_questions.json")
    with open(questions_file, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print(f"\nRunning benchmark on {sample_count} policy questions...")
    for idx, item in enumerate(questions[:sample_count]):
        q = item["question"]
        q_type = item["type"]
        print(f"\n[{idx+1}/{sample_count}] ({q_type}) {q}")
        
        res = run_verification_pipeline(question=q, category=item.get("category", "Policy"), force_mock=True)
        print(f" -> Status: {res.status} | Verdict: {res.decision.verdict.value} | Claims: {res.auditor.total_claims} (Supp: {res.auditor.supported_claims}, Unsupp: {res.auditor.unsupported_claims}) | Retries: {res.decision.retry_count}")

    metrics = calculate_comprehensive_metrics()
    print("\n" + "="*50)
    print("BENCHMARK METRICS SUMMARY")
    print("="*50)
    for k, v in metrics.items():
        print(f" - {k}: {v}")
    print("="*50)
    return metrics

if __name__ == "__main__":
    run_benchmark_suite(sample_count=6)
