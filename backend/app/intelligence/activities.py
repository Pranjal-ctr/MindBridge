"""
Personalized student activities (feature `activities`) -- persisted per student.

The recommendation engine works in two layers:

1. WEEKLY SET (6 activities): generated once per ISO week from real signals
   (latest check-in mood + reason, top stress factors, recent conversation-
   derived stress topics, age, risk level). LLM-personalized when a provider
   is available, otherwise a deterministic signal-aware selection from the
   built-in catalog. Persisted in student_activities.
2. DAILY PICK (1 activity): a fresh catalog activity added each day,
   deterministic (no extra LLM cost), excluding anything suggested recently.

De-duplication: activities suggested in the last RECENT_DAYS days are excluded
from new selections, so suggestions do not repeat. Completions are stored on
the row (completed_at), so state survives logout; an activity cannot be
completed twice.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import router as ai_router
from app.intelligence.parsing import parse_json_response
from app.wellness.schemas import ActivitiesResponse, ActivityItem
from database.models import (
    EmotionSnapshot,
    StressDistribution,
    StudentActivity,
    StudentProfile,
    StudentTimeline,
    WellnessRecord,
)

logger = logging.getLogger(__name__)

WEEKLY_SET_SIZE = 6
RECENT_DAYS = 21  # no repeats within this window

# Each catalog entry lists the signals it best serves.
# moods: amazing/good/okay/low/very_difficult; stress tags are lowercase topics.
ACTIVITY_CATALOG: list[dict] = [
    {"activity_id": "gratitude-journal", "title": "Gratitude journal",
     "description": "Write down three things that went well today, however small.",
     "category": "reflection", "duration_minutes": 5,
     "moods": ["okay", "low"], "stress": ["family", "friends", "self-confidence"]},
    {"activity_id": "breathing-478", "title": "4-7-8 breathing",
     "description": "Breathe in for 4, hold for 7, out for 8. Repeat five times.",
     "category": "mindfulness", "duration_minutes": 3,
     "moods": ["low", "very_difficult"], "stress": ["academic", "future", "health"]},
    {"activity_id": "short-walk", "title": "10-minute walk",
     "description": "Step outside and walk for ten minutes without your phone.",
     "category": "physical", "duration_minutes": 10,
     "moods": ["okay", "low", "very_difficult"], "stress": ["academic", "family"]},
    {"activity_id": "draw-feelings", "title": "Draw how you're feeling",
     "description": "Grab paper and sketch your mood -- shapes and colors, no rules.",
     "category": "creative", "duration_minutes": 10,
     "moods": ["low", "very_difficult"], "stress": ["identity", "self-confidence"]},
    {"activity_id": "positive-reflection", "title": "Positive reflection",
     "description": "Think of one recent moment you're proud of and write two sentences about it.",
     "category": "reflection", "duration_minutes": 5,
     "moods": ["okay", "low"], "stress": ["self-confidence", "academic"]},
    {"activity_id": "confidence-challenge", "title": "Confidence challenge",
     "description": "Do one small thing outside your comfort zone today and note how it felt.",
     "category": "social", "duration_minutes": 15,
     "moods": ["good", "okay"], "stress": ["self-confidence", "friends"]},
    {"activity_id": "mindful-minute", "title": "Mindful minute",
     "description": "Sit comfortably and notice five things you can see, four you can hear, three you can feel.",
     "category": "mindfulness", "duration_minutes": 2,
     "moods": ["okay", "low", "very_difficult"], "stress": ["academic", "future"]},
    {"activity_id": "digital-detox", "title": "One-hour digital detox",
     "description": "Put your phone in another room for an hour and do anything offline.",
     "category": "rest", "duration_minutes": 60,
     "moods": ["okay", "low"], "stress": ["friends", "relationships", "identity"]},
    {"activity_id": "sleep-routine", "title": "Wind-down routine",
     "description": "Tonight, screens off 30 minutes before bed -- stretch, read, or listen to calm music.",
     "category": "rest", "duration_minutes": 30,
     "moods": ["low", "very_difficult"], "stress": ["health", "academic"]},
    {"activity_id": "stretch-break", "title": "Stretch break",
     "description": "Stand up and stretch your neck, shoulders, and back for five minutes.",
     "category": "physical", "duration_minutes": 5,
     "moods": ["good", "okay"], "stress": ["academic", "health"]},
    {"activity_id": "reach-out", "title": "Message a friend",
     "description": "Send a hello to someone you haven't spoken with in a while.",
     "category": "social", "duration_minutes": 5,
     "moods": ["okay", "low"], "stress": ["friends", "relationships"]},
    {"activity_id": "celebrate-win", "title": "Celebrate a win",
     "description": "You're doing well -- treat yourself to something you enjoy and savor it.",
     "category": "rest", "duration_minutes": 15,
     "moods": ["amazing", "good"], "stress": []},
    {"activity_id": "study-sprint", "title": "25-minute study sprint",
     "description": "One focused Pomodoro on the subject worrying you most, then a real break.",
     "category": "reflection", "duration_minutes": 25,
     "moods": ["good", "okay"], "stress": ["academic", "future"]},
    {"activity_id": "exam-plan", "title": "Break the exam into steps",
     "description": "List the topics for your next exam and tick the two you already know well.",
     "category": "reflection", "duration_minutes": 15,
     "moods": ["okay", "low"], "stress": ["academic", "future"]},
    {"activity_id": "music-reset", "title": "Three-song reset",
     "description": "Play three songs you love and do nothing else while they play.",
     "category": "creative", "duration_minutes": 12,
     "moods": ["low", "very_difficult"], "stress": ["identity", "family"]},
    {"activity_id": "read-for-fun", "title": "Read something fun",
     "description": "Fifteen minutes with a book, comic, or article that has nothing to do with school.",
     "category": "rest", "duration_minutes": 15,
     "moods": ["okay", "good"], "stress": ["academic"]},
    {"activity_id": "family-checkin", "title": "Tell family one good thing",
     "description": "Share one good moment from your day with someone at home.",
     "category": "social", "duration_minutes": 5,
     "moods": ["okay", "low"], "stress": ["family", "friends"]},
    {"activity_id": "future-letter", "title": "Letter to future you",
     "description": "Write three sentences to yourself one year from now.",
     "category": "reflection", "duration_minutes": 10,
     "moods": ["okay", "low"], "stress": ["future", "career", "identity"]},
    {"activity_id": "career-curiosity", "title": "Explore one career path",
     "description": "Spend ten minutes reading about one job that sounds interesting -- no pressure.",
     "category": "reflection", "duration_minutes": 10,
     "moods": ["good", "okay"], "stress": ["career", "future"]},
    {"activity_id": "body-exercise", "title": "Quick workout",
     "description": "Ten jumping jacks, ten squats, ten seconds of stretching. Repeat twice.",
     "category": "physical", "duration_minutes": 8,
     "moods": ["good", "okay", "low"], "stress": ["academic", "health"]},
    {"activity_id": "sport-session", "title": "Play your sport",
     "description": "Make time for the sport or game you enjoy, even a short session counts.",
     "category": "physical", "duration_minutes": 30,
     "moods": ["amazing", "good", "okay"], "stress": ["academic", "self-confidence"]},
    {"activity_id": "tidy-space", "title": "Two-minute tidy",
     "description": "Clear just your desk or bedside table -- a small space, a clearer head.",
     "category": "rest", "duration_minutes": 2,
     "moods": ["okay", "low"], "stress": ["academic", "identity"]},
    {"activity_id": "code-something", "title": "Build something tiny",
     "description": "Code, craft, or build any small thing for fifteen minutes -- making things feels good.",
     "category": "creative", "duration_minutes": 15,
     "moods": ["good", "okay"], "stress": ["future", "career"]},
    {"activity_id": "help-someone", "title": "Help someone today",
     "description": "Do one small favor for a friend or family member and notice how it feels.",
     "category": "social", "duration_minutes": 10,
     "moods": ["good", "okay"], "stress": ["friends", "self-confidence"]},
    {"activity_id": "nature-minutes", "title": "Five minutes outside",
     "description": "Stand or sit outside for five minutes and just notice the sky.",
     "category": "mindfulness", "duration_minutes": 5,
     "moods": ["low", "very_difficult"], "stress": ["health", "family"]},
    {"activity_id": "worry-parking", "title": "Park your worries",
     "description": "Write every worry on paper, fold it, and set it aside until tomorrow.",
     "category": "mindfulness", "duration_minutes": 8,
     "moods": ["low", "very_difficult"], "stress": ["future", "academic", "family"]},
]

_CATALOG_BY_ID = {item["activity_id"]: item for item in ACTIVITY_CATALOG}

ACTIVITIES_SYSTEM_PROMPT = """You suggest short wellbeing activities for a student on the Kio \
platform. You receive aggregated signals only (today's mood and reason, top stress areas, \
recent emotion, age, risk level, and recently suggested activities) -- never conversation content.

Output ONLY a JSON object -- no prose, no markdown:

{"activities": [{"activity_id": "<kebab-case-slug>", "title": "<max 6 words>",
"description": "<one friendly, concrete sentence, imperative voice>",
"category": "<mindfulness|physical|social|reflection|rest|creative>",
"duration_minutes": <2-60>, "reason": "<one sentence: why this fits the student today, \
referencing their signals without alarm>"}]}

Rules:
- Exactly 6 activities, at least 4 distinct categories.
- Concrete and immediately doable today (e.g. "draw how you're feeling", "walk 10 minutes").
- Match the mood: gentle/low-effort when mood is low or risk is elevated; energising when good.
- Do NOT repeat anything in the RECENTLY SUGGESTED list (by idea, not just wording).
- Never mention risk scores, diagnoses, or anything clinical.
"""

ACTIVITIES_RESPONSE_SCHEMA: dict = {
    "type": "OBJECT",
    "properties": {
        "activities": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "activity_id": {"type": "STRING"},
                    "title": {"type": "STRING"},
                    "description": {"type": "STRING"},
                    "category": {"type": "STRING"},
                    "duration_minutes": {"type": "INTEGER"},
                    "reason": {"type": "STRING"},
                },
                "required": ["activity_id", "title", "description", "category",
                             "duration_minutes", "reason"],
            },
        },
    },
    "required": ["activities"],
}

VALID_CATEGORIES = {"mindfulness", "physical", "social", "reflection", "rest", "creative"}


def _week_start(today: date | None = None) -> date:
    today = today or date.today()
    return today - timedelta(days=today.weekday())


async def _gather_signals(db: AsyncSession, student_id: uuid.UUID) -> dict:
    today_record = (await db.execute(
        select(WellnessRecord).where(
            WellnessRecord.student_id == student_id,
            WellnessRecord.date_recorded == date.today(),
        ).order_by(WellnessRecord.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    stress = (await db.execute(
        select(StressDistribution)
        .where(StressDistribution.student_id == student_id)
        .order_by(StressDistribution.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    top_stress = []
    if stress is not None and stress.categories:
        top_stress = [
            name for name, value in sorted(
                stress.categories.items(), key=lambda kv: kv[1], reverse=True
            )[:3] if value > 0
        ]

    emotion = (await db.execute(
        select(EmotionSnapshot)
        .where(EmotionSnapshot.student_id == student_id)
        .order_by(EmotionSnapshot.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    profile = (await db.execute(
        select(StudentProfile).where(StudentProfile.student_id == student_id)
    )).scalar_one_or_none()

    return {
        "mood": today_record.mood_label if today_record else None,
        "mood_score": today_record.mood_score if today_record else None,
        "reason": today_record.mood_reason if today_record else None,
        "top_stress": top_stress,
        "emotion": emotion.current_emotion if emotion else None,
        "age": profile.age if profile else None,
        "risk_level": (profile.risk_level or "green") if profile else "green",
    }


async def _recent_activity_rows(
    db: AsyncSession, student_id: uuid.UUID, days: int = RECENT_DAYS
) -> list[StudentActivity]:
    cutoff = date.today() - timedelta(days=days)
    return list((await db.execute(
        select(StudentActivity).where(
            StudentActivity.student_id == student_id,
            StudentActivity.suggested_on >= cutoff,
        ).order_by(StudentActivity.created_at.asc())
    )).scalars().all())


def _rank_catalog(signals: dict, excluded_ids: set[str]) -> list[dict]:
    """Catalog items ranked by fit to the current signals, excluding recent ones."""
    mood = signals.get("mood") or (
        "low" if (signals.get("mood_score") or 5) <= 3
        else "okay" if (signals.get("mood_score") or 5) <= 6 else "good"
    )
    stress_tags = {s.lower() for s in signals.get("top_stress", [])}
    reason = (signals.get("reason") or "").lower()

    def _score(item: dict) -> int:
        score = 0
        if mood in item["moods"]:
            score += 2
        if stress_tags & set(item["stress"]):
            score += 2
        if reason and any(reason.startswith(tag[:4]) for tag in item["stress"]):
            score += 1
        if signals.get("risk_level") in ("red", "critical") and item["category"] in (
            "mindfulness", "rest", "reflection"
        ):
            score += 1
        return score

    candidates = [i for i in ACTIVITY_CATALOG if i["activity_id"] not in excluded_ids]
    return sorted(candidates, key=_score, reverse=True)


def _pick_diverse(ranked: list[dict], count: int) -> list[dict]:
    picked: list[dict] = []
    per_category: dict[str, int] = {}
    for item in ranked:
        if len(picked) == count:
            break
        if per_category.get(item["category"], 0) >= 2:
            continue
        picked.append(item)
        per_category[item["category"]] = per_category.get(item["category"], 0) + 1
    # top up if category caps left us short
    for item in ranked:
        if len(picked) == count:
            break
        if item not in picked:
            picked.append(item)
    return picked


def _fallback_reason(signals: dict) -> str:
    bits = []
    if signals.get("mood"):
        bits.append(f"today's mood ({signals['mood'].replace('_', ' ')})")
    if signals.get("top_stress"):
        bits.append(f"recent stress around {', '.join(s.lower() for s in signals['top_stress'])}")
    return f"Suggested for {' and '.join(bits)}." if bits else "Suggested for a balanced routine."


async def _generate_weekly_set(
    db: AsyncSession, student_id: uuid.UUID, signals: dict,
    excluded_ids: set[str], recent_titles: list[str],
) -> list[StudentActivity]:
    """Generate + persist this week's activity set (LLM first, catalog fallback)."""
    items: list[dict] = []
    source = "catalog"

    signal_lines = [
        f"Today's check-in mood: {signals['mood'] or 'not completed yet'}"
        + (f" (reason: {signals['reason']})" if signals.get("reason") else ""),
        f"Top stress areas: {', '.join(signals['top_stress']) or 'none detected'}",
        f"Most recent emotion: {signals['emotion'] or 'unknown'}",
        f"Age: {signals['age'] or 'unknown'}",
        f"Risk level: {signals['risk_level']}",
        f"RECENTLY SUGGESTED (do not repeat): {', '.join(recent_titles) or 'none'}",
    ]
    try:
        text, _metadata = await ai_router.run(
            db,
            feature="activities",
            system_prompt=ACTIVITIES_SYSTEM_PROMPT,
            contents=[{"role": "user", "parts": [{"text": "\n".join(signal_lines)}]}],
            temperature=0.8,
            max_output_tokens=1024,
            student_id=student_id,
            response_schema=ACTIVITIES_RESPONSE_SCHEMA,
        )
        raw = parse_json_response(text).get("activities", [])
        for entry in raw[:WEEKLY_SET_SIZE]:
            category = str(entry.get("category", "")).lower()
            slug = str(entry.get("activity_id", "custom"))[:60]
            if category not in VALID_CATEGORIES or slug in excluded_ids:
                continue
            duration = int(entry.get("duration_minutes", 10))
            items.append({
                "activity_id": slug,
                "title": str(entry["title"])[:255],
                "description": str(entry["description"]),
                "category": category,
                "duration_minutes": max(2, min(duration, 60)),
                "reason": str(entry.get("reason", "Suggested for you this week.")),
            })
        if len(items) >= 4:
            source = "llm"
        else:
            items = []
            logger.info("Activities LLM returned too few valid items; using catalog")
    except Exception as e:
        logger.info("Weekly activity generation fell back to catalog: %s", str(e))

    if not items:
        ranked = _rank_catalog(signals, excluded_ids)
        reason = _fallback_reason(signals)
        items = [
            {**{k: item[k] for k in
                ("activity_id", "title", "description", "category", "duration_minutes")},
             "reason": reason}
            for item in _pick_diverse(ranked, WEEKLY_SET_SIZE)
        ]

    rows = [
        StudentActivity(
            student_id=student_id,
            source=source,
            kind="weekly",
            week_start=_week_start(),
            suggested_on=date.today(),
            **item,
        )
        for item in items
    ]
    db.add_all(rows)
    await db.flush()
    return rows


async def _ensure_daily_pick(
    db: AsyncSession, student_id: uuid.UUID, signals: dict, excluded_ids: set[str]
) -> StudentActivity | None:
    """One fresh catalog activity per day (deterministic -- no LLM cost)."""
    ranked = _rank_catalog(signals, excluded_ids)
    if not ranked:
        return None
    item = ranked[0]
    row = StudentActivity(
        student_id=student_id,
        activity_id=item["activity_id"],
        title=item["title"],
        description=item["description"],
        category=item["category"],
        duration_minutes=item["duration_minutes"],
        reason="Today's fresh pick, chosen from your recent signals.",
        source="catalog",
        kind="daily",
        week_start=_week_start(),
        suggested_on=date.today(),
    )
    db.add(row)
    await db.flush()
    return row


def _to_item(row: StudentActivity) -> ActivityItem:
    return ActivityItem(
        activity_id=row.activity_id,
        title=row.title,
        description=row.description,
        category=row.category,
        duration_minutes=row.duration_minutes,
        reason=row.reason or "Suggested for you.",
        completed=row.completed_at is not None,
        is_daily=row.kind == "daily",
    )


async def get_personalized_activities(
    db: AsyncSession, student_id: uuid.UUID
) -> ActivitiesResponse:
    """This week's persisted activity set + today's daily pick.

    Generated on first request of the week/day; served from the database after
    that (no repeated AI calls). Flushes, no commit.
    """
    recent = await _recent_activity_rows(db, student_id)
    signals = await _gather_signals(db, student_id)

    week = [r for r in recent if r.week_start == _week_start()]
    weekly_rows = [r for r in week if r.kind == "weekly"]
    daily_rows = [r for r in week if r.kind == "daily"]

    excluded_ids = {r.activity_id for r in recent}
    recent_titles = [r.title for r in recent][-18:]

    if not weekly_rows:
        weekly_rows = await _generate_weekly_set(
            db, student_id, signals, excluded_ids, recent_titles
        )
        excluded_ids |= {r.activity_id for r in weekly_rows}

    todays_daily = next((r for r in daily_rows if r.suggested_on == date.today()), None)
    if todays_daily is None:
        excluded_ids |= {r.activity_id for r in daily_rows}
        todays_daily = await _ensure_daily_pick(db, student_id, signals, excluded_ids)

    rows: list[StudentActivity] = ([todays_daily] if todays_daily else []) + weekly_rows
    personalized = any(r.source == "llm" for r in weekly_rows)

    return ActivitiesResponse(
        activities=[_to_item(r) for r in rows],
        personalized=personalized,
        generated_at=datetime.now(timezone.utc),
    )


async def complete_activity(
    db: AsyncSession, student_id: uuid.UUID, activity_id: str, title: str
) -> None:
    """Persist a completion (idempotence guarded: an activity completes once)."""
    row = (await db.execute(
        select(StudentActivity).where(
            StudentActivity.student_id == student_id,
            StudentActivity.activity_id == activity_id,
            StudentActivity.week_start == _week_start(),
        ).order_by(StudentActivity.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    if row is not None and row.completed_at is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Activity already completed",
        )

    if row is not None:
        row.completed_at = datetime.now(timezone.utc)

    db.add(StudentTimeline(
        student_id=student_id,
        event_type="activity_completed",
        event_description=f"Completed activity: {title}",
    ))
    await db.flush()
