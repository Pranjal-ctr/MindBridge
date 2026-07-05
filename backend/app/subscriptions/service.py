"""
MindBridge Subscriptions Service
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.subscriptions.schemas import SubscriptionResponse, TransactionResponse
from database.models import PaymentTransaction, Subscription


async def get_current_subscription(
    db: AsyncSession, tenant_id: uuid.UUID
) -> SubscriptionResponse:
    """Get the tenant's active subscription."""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.tenant_id == tenant_id, Subscription.status == "active")
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found",
        )

    return SubscriptionResponse.model_validate(subscription)


async def list_transactions(
    db: AsyncSession, tenant_id: uuid.UUID
) -> tuple[list[TransactionResponse], int]:
    """List payment transactions for a tenant."""
    query = (
        select(PaymentTransaction)
        .join(Subscription, PaymentTransaction.subscription_id == Subscription.subscription_id)
        .where(Subscription.tenant_id == tenant_id)
        .order_by(PaymentTransaction.paid_at.desc().nullslast())
    )

    count_query = (
        select(func.count())
        .select_from(PaymentTransaction)
        .join(Subscription, PaymentTransaction.subscription_id == Subscription.subscription_id)
        .where(Subscription.tenant_id == tenant_id)
    )

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(query)
    transactions = result.scalars().all()

    return [TransactionResponse.model_validate(t) for t in transactions], total
