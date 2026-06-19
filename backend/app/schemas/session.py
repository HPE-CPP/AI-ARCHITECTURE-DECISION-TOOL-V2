"""
Pydantic schemas for Analysis Sessions and Results.
Keeps the response shape identical to the original in-memory API.
"""
from typing import Optional, Any
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Analysis response  (same shape the frontend already consumes)
# ---------------------------------------------------------------------------
class AnalysisResponse(BaseModel):
    analysis_id: str
    status: str
    project_name: Optional[str] = None
    project_id: Optional[str] = None
    signals: Optional[dict[str, Any]] = None
    scores: Optional[dict[str, Any]] = None
    recommended: Optional[str] = None
    confidence: Optional[float] = None
    ranking: Optional[list] = None
    suitability: Optional[dict[str, Any]] = None
    factor_breakdown: Optional[dict[str, Any]] = None
    why_not: Optional[dict[str, Any]] = None
    architecture_details: Optional[dict[str, Any]] = None
    followup_questions: Optional[list] = None
    sensitivity: Optional[dict[str, Any]] = None
    decision_trace: Optional[list] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    document_info: Optional[dict[str, Any]] = None
    cost_analysis: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Follow-up answers request body
# ---------------------------------------------------------------------------
class FollowUpAnswers(BaseModel):
    analysis_id: str
    answers: dict[str, str]


# ---------------------------------------------------------------------------
# Questionnaire input
# ---------------------------------------------------------------------------
class QuestionnaireInput(BaseModel):
    dataset_size: Optional[str] = None
    query_volume: Optional[str] = None
    latency_requirement: Optional[str] = None
    data_volatility: Optional[str] = None
    accuracy_requirement: Optional[str] = None
    domain_specificity: Optional[str] = None
    security_level: Optional[str] = None
    cost_sensitivity: Optional[str] = None
    deployment_preference: Optional[str] = None
    user_scale: Optional[str] = None
    citation_requirement: Optional[str] = None
    context_size: Optional[str] = None
