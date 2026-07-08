"""
Vocabularies and validated shapes for the combined post-message analysis.

The AI returns one structured JSON document (risk + emotion + sentiment +
stress). ANALYSIS_RESPONSE_SCHEMA constrains the provider's JSON mode;
MessageAnalysis re-validates defensively (clamps ranges, drops unknown
categories, normalizes emotion names) because a fallback provider may not
honor the schema.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

# 15-emotion vocabulary for the Emotional Intelligence Engine
EMOTIONS = [
    "Happy", "Calm", "Excited", "Grateful", "Confident",
    "Neutral", "Tired", "Bored",
    "Anxious", "Stressed", "Sad", "Lonely", "Overwhelmed", "Angry", "Hopeless",
]

# Emotions that count as negative for stability/trend calculations
NEGATIVE_EMOTIONS = {"Anxious", "Stressed", "Sad", "Lonely", "Overwhelmed", "Angry", "Hopeless"}

RISK_CATEGORIES = [
    "hopelessness", "anxiety", "burnout", "loneliness", "bullying",
    "abuse", "family_conflict", "self_harm", "suicidal_ideation",
    "sleep_issues", "eating_issues", "substance_use", "academic_pressure",
]

STRESS_CATEGORIES = [
    "Academic", "Family", "Friends", "Relationships", "Health",
    "Career", "Future", "Identity", "Financial", "Self-Confidence",
]

SENTIMENTS = ["positive", "neutral", "negative", "mixed"]

# Gemini JSON-mode schema (OpenAPI subset; uppercase types per google-genai)
ANALYSIS_RESPONSE_SCHEMA: dict = {
    "type": "OBJECT",
    "properties": {
        "risk": {
            "type": "OBJECT",
            "properties": {
                "overall": {"type": "INTEGER"},
                "confidence": {"type": "NUMBER"},
                "categories": {
                    "type": "OBJECT",
                    "properties": {cat: {"type": "INTEGER"} for cat in RISK_CATEGORIES},
                },
                "summary": {"type": "STRING"},
            },
            "required": ["overall", "confidence", "categories", "summary"],
        },
        "emotion": {
            "type": "OBJECT",
            "properties": {
                "current": {"type": "STRING", "enum": EMOTIONS},
                "intensity": {"type": "INTEGER"},
                "confidence": {"type": "NUMBER"},
                "secondary": {"type": "ARRAY", "items": {"type": "STRING", "enum": EMOTIONS}},
            },
            "required": ["current", "intensity", "confidence"],
        },
        "sentiment": {"type": "STRING", "enum": SENTIMENTS},
        "stress": {
            "type": "OBJECT",
            "properties": {cat: {"type": "INTEGER"} for cat in STRESS_CATEGORIES},
        },
    },
    "required": ["risk", "emotion", "sentiment", "stress"],
}


INSIGHT_TYPES = ["positive", "caution", "info"]

# Gemini JSON-mode schema for the parent insight narrative
PARENT_INSIGHT_RESPONSE_SCHEMA: dict = {
    "type": "OBJECT",
    "properties": {
        "summary": {"type": "STRING"},
        "recommendations": {"type": "ARRAY", "items": {"type": "STRING"}},
        "today_insights": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "type": {"type": "STRING", "enum": INSIGHT_TYPES},
                    "title": {"type": "STRING"},
                    "body": {"type": "STRING"},
                },
                "required": ["type", "title", "body"],
            },
        },
        "improvements": {"type": "ARRAY", "items": {"type": "STRING"}},
        "concerns": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["summary", "recommendations", "today_insights", "improvements", "concerns"],
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


_EMOTION_LOOKUP = {e.lower(): e for e in EMOTIONS}
_STRESS_LOOKUP = {c.lower(): c for c in STRESS_CATEGORIES}


class RiskBlock(BaseModel):
    overall: float = Field(ge=0, le=100)
    confidence: float = Field(default=0.5, ge=0, le=1)
    categories: dict[str, float] = Field(default_factory=dict)
    summary: str = ""

    @field_validator("categories", mode="before")
    @classmethod
    def _known_categories_only(cls, v: object) -> dict:
        if not isinstance(v, dict):
            return {}
        return {
            k: _clamp(float(val), 0, 100)
            for k, val in v.items()
            if k in RISK_CATEGORIES and isinstance(val, (int, float))
        }


class EmotionBlock(BaseModel):
    current: str
    intensity: float = Field(default=50, ge=0, le=100)
    confidence: float = Field(default=0.5, ge=0, le=1)
    secondary: list[str] = Field(default_factory=list)

    @field_validator("current", mode="before")
    @classmethod
    def _normalize_emotion(cls, v: object) -> str:
        emotion = _EMOTION_LOOKUP.get(str(v).strip().lower())
        if emotion is None:
            raise ValueError(f"unknown emotion: {v!r}")
        return emotion

    @field_validator("secondary", mode="before")
    @classmethod
    def _normalize_secondary(cls, v: object) -> list[str]:
        if not isinstance(v, list):
            return []
        return [
            _EMOTION_LOOKUP[str(e).strip().lower()]
            for e in v
            if str(e).strip().lower() in _EMOTION_LOOKUP
        ][:3]


class TodayInsight(BaseModel):
    type: str = "info"
    title: str
    body: str

    @field_validator("type", mode="before")
    @classmethod
    def _known_type(cls, v: object) -> str:
        t = str(v).strip().lower()
        return t if t in INSIGHT_TYPES else "info"


class ParentInsightPayload(BaseModel):
    """Validated parent-insight narrative from the LLM."""
    summary: str
    recommendations: list[str] = Field(default_factory=list)
    today_insights: list[TodayInsight] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


class MessageAnalysis(BaseModel):
    risk: RiskBlock
    emotion: EmotionBlock
    sentiment: str = "neutral"
    stress: dict[str, float] = Field(default_factory=dict)

    @field_validator("sentiment", mode="before")
    @classmethod
    def _known_sentiment(cls, v: object) -> str:
        s = str(v).strip().lower()
        return s if s in SENTIMENTS else "neutral"

    @field_validator("stress", mode="before")
    @classmethod
    def _known_stress_only(cls, v: object) -> dict:
        if not isinstance(v, dict):
            return {}
        return {
            _STRESS_LOOKUP[k.lower()]: _clamp(float(val), 0, 100)
            for k, val in v.items()
            if isinstance(k, str) and k.lower() in _STRESS_LOOKUP
            and isinstance(val, (int, float))
        }
