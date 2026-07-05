"""
MindBridge Platform Admin (Phase 5 Group C) Tests
"""

import uuid

import pytest
from httpx import AsyncClient

from app.config import settings
from database.models import User


@pytest.mark.asyncio
async def test_platform_analytics(client: AsyncClient, admin_auth_headers, test_student_user):
    resp = await client.get("/admin/analytics/platform", headers=admin_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    for key in ("total_schools", "total_students", "total_counselors", "ai_cost_usd",
                "conversation_count", "revenue_usd"):
        assert key in data
    assert data["total_students"] >= 1  # the seeded test student


@pytest.mark.asyncio
async def test_ai_routes_list_and_update(client: AsyncClient, admin_auth_headers):
    listing = await client.get("/admin/ai/routes", headers=admin_auth_headers)
    assert listing.status_code == 200
    features = {r["feature_name"] for r in listing.json()["routes"]}
    assert {"comrade_chat", "memory_extraction", "title_generation"}.issubset(features)

    upd = await client.patch("/admin/ai/routes/comrade_chat",
                             json={"primary_model": "gemini-2.5-pro"}, headers=admin_auth_headers)
    assert upd.status_code == 200
    assert upd.json()["primary_model"] == "gemini-2.5-pro"


@pytest.mark.asyncio
async def test_register_and_verify_counselor(client: AsyncClient, admin_auth_headers):
    create = await client.post("/admin/counselors", json={
        "email": f"newcounselor_{uuid.uuid4().hex[:8]}@mindbridge.ai",
        "password": "CounselorPass1!",
        "first_name": "Nova", "last_name": "Advisor",
        "qualification": "LMFT", "specializations": ["Anxiety"], "languages": ["English"],
        "experience_years": 5, "is_verified": False,
    }, headers=admin_auth_headers)
    assert create.status_code == 201
    cid = create.json()["counselor_id"]
    assert create.json()["is_verified"] is False

    # It should appear in the admin list
    lst = await client.get("/admin/counselors", headers=admin_auth_headers)
    assert any(c["counselor_id"] == cid for c in lst.json()["counselors"])

    # Verify credentials
    verify = await client.patch(f"/admin/counselors/{cid}", json={"is_verified": True},
                                headers=admin_auth_headers)
    assert verify.status_code == 200
    assert verify.json()["is_verified"] is True


@pytest.mark.asyncio
async def test_user_disable_and_password_reset(client: AsyncClient, admin_auth_headers, test_student_user, db_session):
    resp = await client.patch(f"/admin/users/{test_student_user.user_id}",
                              json={"is_active": False, "new_password": "BrandNewPass1!"},
                              headers=admin_auth_headers)
    assert resp.status_code == 200

    await db_session.refresh(test_student_user)
    assert test_student_user.is_active is False
    assert test_student_user.password_hash is not None


@pytest.mark.asyncio
async def test_ai_route_change_reflected_by_config_loader(client: AsyncClient, admin_auth_headers, db_session):
    """Updating a route should change what the AI config loader resolves."""
    from app.ai.config_loader import load_feature_route

    await client.patch("/admin/ai/routes/title_generation",
                       json={"primary_model": "gemini-2.5-flash"}, headers=admin_auth_headers)

    route = await load_feature_route(db_session, "title_generation")
    assert route.primary_model == "gemini-2.5-flash"
