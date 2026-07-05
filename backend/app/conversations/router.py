"""
MindBridge Conversations Router
ChatGPT-style conversation and message endpoints.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.schemas import (
    ConversationCreate,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
    MessageCreate,
    MessageListResponse,
    MessageResponse,
    SendMessageResponse,
)
from app.conversations.service import (
    create_conversation,
    delete_conversation,
    get_conversation,
    get_messages,
    get_student_id_for_user,
    list_conversations,
    send_message,
    send_ai_response,
    update_conversation,
)
from app.dependencies import CurrentUser, require_role
from database.session import get_db

router = APIRouter()


# -------------------------------------------------------------------
# Conversation CRUD
# -------------------------------------------------------------------

@router.post("/", response_model=ConversationResponse, status_code=201)
async def create_new_conversation(
    payload: ConversationCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new conversation. Students only."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await create_conversation(db, student_id, payload)


@router.get("/", response_model=ConversationListResponse)
async def list_my_conversations(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_archived: bool = Query(False),
):
    """List the current student's conversations."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    conversations, total = await list_conversations(db, student_id, page, page_size, include_archived)
    return ConversationListResponse(
        conversations=conversations, total=total, page=page, page_size=page_size
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation_detail(
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get a conversation with its messages."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    conversation = await get_conversation(db, conversation_id, student_id)
    messages, _, _ = await get_messages(db, conversation_id, student_id)

    response = ConversationDetailResponse.model_validate(conversation)
    response.messages = messages
    return response


@router.put("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation_endpoint(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update conversation title or archive status."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await update_conversation(db, conversation_id, student_id, payload)


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation_endpoint(
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Archive (soft-delete) a conversation."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    await delete_conversation(db, conversation_id, student_id)


# -------------------------------------------------------------------
# Messages
# -------------------------------------------------------------------

@router.post("/{conversation_id}/messages", response_model=SendMessageResponse, status_code=201)
async def send_new_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Send a message in a conversation.

    Flow:
    1. Store the user's message
    2. Call Comrade AI (Gemini 2.5 Flash)
    3. Store the AI response with metadata
    4. Return both messages
    """
    student_id = await get_student_id_for_user(db, current_user.user_id)

    # 1. Store user message
    user_msg = await send_message(db, conversation_id, student_id, current_user.user_id, payload)

    # 2+3. Generate and store AI response
    ai_msg = await send_ai_response(db, conversation_id, student_id, current_user.user_id, payload.message_text)

    return SendMessageResponse(user_message=user_msg, ai_message=ai_msg)


@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    cursor: str | None = Query(None, description="Message ID cursor for pagination"),
    limit: int = Query(50, ge=1, le=200),
):
    """Get messages in a conversation with cursor-based pagination."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    messages, has_more, next_cursor = await get_messages(
        db, conversation_id, student_id, cursor, limit
    )
    return MessageListResponse(messages=messages, has_more=has_more, next_cursor=next_cursor)
