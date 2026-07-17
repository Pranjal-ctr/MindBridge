"""
Weekly AI reports (feature `weekly_report`) -- one role-appropriate summary per
student/audience/ISO week, generated lazily on first request and cached in
weekly_reports.

Student version speaks to the student; parent version is privacy-safe
(aggregates only, no conversation content); counselor version is professional
and may reference risk levels. A deterministic fallback built from the stored
wellness score and weekly counters guarantees a report even with no AI
provider configured.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import router as ai_router
from app.intelligence.insights import _build_signal_summary
from app.intelligence.parsing import parse_json_response
from database.models import (
    Conversation,
    Message,
    WeeklyReport,
    WellnessRecord,
    WellnessScore,
)

logger = logging.getLogger(__name__)

AUDIENCES = ("student", "parent", "counselor")

_AUDIENCE_INSTRUCTIONS = {
    "student": (
        "Write TO the student in warm, encouraging second person ('you'). "
        "Celebrate effort, normalize hard days, suggest one gentle focus for next week. "
        "Never mention risk scores or that they are being monitored."
    ),
    "parent": (
        "Write FOR a parent about their child in supportive third person. "
        "Aggregated patterns only -- NEVER quote or invent things the student said. "
        "No clinical language, no alarmism; end with one concrete way to support them."
    ),
    "counselor": (
        "Write FOR a school counselor. Professional, objective, information-dense. "
        "You may reference risk levels and component scores. Note trajectory, key "
        "signals, and a suggested follow-up priority. Still no invented quotes."
    ),
}

WEEKLY_REPORT_SYSTEM_PROMPT = """You write a weekly wellbeing report for the Kio platform \
from aggregated signals only (wellness components, risk trajectory, emotion trends, stress \
distribution, engagement counts).

AUDIENCE INSTRUCTIONS:
{audience_instructions}

Output ONLY a JSON object -- no prose, no markdown:

{{"headline": "<one short sentence capturing the week>",
"summary": "<3-5 sentence narrative of the week>",
"highlights": ["<2-4 positive developments or wins>"],
"focus_areas": ["<1-3 things to focus on next week>"]}}
"""

WEEKLY_REPORT_RESPONSE_SCHEMA: dict = {
    "type": "OBJECT",
    "properties": {
        "headline": {"type": "STRING"},
        "summary": {"type": "STRING"},
        "highlights": {"type": "ARRAY", "items": {"type": "STRING"}},
        "focus_areas": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["headline", "summary", "highlights", "focus_areas"],
}


def current_week_start(today: date | None = None) -> date:
    """Monday of the current ISO week."""
    today = today or date.today()
    return today - timedelta(days=today.weekday())


async def _weekly_counters(db: AsyncSession, student_id: uuid.UUID) -> dict:
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    messages = (await db.execute(
        select(func.count()).select_from(Message)
        .join(Conversation, Message.conversation_id == Conversation.conversation_id)
        .where(
            Conversation.student_id == student_id,
            Message.sender_type == "user",
            Message.created_at >= week_ago,
        )
    )).scalar() or 0
    checkin_days = (await db.execute(
        select(func.count(func.distinct(WellnessRecord.date_recorded)))
        .select_from(WellnessRecord)
        .where(WellnessRecord.student_id == student_id, WellnessRecord.created_at >= week_ago)
    )).scalar() or 0
    return {"messages": messages, "checkin_days": checkin_days}


def _fallback_content(
    audience: str,
    score: WellnessScore | None,
    counters: dict,
) -> dict:
    """Deterministic template report from stored data (no LLM)."""
    subject = "You" if audience == "student" else "The student"
    possessive = "your" if audience == "student" else "their"

    if score is not None:
        value = float(score.overall_score)
        trend_text = {
            "improving": "trending upward",
            "declining": "under some pressure",
            "stable": "holding steady",
        }.get(score.trend, "holding steady")
        headline = f"Wellness is {value:.0f}/100 and {trend_text} this week."
        summary = (
            f"{subject} logged {counters['checkin_days']} check-in day(s) and "
            f"{counters['messages']} companion conversation message(s) this week. "
            f"The computed wellness score is {value:.0f}/100 ({score.trend}). "
            f"{score.explanation or ''}"
        ).strip()
    else:
        headline = "Not enough activity for a full report yet."
        summary = (
            f"{subject} logged {counters['checkin_days']} check-in day(s) and "
            f"{counters['messages']} message(s) this week -- a little more activity "
            f"will unlock {possessive} first full weekly report."
        )

    highlights = []
    if counters["checkin_days"] >= 5:
        highlights.append(f"Checked in {counters['checkin_days']} days this week -- great consistency.")
    elif counters["checkin_days"] >= 1:
        highlights.append(f"Completed {counters['checkin_days']} daily check-in(s).")
    if counters["messages"] >= 5:
        highlights.append("Engaged regularly with Comrade this week.")
    if score is not None and score.trend == "improving":
        highlights.append("Overall wellness moved in the right direction.")
    if not highlights:
        highlights.append("A fresh week is a fresh start.")

    focus_areas = []
    if counters["checkin_days"] < 5:
        focus_areas.append("Aim for a daily check-in to build the streak.")
    if score is not None and score.trend == "declining":
        focus_areas.append(
            "Wellness dipped this week -- a short daily activity could help steady it."
        )
    if not focus_areas:
        focus_areas.append("Keep the current routine going.")

    return {
        "headline": headline,
        "summary": summary,
        "highlights": highlights[:4],
        "focus_areas": focus_areas[:3],
    }


async def get_weekly_report(
    db: AsyncSession, student_id: uuid.UUID, audience: str
) -> WeeklyReport:
    """Return this ISO week's cached report, generating it on first request.

    Flushes but does not commit (caller/session middleware commits).
    """
    assert audience in AUDIENCES, f"unknown audience {audience!r}"
    week_start = current_week_start()

    existing = (await db.execute(
        select(WeeklyReport).where(
            WeeklyReport.student_id == student_id,
            WeeklyReport.audience == audience,
            WeeklyReport.week_start == week_start,
        )
    )).scalar_one_or_none()
    if existing is not None:
        return existing

    counters = await _weekly_counters(db, student_id)
    latest_score = (await db.execute(
        select(WellnessScore)
        .where(WellnessScore.student_id == student_id)
        .order_by(WellnessScore.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    content: dict | None = None
    generated_by = "fallback"

    signal_summary = await _build_signal_summary(db, student_id)
    if signal_summary is not None:
        try:
            system_prompt = WEEKLY_REPORT_SYSTEM_PROMPT.format(
                audience_instructions=_AUDIENCE_INSTRUCTIONS[audience]
            )
            text, _metadata = await ai_router.run(
                db,
                feature="weekly_report",
                system_prompt=system_prompt,
                contents=[{"role": "user", "parts": [{"text": signal_summary}]}],
                temperature=0.4,
                max_output_tokens=1024,
                student_id=student_id,
                response_schema=WEEKLY_REPORT_RESPONSE_SCHEMA,
            )
            payload = parse_json_response(text)
            if payload.get("headline") and payload.get("summary"):
                content = {
                    "headline": str(payload["headline"]),
                    "summary": str(payload["summary"]),
                    "highlights": [str(h) for h in payload.get("highlights", [])][:4],
                    "focus_areas": [str(f) for f in payload.get("focus_areas", [])][:3],
                }
                generated_by = "llm"
        except Exception as e:
            logger.info("Weekly report LLM failed; using fallback: %s", str(e))

    if content is None:
        content = _fallback_content(audience, latest_score, counters)

    content["week_start"] = week_start.isoformat()
    content["audience"] = audience

    report = WeeklyReport(
        student_id=student_id,
        audience=audience,
        week_start=week_start,
        content=content,
        generated_by=generated_by,
    )
    db.add(report)
    await db.flush()
    logger.info(
        "Weekly report generated for student %s (%s, %s)",
        student_id, audience, generated_by,
    )
    return report
