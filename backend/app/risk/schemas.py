"""
MindBridge Risk Schemas
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


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
    trigger_reason: str | None = None
    generated_by: str | None = None
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
