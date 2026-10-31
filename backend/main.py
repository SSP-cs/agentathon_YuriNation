import os
import shutil
import uuid
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.schemas import (
    QuestionRequest, VerificationResponse, ReviewActionRequest,
    DocumentMeta, DashboardMetrics
)
from backend.token_tracker import token_tracker
from database.crud import (
    list_documents, save_document_record, delete_document_record,
    get_pending_escalations, record_escalation_review, get_audit_logs,
    get_dashboard_metrics, get_session_details
)
from retrieval.document_processor import process_file
from retrieval.retriever import retriever
from agents.orchestrator import run_verification_pipeline

app = FastAPI(
    title="TrustLayer API",
    description="Cybersecurity & AI Governance Policy Verification Engine",
    version="1.0.0"
)

# Enable CORS for Streamlit or web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "indexed_chunks": retriever.count_chunks(),
        "providers_configured": {
            "openai": bool(settings.OPENAI_API_KEY),
            "anthropic": bool(settings.ANTHROPIC_API_KEY),
            "gemini": bool(settings.GEMINI_API_KEY),
            "groq": bool(settings.GROQ_API_KEY)
        },
        "active_models": {
            "agent_a": f"{settings.AGENT_A_PROVIDER} ({settings.AGENT_A_MODEL})",
            "agent_b": f"{settings.AGENT_B_PROVIDER} ({settings.AGENT_B_MODEL})",
            "auditor": f"{settings.AUDITOR_PROVIDER} ({settings.AUDITOR_MODEL})"
        }
    }

@app.post("/api/verify", response_model=VerificationResponse)
def verify_policy_question(req: QuestionRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    try:
        response = run_verification_pipeline(
            question=req.question,
            category=req.category or "Policy",
            force_mock=req.force_mock or False
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification pipeline failed: {str(e)}")

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".pdf", ".txt", ".md"]:
        raise HTTPException(status_code=400, detail="Unsupported format. Only PDF and TXT files are accepted.")

    doc_id = str(uuid.uuid4())
    save_path = os.path.join(settings.DOCS_DIR, f"{doc_id}_{filename}")
    
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size_kb = round(os.path.getsize(save_path) / 1024.0, 2)

    try:
        chunks = process_file(save_path, filename)
        retriever.add_chunks(chunks)
        save_document_record(
            doc_id=doc_id,
            filename=filename,
            file_type=ext.replace(".", "").upper(),
            file_size_kb=file_size_kb,
            chunk_count=len(chunks)
        )
        return {
            "status": "success",
            "document_id": doc_id,
            "filename": filename,
            "chunk_count": len(chunks),
            "file_size_kb": file_size_kb
        }
    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")

@app.get("/api/documents", response_model=List[DocumentMeta])
def get_documents():
    return list_documents()

@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    docs = list_documents()
    target = next((d for d in docs if d.id == doc_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Document not found.")

    retriever.delete_document(target.filename)
    delete_document_record(doc_id)
    return {"status": "success", "message": f"Document '{target.filename}' deleted successfully."}

@app.get("/api/escalations")
def get_escalations():
    return get_pending_escalations()

@app.post("/api/escalations/review")
def review_escalation(req: ReviewActionRequest):
    if req.decision not in ["APPROVE", "REJECT", "REQUEST_EVIDENCE"]:
        raise HTTPException(status_code=400, detail="Invalid decision. Choose APPROVE, REJECT, or REQUEST_EVIDENCE.")
    
    record_escalation_review(
        session_id=req.session_id,
        decision=req.decision,
        notes=req.reviewer_notes,
        reviewer=req.reviewed_by
    )
    return {"status": "success", "message": f"Escalation {req.session_id} marked as {req.decision}."}

@app.get("/api/audit-logs")
def fetch_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    search: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None)
):
    return get_audit_logs(limit=limit, search=search, event_type=event_type)

@app.get("/api/metrics", response_model=DashboardMetrics)
def fetch_metrics():
    return get_dashboard_metrics()

@app.get("/api/sessions/{session_id}")
def fetch_session(session_id: str):
    session = get_session_details(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session

