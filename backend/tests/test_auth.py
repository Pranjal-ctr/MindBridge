"""
Kio Auth Tests
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test the health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Kio API"


@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient, test_tenant):
    """Test user registration."""
    response = await client.post("/auth/signup", json={
        "email": "newuser@test.com",
        "password": "SecurePass123!",
        "first_name": "New",
        "last_name": "User",
        "role": "student",
        "phone": "+1 555 010 0000",
        "school_code": test_tenant.school_code,
    })
    assert response.status_code == 201
    data = response.json()
    assert "tokens" in data
    assert data["tokens"]["token_type"] == "bearer"
    assert data["user"]["email"] == "newuser@test.com"
    assert data["user"]["role"] == "student"


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient, test_tenant, test_student_user):
    """Test signup with existing email fails."""
    response = await client.post("/auth/signup", json={
        "email": test_student_user.email,
        "password": "AnotherPass123!",
        "first_name": "Dup",
        "last_name": "User",
        "role": "student",
        "phone": "+1 555 010 0001",
        "school_code": test_tenant.school_code,
    })
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_signup_duplicate_email_case_insensitive(client: AsyncClient, test_tenant, test_student_user):
    """Emails differing only by case are the same account."""
    response = await client.post("/auth/signup", json={
        "email": test_student_user.email.upper(),
        "password": "AnotherPass123!",
        "first_name": "Dup",
        "last_name": "User",
        "role": "student",
        "phone": "+1 555 010 0002",
        "school_code": test_tenant.school_code,
    })
    assert response.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["counselor", "school_admin", "admin"])
async def test_staff_self_signup_rejected(client: AsyncClient, test_tenant, role):
    """Staff and admin roles cannot self-register via /auth/signup."""
    response = await client.post("/auth/signup", json={
        "email": f"escalation_{role}@test.com",
        "password": "SecurePass123!",
        "first_name": "Evil",
        "last_name": "Actor",
        "role": role,
        "phone": "+1 555 010 0003",
        "school_code": test_tenant.school_code,
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_rate_limited(client: AsyncClient):
    """Repeated login attempts are throttled."""
    statuses = []
    for _ in range(12):
        resp = await client.post("/auth/login", json={
            "email": "nobody@test.com",
            "password": "wrong",
        })
        statuses.append(resp.status_code)
    assert 429 in statuses


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_student_user):
    """Test login with valid credentials."""
    response = await client.post("/auth/login", json={
        "email": test_student_user.email,
        "password": "TestPassword123!",
    })
    assert response.status_code == 200
    data = response.json()
    assert "tokens" in data
    assert data["user"]["user_id"] == str(test_student_user.user_id)


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_student_user):
    """Test login with wrong password."""
    response = await client.post("/auth/login", json={
        "email": test_student_user.email,
        "password": "WrongPassword!",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, student_auth_headers):
    """Test getting current user profile."""
    response = await client.get("/auth/me", headers=student_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "student"


@pytest.mark.asyncio
async def test_unauthorized_access(client: AsyncClient):
    """Test accessing protected endpoint without token."""
    response = await client.get("/auth/me")
    assert response.status_code == 403
