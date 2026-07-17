"""
Kio Onboarding Tests
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_onboarding_starts_null(client: AsyncClient, student_auth_headers):
    resp = await client.get("/onboarding/", headers=student_auth_headers)
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_onboarding_submit_and_fetch(client: AsyncClient, student_auth_headers):
    payload = {
        "class_level": "Class 10",
        "help_goals": ["Exam Stress", "Study Habits"],
        "hobbies": ["Music", "Coding"],
        "strengths": ["Problem Solving"],
        "interaction_style": "Friendly Friend",
    }
    submit = await client.post("/onboarding/", json=payload, headers=student_auth_headers)
    assert submit.status_code == 201
    body = submit.json()
    assert body["class_level"] == "Class 10"
    assert body["help_goals"] == ["Exam Stress", "Study Habits"]

    fetch = await client.get("/onboarding/", headers=student_auth_headers)
    assert fetch.status_code == 200
    assert fetch.json()["interaction_style"] == "Friendly Friend"


@pytest.mark.asyncio
async def test_onboarding_submit_is_idempotent(client: AsyncClient, student_auth_headers):
    first = {
        "class_level": "Class 9", "help_goals": ["Confidence"], "hobbies": ["Sports"],
        "strengths": ["Sports"], "interaction_style": "Motivational",
    }
    await client.post("/onboarding/", json=first, headers=student_auth_headers)

    second = {**first, "class_level": "College", "interaction_style": "Mentor"}
    resp = await client.post("/onboarding/", json=second, headers=student_auth_headers)
    assert resp.status_code == 201
    assert resp.json()["class_level"] == "College"
    assert resp.json()["interaction_style"] == "Mentor"
