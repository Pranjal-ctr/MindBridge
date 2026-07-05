"""
MindBridge Memory Service
Business logic for AI-powered student memory system.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.schemas import MemoryItemCreate, MemoryItemResponse, MemoryPinUpdate
from database.models import MemoryItem


async def create_memory_item(
    db: AsyncSession, student_id: uuid.UUID, payload: MemoryItemCreate
) -> MemoryItemResponse:
    """Store a new memory item for a student."""
    item = MemoryItem(
        student_id=student_id,
        memory_type=payload.memory_type,
        content=payload.content,
        importance_score=payload.importance_score,
        confidence_score=payload.confidence_score,
        source_conversation_id=payload.source_conversation_id,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return MemoryItemResponse.model_validate(item)


async def list_memory_items(
    db: AsyncSession,
    student_id: uuid.UUID,
    memory_type: str | None = None,
) -> tuple[list[MemoryItemResponse], int]:
    """List memory items for a student."""
    query = select(MemoryItem).where(MemoryItem.student_id == student_id)
    count_query = select(func.count()).select_from(MemoryItem).where(MemoryItem.student_id == student_id)

    if memory_type:
        query = query.where(MemoryItem.memory_type == memory_type)
        count_query = count_query.where(MemoryItem.memory_type == memory_type)

    # Pinned first, then by importance + recency
    query = query.order_by(
        MemoryItem.is_pinned.desc(),
        MemoryItem.importance_score.desc().nullslast(),
        MemoryItem.created_at.desc(),
    )

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(query)
    items = result.scalars().all()

    return [MemoryItemResponse.model_validate(i) for i in items], total


async def delete_memory_item(
    db: AsyncSession, memory_id: uuid.UUID, student_id: uuid.UUID
) -> None:
    """Delete a specific memory item."""
    result = await db.execute(
        select(MemoryItem).where(
            MemoryItem.memory_id == memory_id,
            MemoryItem.student_id == student_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory item not found")
    await db.delete(item)
    await db.flush()


async def pin_memory_item(
    db: AsyncSession,
    memory_id: uuid.UUID,
    student_id: uuid.UUID,
    payload: MemoryPinUpdate,
) -> MemoryItemResponse:
    """Pin or unpin a memory item."""
    result = await db.execute(
        select(MemoryItem).where(
            MemoryItem.memory_id == memory_id,
            MemoryItem.student_id == student_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory item not found")

    item.is_pinned = payload.is_pinned
    await db.flush()
    await db.refresh(item)
    return MemoryItemResponse.model_validate(item)
