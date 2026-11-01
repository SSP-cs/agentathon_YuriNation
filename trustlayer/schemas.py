"""Pydantic schemas and typed definitions for TrustLayer."""

from typing import List, Dict, Optional, Literal, Any
from pydantic import BaseModel, Field

class EvidenceChunk(BaseModel):
    """Retrieved source evidence chunk."""
    id: str = Field(description="Unique chunk identifier, e.g. S1, S2")
    content: str = Field(description="Text content of the evidence chunk")
    source: str = Field(description="Originating policy document filename")
    section: str = Field(description="Document heading/section name")
    score: float = Field(default=0.0, description="Similarity score between 0.0 and 1.0")

class PlannerOutput(BaseModel):
    """Output from the planner node."""
    sub_queries: List[str] = Field(description="1 to 4 targeted retrieval sub-queries", min_length=1, max_length=4)
    required_facts: List[str] = Field(description="Key policy facts required to answer accurately")

class AnswerOutput(BaseModel):
    """Output from an answering agent (Agent A or Agent B)."""
    answer: str = Field(description="Drafted answer text")
    used_evidence_ids: List[str] = Field(default_factory=list, description="IDs of evidence chunks referenced, e.g. ['S1', 'S2']")

class ClaimVerdict(BaseModel):
    """Verification verdict for an atomic claim."""
    claim: str = Field(description="Atomic factual proposition extracted from the answer")
    verdict: Literal["SUPPORTED", "UNSUPPORTED", "CONTRADICTED"] = Field(description="Audit verification verdict")
    evidence_id: Optional[str] = Field(default=None, description="ID of source chunk that supports or contradicts the claim")
    quote: Optional[str] = Field(default=None, description="Direct supporting or contradicting verbatim excerpt from source")
    reasoning: str = Field(default="", description="Auditor explanation for the verdict")

class AuditorOutput(BaseModel):
    """Comprehensive output from the auditor node."""
    claims_a: List[ClaimVerdict] = Field(default_factory=list, description="Atomic claim verdicts for Agent A")
    claims_b: List[ClaimVerdict] = Field(default_factory=list, description="Atomic claim verdicts for Agent B")
    support_score_a: float = Field(default=0.0, description="Ratio of supported claims to total claims for Agent A (0.0 - 1.0)")
    support_score_b: float = Field(default=0.0, description="Ratio of supported claims to total claims for Agent B (0.0 - 1.0)")
    agreement: Literal["AGREE", "MINOR_DIFFERENCE", "CONFLICT"] = Field(description="Inter-agent agreement assessment")
    conflicting_facts: List[str] = Field(default_factory=list, description="List of specific points where Agent A and B disagree")
    reasoning: str = Field(default="", description="High-level reasoning summarizing verification and comparison")

class HandoffPackage(BaseModel):
    """Human-in-the-loop escalation payload."""
    question: str
    answer_a: Optional[str] = None
    answer_b: Optional[str] = None
    claim_verdicts: List[Dict[str, Any]] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    reason_code: str = Field(description="NO_EVIDENCE | LOW_SUPPORT | AGENT_CONFLICT")
    message: str = Field(description="Human operator briefing")

class TrustLayerRunResult(BaseModel):
    """Final result of a TrustLayer execution."""
    run_id: str
    question: str
    decision: Literal["RELEASE", "ESCALATE"]
    status: Literal["VERIFIED", "ESCALATED"]
    final_answer: Optional[str] = None
    handoff_package: Optional[HandoffPackage] = None
    support_score_a: float = 0.0
    support_score_b: float = 0.0
    agreement: str = "AGREE"
    retry_count: int = 0
    latency_ms: float = 0.0
    evidence_chunks: List[EvidenceChunk] = Field(default_factory=list)
    claims: List[ClaimVerdict] = Field(default_factory=list)
    event_trace: List[Dict[str, Any]] = Field(default_factory=list)
    answer_a: Optional[str] = None
    answer_b: Optional[str] = None

