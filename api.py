"""FastAPI backend service exposing TrustLayer verification API."""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure project root in sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from trustlayer.config import (
    ANSWER_MODEL_A,
    ANSWER_MODEL_B,
    AUDITOR_MODEL,
    MOCK_LLM,
    USE_CACHE,
    MIN_SIM,
    SUPPORT_THRESHOLD,
    MAX_RETRIES,
)
from trustlayer.graph import run_trustlayer
from trustlayer.audit_db import get_runs, get_run_details
from trustlayer.retrieval import get_collection

app = FastAPI(
    title="TrustLayer API",
    description="Multi-agent verification layer for customer-support policy answers",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskRequest(BaseModel):
    question: str
    run_id: Optional[str] = None

@app.get("/")
@app.get("/health")
def health_check():
    """Health check endpoint displaying system configuration and index status."""
    try:
        col = get_collection()
        doc_count = col.count()
    except Exception:
        doc_count = 0

    return {
        "status": "healthy",
        "mock_mode": MOCK_LLM,
        "cache_enabled": USE_CACHE,
        "indexed_chunks": doc_count,
        "models": {
            "agent_a": ANSWER_MODEL_A,
            "agent_b": ANSWER_MODEL_B,
            "auditor": AUDITOR_MODEL,
        },
        "thresholds": {
            "min_sim": MIN_SIM,
            "support_threshold": SUPPORT_THRESHOLD,
            "max_retries": MAX_RETRIES,
        }
    }

@app.post("/ask")
def ask_question(req: AskRequest) -> Dict[str, Any]:
    """Execute TrustLayer verification graph on a policy question."""
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    result = run_trustlayer(
        question=req.question.strip(),
        run_id=req.run_id
    )

    return result.model_dump()

@app.get("/runs")
def list_runs(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None, description="Filter by VERIFIED or ESCALATED")
) -> List[Dict[str, Any]]:
    """Retrieve historical runs from the SQLite audit database."""
    return get_runs(limit=limit, status_filter=status)

@app.get("/runs/{run_id}")
def get_single_run(run_id: str) -> Dict[str, Any]:
    """Retrieve full trace and claims for a specific run."""
    run_details = get_run_details(run_id)
    if not run_details:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    return run_details

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)

