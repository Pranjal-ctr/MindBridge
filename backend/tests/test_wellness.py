"""
Kio Wellness Tests
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_log_wellness(client: AsyncClient, student_auth_headers):
    """Test logging a wellness check-in."""
    response = await client.post(
        "/wellness/records",
        json={
            "mood_score": 7,
            "stress_score": 4,
            "confidence_score": 6,
            "anxiety_score": 3,
            "energy_score": 8,
        },
        headers=student_auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["mood_score"] == 7
    assert data["energy_score"] == 8


@pytest.mark.asyncio
async def test_create_goal(client: AsyncClient, student_auth_headers):
    """Test creating a wellness goal."""
    response = await client.post(
        "/wellness/goals",
        json={
            "goal_title": "Meditate daily",
            "goal_description": "Practice 10 minutes of mindfulness each morning",
        },
        headers=student_auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["goal_title"] == "Meditate daily"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_create_journal_entry(client: AsyncClient, student_auth_headers):
    """Test creating a journal entry."""
    response = await client.post(
        "/wellness/journal",
        json={
            "title": "Good day today",
            "content": "I felt productive and connected with friends.",
            "mood_score": 8,
        },
        headers=student_auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Good day today"
    assert data["mood_score"] == 8
