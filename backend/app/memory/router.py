"""
MindBridge Memory Router
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.service import get_student_id_for_user
from app.dependencies import CurrentUser
from app.memory.schemas import (
    MemoryItemCreate,
    MemoryItemResponse,
    MemoryListResponse,
    MemoryPinUpdate,
)
from app.memory.service import (
    create_memory_item,
    delete_memory_item,
    list_memory_items,
    pin_memory_item,
)
from database.session import get_db

router = APIRouter()


@router.post("/", response_model=MemoryItemResponse, status_code=201)
async def create_memory(
    payload: MemoryItemCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Store a new memory item for the current student."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await create_memory_item(db, student_id, payload)


@router.get("/", response_model=MemoryListResponse)
async def list_memories(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    memory_type: str | None = Query(None),
):
    """List memory items for the current student."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    items, total = await list_memory_items(db, student_id, memory_type)
    return MemoryListResponse(items=items, total=total)


@router.patch("/{memory_id}/pin", response_model=MemoryItemResponse)
async def pin_memory(
    memory_id: uuid.UUID,
    payload: MemoryPinUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Pin or unpin a memory item. Pinned memories are always included in AI context."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await pin_memory_item(db, memory_id, student_id, payload)


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a specific memory item."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    await delete_memory_item(db, memory_id, student_id)
