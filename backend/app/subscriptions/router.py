"""
Kio Subscriptions Router
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentTenant, require_role
from app.subscriptions.schemas import SubscriptionResponse, TransactionListResponse
from app.subscriptions.service import get_current_subscription, list_transactions
from database.session import get_db

router = APIRouter()


@router.get(
    "/current",
    response_model=SubscriptionResponse,
    dependencies=[Depends(require_role("school_admin", "admin"))],
)
async def get_subscription(
    tenant_id: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get the current tenant's active subscription."""
    return await get_current_subscription(db, tenant_id)


@router.get(
    "/transactions",
    response_model=TransactionListResponse,
    dependencies=[Depends(require_role("school_admin", "admin"))],
)
async def get_transactions(
    tenant_id: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List payment transactions for the current tenant."""
    transactions, total = await list_transactions(db, tenant_id)
    return TransactionListResponse(transactions=transactions, total=total)
