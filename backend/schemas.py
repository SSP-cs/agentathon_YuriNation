from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime, timezone

class ClaimStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

class DecisionVerdict(str, Enum):
    RELEASE = "RELEASE"
    RETRY = "RETRY"
    ESCALATE = "ESCALATE"

class RetrievedChunk(BaseModel):
    chunk_id: str
    document_name: str
    page_number: int
    text: str
    score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ClaimItem(BaseModel):
    claim_id: str
    text: str
    status: ClaimStatus
    source_agent: str = "Agent A" # Agent A, Agent B, or Both
    evidence_text: Optional[str] = None
    document_name: Optional[str] = None
    page_number: Optional[int] = None
    confidence_score: float = 0.0
    reasoning: str = ""

class AgentResponse(BaseModel):
    agent_id: str
    model_name: str
    provider: str
    answer: str
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0

class AuditorResult(BaseModel):
    claims: List[ClaimItem] = Field(default_factory=list)
    total_claims: int = 0
    supported_claims: int = 0
    unsupported_claims: int = 0
    contradicted_claims: int = 0
    overall_confidence: float = 0.0
    auditor_explanation: str = ""
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0

class VerificationDecision(BaseModel):
    verdict: DecisionVerdict
    reason: str
    retry_count: int = 0
    escalation_id: Optional[str] = None

class QuestionRequest(BaseModel):
    question: str
    category: Optional[str] = "Policy"
    force_mock: Optional[bool] = False

class VerificationResponse(BaseModel):
    session_id: str
    question: str
    status: str # "VERIFIED_RELEASED", "ESCALATED_HUMAN_REVIEW", "PROCESSING_RETRY"
    final_answer: Optional[str] = None
    agent_a: AgentResponse
    agent_b: AgentResponse
    auditor: AuditorResult
    decision: VerificationDecision
    evidence: List[RetrievedChunk] = Field(default_factory=list)
    retry_history: List[Dict[str, Any]] = Field(default_factory=list)
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    is_mock_mode: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ReviewActionRequest(BaseModel):
    session_id: str
    decision: str # "APPROVE", "REJECT", "REQUEST_EVIDENCE"
    reviewer_notes: str = ""
    reviewed_by: str = "Compliance Officer"

class DocumentMeta(BaseModel):
    id: str
    filename: str
    file_type: str
    chunk_count: int
    upload_time: str
    file_size_kb: float

class DashboardMetrics(BaseModel):
    total_questions: int = 0
    verified_answers: int = 0
    escalated_questions: int = 0
    unsupported_claims_caught: int = 0
    avg_response_time_ms: float = 0.0
    avg_token_usage: float = 0.0
    total_cost_usd: float = 0.0
    hallucination_prevention_rate: float = 0.0
