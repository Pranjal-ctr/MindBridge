"""
Intelligence layer foundations: JSON parsing, analysis schema validation,
platform config loading, risk-level derivation, and admin config endpoints.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.config import DEFAULTS, derive_risk_level, load_config
from app.intelligence.parsing import parse_json_response
from app.intelligence.schemas import MessageAnalysis
from database.models import PlatformConfig


VALID_ANALYSIS = {
    "risk": {
        "overall": 81,
        "confidence": 0.94,
        "categories": {"self_harm": 95, "family_conflict": 78, "academic_pressure": 62},
        "summary": "Persistent hopelessness linked to family pressure.",
    },
    "emotion": {"current": "Hopeless", "intensity": 85, "confidence": 0.9, "secondary": ["Sad"]},
    "sentiment": "negative",
    "stress": {"Academic": 62, "Family": 78, "Friends": 10},
}


# -------------------------------------------------------------------
# parse_json_response
# -------------------------------------------------------------------

def test_parse_plain_json():
    assert parse_json_response('{"a": 1}') == {"a": 1}


def test_parse_fenced_json():
    fenced = '```json\n{"a": 1}\n```'
    assert parse_json_response(fenced) == {"a": 1}


def test_parse_garbage_raises():
    with pytest.raises(ValueError):
        parse_json_response("I'm sorry, I can't produce JSON right now.")


def test_parse_non_object_raises():
    with pytest.raises(ValueError):
        parse_json_response("[1, 2, 3]")


def test_parse_none_raises():
    with pytest.raises(ValueError):
        parse_json_response(None)


# -------------------------------------------------------------------
# MessageAnalysis validation
# -------------------------------------------------------------------

def test_valid_analysis_parses():
    analysis = MessageAnalysis.model_validate(VALID_ANALYSIS)
    assert analysis.risk.overall == 81
    assert analysis.emotion.current == "Hopeless"
    assert analysis.stress["Family"] == 78


def test_unknown_risk_categories_dropped():
    data = {**VALID_ANALYSIS, "risk": {**VALID_ANALYSIS["risk"], "categories": {
        "self_harm": 95, "made_up_category": 50,
    }}}
    analysis = MessageAnalysis.model_validate(data)
    assert "made_up_category" not in analysis.risk.categories
    assert analysis.risk.categories["self_harm"] == 95


def test_emotion_case_insensitive():
    data = {**VALID_ANALYSIS, "emotion": {"current": "anxious", "intensity": 50, "confidence": 0.8}}
    analysis = MessageAnalysis.model_validate(data)
    assert analysis.emotion.current == "Anxious"


def test_unknown_emotion_rejected():
    data = {**VALID_ANALYSIS, "emotion": {"current": "Bamboozled", "intensity": 50, "confidence": 0.8}}
    with pytest.raises(Exception):
        MessageAnalysis.model_validate(data)


def test_unknown_sentiment_defaults_to_neutral():
    data = {**VALID_ANALYSIS, "sentiment": "ecstatic"}
    assert MessageAnalysis.model_validate(data).sentiment == "neutral"


def test_stress_values_clamped_and_filtered():
    data = {**VALID_ANALYSIS, "stress": {"Academic": 250, "Nonsense": 40, "family": 30}}
    analysis = MessageAnalysis.model_validate(data)
    assert analysis.stress["Academic"] == 100
    assert analysis.stress["Family"] == 30  # case-normalized
    assert "Nonsense" not in analysis.stress


# -------------------------------------------------------------------
# Platform config
# -------------------------------------------------------------------

def test_derive_risk_level_bands():
    bands = DEFAULTS["risk_level_bands"]
    assert derive_risk_level(10, bands) == "green"
    assert derive_risk_level(40, bands) == "yellow"
    assert derive_risk_level(65, bands) == "red"
    assert derive_risk_level(85, bands) == "critical"


@pytest.mark.asyncio
async def test_load_config_falls_back_to_defaults(db_session: AsyncSession):
    config = await load_config(db_session, "crisis")
    assert config == DEFAULTS["crisis"]


@pytest.mark.asyncio
async def test_load_config_merges_db_over_defaults(db_session: AsyncSession):
    db_session.add(PlatformConfig(config_key="crisis", config_value={"trigger_score": 50}))
    await db_session.flush()

    config = await load_config(db_session, "crisis")
    assert config["trigger_score"] == 50           # DB wins
    assert config["deescalate_after"] == 3         # default sub-key preserved


@pytest.mark.asyncio
async def test_load_config_unknown_key_raises(db_session: AsyncSession):
    with pytest.raises(KeyError):
        await load_config(db_session, "not_a_real_key")


# -------------------------------------------------------------------
# Admin config endpoints
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_lists_all_config(client: AsyncClient, admin_auth_headers):
    resp = await client.get("/admin/config", headers=admin_auth_headers)
    assert resp.status_code == 200
    keys = {c["config_key"] for c in resp.json()["configs"]}
    assert keys == set(DEFAULTS)


@pytest.mark.asyncio
async def test_admin_updates_config(client: AsyncClient, admin_auth_headers):
    resp = await client.put(
        "/admin/config/risk_level_bands",
        headers=admin_auth_headers,
        json={"config_value": {"yellow": 35, "red": 60, "critical": 80}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["config_value"]["red"] == 60
    assert body["source"] == "database"


@pytest.mark.asyncio
async def test_admin_rejects_unknown_config_key(client: AsyncClient, admin_auth_headers):
    resp = await client.put(
        "/admin/config/nope",
        headers=admin_auth_headers,
        json={"config_value": {"x": 1}},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_rejects_bad_wellness_weights(client: AsyncClient, admin_auth_headers):
    resp = await client.put(
        "/admin/config/wellness_weights",
        headers=admin_auth_headers,
        json={"config_value": {"mood_level": 0.5}},  # sums to 0.5
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_student_cannot_read_config(client: AsyncClient, student_auth_headers):
    resp = await client.get("/admin/config", headers=student_auth_headers)
    assert resp.status_code == 403
