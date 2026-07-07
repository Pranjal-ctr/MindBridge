"""
Counselor review queue API: RBAC, tenant isolation, ordering, review transitions.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.utils import create_access_token
from database.models import RiskAssessment, StudentProfile, Tenant, User
from tests.conftest import hash_password


@pytest_asyncio.fixture
async def counselor_auth_headers(db_session: AsyncSession, test_tenant: Tenant):
    user = User(
        user_id=uuid.uuid4(), tenant_id=test_tenant.tenant_id,
        email=f"coun_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("x"), role="counselor",
        first_name="Cora", last_name="Counselor",
    )
    db_session.add(user)
    await db_session.flush()
    token = create_access_token({
        "sub": str(user.user_id),
        "tenant_id": str(test_tenant.tenant_id),
        "role": "counselor",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def pending_assessments(db_session: AsyncSession, test_student_user: User):
    profile = (await db_session.execute(
        select(StudentProfile).where(StudentProfile.user_id == test_student_user.user_id)
    )).scalar_one()

    red = RiskAssessment(
        student_id=profile.student_id, risk_level="red", risk_score=70,
        generated_by="ai_pipeline", review_status="pending",
        summary="Persistent distress.",
    )
    critical = RiskAssessment(
        student_id=profile.student_id, risk_level="critical", risk_score=92,
        generated_by="keyword_tripwire", review_status="pending",
    )
    resolved = RiskAssessment(
        student_id=profile.student_id, risk_level="red", risk_score=68,
        generated_by="ai_pipeline", review_status="resolved",
    )
    unqueued = RiskAssessment(
        student_id=profile.student_id, risk_level="green", risk_score=10,
        generated_by="ai_pipeline",
    )
    db_session.add_all([red, critical, resolved, unqueued])
    await db_session.flush()
    return red, critical, resolved, unqueued


@pytest.mark.asyncio
async def test_queue_lists_pending_most_severe_first(
    client: AsyncClient, counselor_auth_headers, pending_assessments
):
    red, critical, _resolved, _unqueued = pending_assessments

    resp = await client.get("/risk/queue", headers=counselor_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["items"][0]["risk_id"] == str(critical.risk_id)  # critical first
    assert body["items"][1]["risk_id"] == str(red.risk_id)
    assert body["items"][1]["summary"] == "Persistent distress."
    assert body["items"][0]["student_name"] == "Test Student"


@pytest.mark.asyncio
async def test_queue_forbidden_for_students(client: AsyncClient, student_auth_headers):
    resp = await client.get("/risk/queue", headers=student_auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_review_acknowledges_assessment(
    client: AsyncClient, counselor_auth_headers, pending_assessments, db_session
):
    red, _critical, _resolved, _unqueued = pending_assessments

    resp = await client.patch(
        f"/risk/queue/{red.risk_id}",
        headers=counselor_auth_headers,
        json={"review_status": "acknowledged"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["review_status"] == "acknowledged"
    assert body["reviewed_by"] is not None
    assert body["reviewed_at"] is not None

    # Gone from the queue
    queue = await client.get("/risk/queue", headers=counselor_auth_headers)
    ids = [item["risk_id"] for item in queue.json()["items"]]
    assert str(red.risk_id) not in ids


@pytest.mark.asyncio
async def test_review_unqueued_assessment_conflicts(
    client: AsyncClient, counselor_auth_headers, pending_assessments
):
    _red, _critical, _resolved, unqueued = pending_assessments
    resp = await client.patch(
        f"/risk/queue/{unqueued.risk_id}",
        headers=counselor_auth_headers,
        json={"review_status": "resolved"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_review_cross_tenant_is_404(
    client: AsyncClient, db_session, pending_assessments
):
    red, _critical, _resolved, _unqueued = pending_assessments

    other_tenant = Tenant(
        tenant_id=uuid.uuid4(), tenant_name="Other School", tenant_type="school",
        school_code=f"OTHER{uuid.uuid4().hex[:5].upper()}", status="active",
    )
    db_session.add(other_tenant)
    await db_session.flush()
    outsider = User(
        user_id=uuid.uuid4(), tenant_id=other_tenant.tenant_id,
        email=f"coun_{uuid.uuid4().hex[:8]}@other.com",
        password_hash=hash_password("x"), role="counselor",
        first_name="Out", last_name="Sider",
    )
    db_session.add(outsider)
    await db_session.flush()
    token = create_access_token({
        "sub": str(outsider.user_id),
        "tenant_id": str(other_tenant.tenant_id),
        "role": "counselor",
    })

    resp = await client.patch(
        f"/risk/queue/{red.risk_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"review_status": "resolved"},
    )
    assert resp.status_code == 404
