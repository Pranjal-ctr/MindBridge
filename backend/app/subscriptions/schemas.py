"""
Kio Subscriptions Schemas
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class SubscriptionResponse(BaseModel):
    """Subscription details."""
    subscription_id: uuid.UUID
    tenant_id: uuid.UUID
    plan_name: str
    student_limit: int
    active_students: int
    billing_cycle: str
    amount: float
    start_date: date
    renewal_date: date | None = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionResponse(BaseModel):
    """Payment transaction."""
    transaction_id: uuid.UUID
    subscription_id: uuid.UUID
    payment_provider: str | None = None
    amount: float
    currency: str = "USD"
    payment_status: str
    transaction_reference: str | None = None
    paid_at: datetime | None = None

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
    total: int
