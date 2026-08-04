"""
Kio Risk Schemas
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# Structured outcomes a counselor can record when resolving an assessment.
# Kept as a closed vocabulary so the accumulating dataset stays clean/queryable.
RISK_OUTCOMES = [
    "no_action_needed",
    "monitoring",
    "counseling_scheduled",
    "parent_contacted",
    "escalated",
    "referred_external",
    "false_positive",
]


class RiskAssessmentCreate(BaseModel):
    """Create a risk assessment."""
    student_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    risk_score: float | None = Field(None, ge=0.0, le=100.0)
    risk_level: str = Field(..., pattern=r"^(green|yellow|red|critical)$")
    trigger_reason: str | None = None
    generated_by: str | None = Field(None, max_length=50)


class RiskAssessmentResponse(BaseModel):
    """Risk assessment response."""
    risk_id: uuid.UUID
    student_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    risk_score: float | None = None
    risk_level: str
    categories: dict | None = None
    confidence: float | None = None
    summary: str | None = None
    trigger_reason: str | None = None
    generated_by: str | None = None
    review_status: str | None = None
    reviewed_by: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    counselor_risk_level: str | None = None
    verdict: str | None = None
    outcome: str | None = None
    resolution_note: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RiskAlertResponse(BaseModel):
    """Risk alert with student info."""
    risk_id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    risk_level: str
    risk_score: float | None = None
    trigger_reason: str | None = None
    created_at: datetime


class RiskListResponse(BaseModel):
    assessments: list[RiskAssessmentResponse]
    total: int


class RiskAlertListResponse(BaseModel):
    alerts: list[RiskAlertResponse]
    total: int


# -------------------------------------------------------------------
# Counselor review queue
# -------------------------------------------------------------------

class RiskQueueItem(BaseModel):
    """Pending AI/tripwire assessment awaiting counselor review."""
    risk_id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    risk_level: str
    risk_score: float | None = None
    categories: dict | None = None
    confidence: float | None = None
    # True when the model's confidence is below the configured floor: the
    # counselor should read this as "not enough signal", not "low risk".
    inconclusive: bool = False
    summary: str | None = None
    trigger_reason: str | None = None
    generated_by: str | None = None
    created_at: datetime


class RiskQueueListResponse(BaseModel):
    items: list[RiskQueueItem]
    total: int


class RiskReviewUpdate(BaseModel):
    """Counselor action on a queued assessment.

    `review_status` is the only required field, so the pre-existing
    {review_status} payload keeps working. The rest capture the counselor's
    judgment for the evaluation dataset -- all optional.
    """
    review_status: str = Field(..., pattern=r"^(acknowledged|resolved)$")
    verdict: str | None = Field(None, pattern=r"^(agree|disagree)$")
    counselor_risk_level: str | None = Field(
        None, pattern=r"^(green|yellow|red|critical)$"
    )
    outcome: str | None = None
    note: str | None = Field(None, max_length=2000)

    @field_validator("outcome")
    @classmethod
    def _known_outcome(cls, v: str | None) -> str | None:
        if v is not None and v not in RISK_OUTCOMES:
            raise ValueError(f"outcome must be one of {RISK_OUTCOMES}")
        return v
