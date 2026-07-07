"""
Post-message intelligence pipeline (background, own DB session).

Runs after every student chat exchange, invoked from
app/conversations/service.py::run_post_response_hooks. Each step is
individually non-fatal: a failed step logs a warning and later steps still
run. Crisis-relevant data (step 1) is committed immediately so it survives
any later failure. Safety never depends on this pipeline being up -- the
keyword tripwire already ran on the synchronous chat path.

Step order:
1. Combined AI analysis -> risk/emotion/stress/sentiment rows  [Group B]
2. Crisis workflow when risk crosses the threshold             [Group D]
3. Deterministic wellness recalc                               [Group C]
4. Timeline event                                              [Group B]
5. Debounced parent insight refresh                            [Group E]
"""

from __future__ import annotations

import logging
import uuid

from app.intelligence.analysis import AnalysisOutcome, run_message_analysis

logger = logging.getLogger(__name__)


async def run_intelligence_pipeline(
    conversation_id: uuid.UUID,
    student_id: uuid.UUID,
    student_user_id: uuid.UUID,
    student_message_id: uuid.UUID | None,
) -> None:
    from database.models import StudentTimeline
    from database.session import async_session_factory

    async with async_session_factory() as db:
        # --- Step 1: combined analysis (commit immediately; crisis data
        # must survive any later step failing) ---
        outcome: AnalysisOutcome | None = None
        try:
            outcome = await run_message_analysis(
                db,
                conversation_id=conversation_id,
                student_id=student_id,
                student_message_id=student_message_id,
            )
            await db.commit()
        except Exception as e:
            logger.warning("Intelligence analysis failed (non-fatal): %s", str(e))
            await db.rollback()

        # --- Step 2: crisis workflow ---
        if outcome is not None:
            try:
                from app.intelligence.crisis import evaluate_and_trigger_crisis

                await evaluate_and_trigger_crisis(db, student_id, student_user_id, outcome)
                await db.commit()
            except Exception as e:
                logger.warning("Crisis workflow failed (non-fatal): %s", str(e))
                await db.rollback()

        # --- Step 3: wellness recalc (deterministic; runs even if the AI
        # analysis failed, using last-known signals) ---
        try:
            from app.intelligence.wellness import compute_wellness_score

            await compute_wellness_score(db, student_id, trigger_source="message")
            await db.commit()
        except Exception as e:
            logger.warning("Wellness recalc failed (non-fatal): %s", str(e))
            await db.rollback()

        # --- Step 4: timeline event (neutral description only) ---
        try:
            description = "Chat session with Comrade"
            if outcome is not None:
                description = f"Chat session -- mood: {outcome.analysis.emotion.current}"
            db.add(StudentTimeline(
                student_id=student_id,
                event_type="conversation",
                reference_id=conversation_id,
                event_description=description,
            ))
            await db.commit()
        except Exception as e:
            logger.warning("Timeline event failed (non-fatal): %s", str(e))
            await db.rollback()

        # --- Step 5: debounced parent insight refresh ---
        try:
            from app.intelligence.insights import maybe_refresh_parent_insight

            risk_changed = (
                outcome is not None
                and outcome.new_profile_level != outcome.previous_profile_level
            )
            await maybe_refresh_parent_insight(db, student_id, force=risk_changed)
            await db.commit()
        except Exception as e:
            logger.warning("Parent insight refresh failed (non-fatal): %s", str(e))
            await db.rollback()
