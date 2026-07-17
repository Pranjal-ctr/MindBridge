"""
Kio Memory Schemas
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# Valid memory types
VALID_MEMORY_TYPES = ["goal", "academic", "preference", "fact", "emotion", "relationship"]
MEMORY_TYPE_PATTERN = r"^(goal|academic|preference|fact|emotion|relationship)$"


class MemoryItemCreate(BaseModel):
    """Create a new memory item."""
    memory_type: str = Field(..., pattern=MEMORY_TYPE_PATTERN)
    content: str = Field(..., min_length=1)
    importance_score: float | None = Field(None, ge=0.0, le=1.0)
    confidence_score: float | None = Field(None, ge=0.0, le=1.0)
    source_conversation_id: uuid.UUID | None = None


class MemoryItemResponse(BaseModel):
    """Memory item response."""
    memory_id: uuid.UUID
    student_id: uuid.UUID
    memory_type: str
    content: str
    importance_score: float | None = None
    confidence_score: float | None = None
    is_pinned: bool = False
    source_conversation_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MemoryListResponse(BaseModel):
    """List of memory items."""
    items: list[MemoryItemResponse]
    total: int


class MemoryPinUpdate(BaseModel):
    """Pin or unpin a memory item."""
    is_pinned: bool
