"""
Kio Conversations Schemas
Pydantic v2 models for conversations and messages.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# -------------------------------------------------------------------
# Conversations
# -------------------------------------------------------------------

class ConversationCreate(BaseModel):
    """Create a new conversation."""
    title: str | None = Field(None, max_length=255)


class ConversationUpdate(BaseModel):
    """Update conversation metadata."""
    title: str | None = Field(None, max_length=255)
    is_archived: bool | None = None


class ConversationResponse(BaseModel):
    """Conversation with metadata."""
    conversation_id: uuid.UUID
    student_id: uuid.UUID
    title: str | None = None
    ai_generated_title: bool = False
    is_archived: bool = False
    total_messages: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetailResponse(ConversationResponse):
    """Conversation with messages included."""
    messages: list[MessageResponse] = []


class ConversationListResponse(BaseModel):
    """Paginated conversation list."""
    conversations: list[ConversationResponse]
    total: int
    page: int
    page_size: int


# -------------------------------------------------------------------
# Messages
# -------------------------------------------------------------------

class MessageCreate(BaseModel):
    """Send a new message in a conversation.
    sender_type and metadata are server-controlled -- clients cannot forge AI/system messages."""
    message_text: str = Field(..., min_length=1, max_length=4000)


class MessageResponse(BaseModel):
    """Message in a conversation."""
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    sender_type: str
    sender_id: uuid.UUID | None = None
    message_text: str
    metadata: dict | None = Field(default=None, alias="metadata_")
    token_count: int | None = None
    sentiment: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class MessageListResponse(BaseModel):
    """Paginated message list (cursor-based)."""
    messages: list[MessageResponse]
    has_more: bool
    next_cursor: str | None = None


class SendMessageResponse(BaseModel):
    """Response after sending a message: includes user message + AI response."""
    user_message: MessageResponse
    ai_message: MessageResponse
