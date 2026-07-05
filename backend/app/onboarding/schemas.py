"""
MindBridge Onboarding Schemas
Student first-login questionnaire (max 5 questions).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OnboardingSubmit(BaseModel):
    """Student's answers to the first-login questionnaire."""
    class_level: str = Field(..., max_length=30, description="e.g. Class 10, College")
    help_goals: list[str] = Field(default_factory=list, max_length=20)
    hobbies: list[str] = Field(default_factory=list, max_length=20)
    strengths: list[str] = Field(default_factory=list, max_length=20)
    interaction_style: str = Field(..., max_length=50, description="How Comrade should interact")


class OnboardingResponse(BaseModel):
    """Stored onboarding responses, or null if not completed."""
    class_level: str | None = None
    help_goals: list[str] = []
    hobbies: list[str] = []
    strengths: list[str] = []
    interaction_style: str | None = None
    completed_at: datetime

    model_config = {"from_attributes": True}
