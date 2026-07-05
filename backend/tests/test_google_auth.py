"""
MindBridge Google Auth Tests
Google ID-token verification is monkeypatched so no network/creds are needed.
"""

import uuid

import pytest
from httpx import AsyncClient

import app.auth.service as auth_service
from app.auth.utils import hash_password
from database.models import User


def _fake_google(monkeypatch, sub: str, email: str, name: str = "Google User"):
    """Patch verify_google_id_token (imported inside google_authenticate)."""
    def _verify(_token: str) -> dict:
        return {
            "sub": sub,
            "email": email.lower(),
            "email_verified": True,
            "name": name,
            "picture": "https://example.com/p.png",
        }
    monkeypatch.setattr("app.auth.google.verify_google_id_token", _verify)


@pytest.mark.asyncio
async def test_google_new_user_requires_registration(client: AsyncClient, monkeypatch):
    _fake_google(monkeypatch, "google-sub-1", "newby@gmail.com", "New Person")
    resp = await client.post("/auth/google", json={"id_token": "x" * 20})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "registration_required"
    assert data["registration_token"]
    assert data["email"] == "newby@gmail.com"
    assert data["first_name"] == "New"


@pytest.mark.asyncio
async def test_google_signup_completion(client: AsyncClient, test_tenant, monkeypatch):
    _fake_google(monkeypatch, "google-sub-2", "gstudent@gmail.com", "Grace Student")
    start = await client.post("/auth/google", json={"id_token": "x" * 20})
    reg_token = start.json()["registration_token"]

    done = await client.post("/auth/google/complete", json={
        "registration_token": reg_token,
        "role": "student",
        "phone": "+1 555 222 3333",
        "school_code": test_tenant.school_code,
    })
    assert done.status_code == 201
    body = done.json()
    assert body["user"]["email"] == "gstudent@gmail.com"
    assert body["user"]["role"] == "student"
    assert body["tokens"]["access_token"]


@pytest.mark.asyncio
async def test_google_login_existing_google_user(client: AsyncClient, db_session, test_tenant, monkeypatch):
    # Seed a Google-linked user directly
    user = User(
        user_id=uuid.uuid4(), tenant_id=test_tenant.tenant_id,
        email="returning@gmail.com", password_hash=None,
        google_sub="google-sub-3", auth_provider="google",
        role="parent", first_name="Ret", last_name="Urning", is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    _fake_google(monkeypatch, "google-sub-3", "returning@gmail.com")
    resp = await client.post("/auth/google", json={"id_token": "x" * 20})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "authenticated"
    assert data["user"]["user_id"] == str(user.user_id)


@pytest.mark.asyncio
async def test_google_links_to_existing_password_account(client: AsyncClient, db_session, test_tenant, monkeypatch):
    # Existing email/password account with no google_sub
    user = User(
        user_id=uuid.uuid4(), tenant_id=test_tenant.tenant_id,
        email="hybrid@gmail.com", password_hash=hash_password("Passw0rd!"),
        role="student", first_name="Hy", last_name="Brid", is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    _fake_google(monkeypatch, "google-sub-4", "hybrid@gmail.com")
    resp = await client.post("/auth/google", json={"id_token": "x" * 20})
    assert resp.status_code == 200
    assert resp.json()["status"] == "authenticated"

    await db_session.refresh(user)
    assert user.google_sub == "google-sub-4"  # linked


@pytest.mark.asyncio
async def test_google_completion_rejects_staff_role(client: AsyncClient, test_tenant, monkeypatch):
    _fake_google(monkeypatch, "google-sub-5", "sneaky@gmail.com")
    start = await client.post("/auth/google", json={"id_token": "x" * 20})
    reg_token = start.json()["registration_token"]

    resp = await client.post("/auth/google/complete", json={
        "registration_token": reg_token,
        "role": "counselor",  # not allowed
        "phone": "+1 555 000 0000",
        "school_code": test_tenant.school_code,
    })
    assert resp.status_code == 422
