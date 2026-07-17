"""
Student-facing personal insights -- deterministic pattern mining, zero LLM calls.

Surfaces observations ("your mood is usually highest on Fridays", "check-ins
mentioning academics tend to be tougher days") only when the underlying history
is large enough to support them; otherwise returns an empty, honest response.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.wellness.schemas import PersonalInsight, PersonalInsightsResponse
from database.models import StressDistribution, WellnessRecord

# Data-sufficiency gates
MIN_CHECKIN_DAYS = 7          # below this: no insights at all
MIN_WEEKDAY_SAMPLES = 2       # per-weekday minimum for the weekday pattern
MIN_REASON_SAMPLES = 3        # per-reason minimum for reason correlations
MIN_TREND_SAMPLES = 5         # per-window minimum for the 14-day trend
MIN_STRESS_ROWS = 5           # distributions needed for the stress pattern

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

REASON_LABELS = {
    "academics": "academics", "family": "family", "friends": "friends",
    "relationship": "relationships", "health": "health", "career": "career",
    "sports": "sports", "financial": "money worries", "social_media": "social media",
    "other": "other things",
}


def _evidence(n: int, days: int) -> str:
    weeks = max(1, round(days / 7))
    return f"Based on {n} check-in(s) over the last {weeks} week(s)"


async def mine_personal_insights(
    db: AsyncSession, student_id: uuid.UUID
) -> PersonalInsightsResponse:
    """Mine mood/stress history for patterns worth telling the student about."""
    today = date.today()
    window_start = today - timedelta(days=90)

    records = (await db.execute(
        select(WellnessRecord)
        .where(
            WellnessRecord.student_id == student_id,
            WellnessRecord.date_recorded >= window_start,
            WellnessRecord.mood_score.isnot(None),
        )
        .order_by(WellnessRecord.date_recorded.asc())
    )).scalars().all()

    # One reading per day (latest wins) so streak days aren't double-counted
    daily: dict[date, WellnessRecord] = {}
    for r in records:
        daily[r.date_recorded] = r
    checkin_days = len(daily)

    if checkin_days < MIN_CHECKIN_DAYS:
        return PersonalInsightsResponse(
            insights=[], sufficient_data=False, checkin_days=checkin_days
        )

    span_days = (today - min(daily)).days + 1 if daily else 0
    insights: list[PersonalInsight] = []

    # --- weekday pattern: best vs worst day of the week ---
    by_weekday: dict[int, list[int]] = defaultdict(list)
    for day, rec in daily.items():
        by_weekday[day.weekday()].append(rec.mood_score)
    weekday_avgs = {
        wd: sum(scores) / len(scores)
        for wd, scores in by_weekday.items()
        if len(scores) >= MIN_WEEKDAY_SAMPLES
    }
    if len(weekday_avgs) >= 3:
        best = max(weekday_avgs, key=weekday_avgs.get)
        worst = min(weekday_avgs, key=weekday_avgs.get)
        if weekday_avgs[best] - weekday_avgs[worst] >= 1.5:
            insights.append(PersonalInsight(
                kind="weekday_pattern",
                title=f"{WEEKDAYS[best]}s tend to be your best days",
                body=(
                    f"Your mood averages {weekday_avgs[best]:.1f}/10 on {WEEKDAYS[best]}s "
                    f"but {weekday_avgs[worst]:.1f}/10 on {WEEKDAYS[worst]}s. "
                    f"It might help to plan something you enjoy on {WEEKDAYS[worst]}s."
                ),
                evidence=_evidence(checkin_days, span_days),
            ))

    # --- reason correlations: which check-in reasons come with high/low moods ---
    by_reason: dict[str, list[int]] = defaultdict(list)
    for rec in daily.values():
        if rec.mood_reason:
            by_reason[rec.mood_reason].append(rec.mood_score)
    reason_avgs = {
        reason: sum(scores) / len(scores)
        for reason, scores in by_reason.items()
        if len(scores) >= MIN_REASON_SAMPLES
    }
    if reason_avgs:
        top_reason = max(reason_avgs, key=reason_avgs.get)
        low_reason = min(reason_avgs, key=reason_avgs.get)
        if reason_avgs[top_reason] >= 7:
            insights.append(PersonalInsight(
                kind="reason_pattern",
                title=f"Days involving {REASON_LABELS.get(top_reason, top_reason)} lift your mood",
                body=(
                    f"When your check-in mentions {REASON_LABELS.get(top_reason, top_reason)}, "
                    f"your mood averages {reason_avgs[top_reason]:.1f}/10 -- "
                    "clearly one of your strengths. Keep making room for it."
                ),
                evidence=_evidence(len(by_reason[top_reason]), span_days),
            ))
        if low_reason != top_reason and reason_avgs[low_reason] <= 4.5:
            insights.append(PersonalInsight(
                kind="reason_pattern",
                title=f"{REASON_LABELS.get(low_reason, low_reason).capitalize()} has been weighing on you",
                body=(
                    f"Check-ins that mention {REASON_LABELS.get(low_reason, low_reason)} average "
                    f"{reason_avgs[low_reason]:.1f}/10. Talking it through with Comrade or "
                    "someone you trust could make those days lighter."
                ),
                evidence=_evidence(len(by_reason[low_reason]), span_days),
            ))

    # --- 14-day mood trend vs the previous 14 days ---
    recent = [r.mood_score for d, r in daily.items() if d >= today - timedelta(days=14)]
    prior = [
        r.mood_score for d, r in daily.items()
        if today - timedelta(days=28) <= d < today - timedelta(days=14)
    ]
    if len(recent) >= MIN_TREND_SAMPLES and len(prior) >= MIN_TREND_SAMPLES:
        delta = sum(recent) / len(recent) - sum(prior) / len(prior)
        if delta >= 1:
            insights.append(PersonalInsight(
                kind="mood_trend",
                title="Your mood has been climbing",
                body=(
                    f"Your average mood over the last two weeks is up {delta:.1f} points "
                    "compared with the two weeks before. Whatever you changed is working."
                ),
                evidence=_evidence(len(recent) + len(prior), 28),
            ))
        elif delta <= -1:
            insights.append(PersonalInsight(
                kind="mood_trend",
                title="The last two weeks look tougher",
                body=(
                    f"Your average mood dipped {abs(delta):.1f} points versus the previous "
                    "two weeks. Be kind to yourself -- a small routine or a chat with "
                    "Comrade can help steady things."
                ),
                evidence=_evidence(len(recent) + len(prior), 28),
            ))

    # --- persistent top stress source (from AI stress distributions) ---
    month_ago = datetime.now(timezone.utc) - timedelta(days=30)
    distributions = (await db.execute(
        select(StressDistribution)
        .where(
            StressDistribution.student_id == student_id,
            StressDistribution.created_at >= month_ago,
        )
        .order_by(StressDistribution.created_at.desc())
        .limit(20)
    )).scalars().all()
    if len(distributions) >= MIN_STRESS_ROWS:
        top_factors = Counter()
        for dist in distributions:
            categories = dist.categories or {}
            if categories:
                top = max(categories, key=categories.get)
                if categories[top] > 0:
                    top_factors[top] += 1
        if top_factors:
            factor, count = top_factors.most_common(1)[0]
            if count / len(distributions) >= 0.6:
                insights.append(PersonalInsight(
                    kind="stress_pattern",
                    title=f"{factor} keeps showing up as your main pressure",
                    body=(
                        f"{factor} has been the biggest stress topic in most of your recent "
                        "conversations. Breaking it into smaller steps -- or bringing it to "
                        "a counselor -- usually shrinks it."
                    ),
                    evidence=f"Top stress area in {count} of your last {len(distributions)} analyses",
                ))

    # --- consistency celebration ---
    streak_days = sorted(daily.keys(), reverse=True)
    streak = 0
    expected = today
    for d in streak_days:
        if d in (expected, expected - timedelta(days=1)) and streak == 0:
            streak = 1
            expected = d - timedelta(days=1)
        elif d == expected:
            streak += 1
            expected = d - timedelta(days=1)
        else:
            break
    if streak >= 5:
        insights.append(PersonalInsight(
            kind="consistency",
            title=f"{streak} days of showing up for yourself",
            body=(
                f"You've checked in {streak} days in a row. That kind of consistency is "
                "exactly how self-awareness grows."
            ),
            evidence=f"Current check-in streak: {streak} day(s)",
        ))

    return PersonalInsightsResponse(
        insights=insights[:4],
        sufficient_data=True,
        checkin_days=checkin_days,
    )
