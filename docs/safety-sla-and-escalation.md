# Safety: Response SLA & Emergency Escalation

Internal reference for how Kio surfaces risk to counselors, the expected
response times, and the emergency escalation flow. The product wording lives in
`src/lib/risk-sla.ts` (SLA + steps) and `src/app/components/Disclaimer.tsx`
(non-diagnostic disclaimer) — keep this doc in sync with those.

## Positioning (non-diagnostic)

> Kio is an AI wellbeing support platform. It assists students, parents,
> counselors, and schools by identifying wellbeing patterns and potential areas
> of concern. It does not provide medical or psychological diagnoses and should
> not replace qualified professional care.

Kio's risk output is **assistive decision support**, reviewed by a human. It is
never an autonomous clinical judgment.

## Risk levels & response SLA

Four bands (no "orange"), matching the backend `risk_level_bands`.

| Level | Meaning | Target response |
|-------|---------|-----------------|
| **Green** | Typical ups and downs | Routine monitoring |
| **Yellow** | Elevated stress worth watching | Within **48 hours** |
| **Red** | Persistent distress needing attention | **Same working day** |
| **Critical** | Acute risk (self-harm, suicidal ideation, abuse, severe hopelessness) | **Immediately** — emergency escalation |

## Emergency escalation flow (Critical)

1. **Acknowledge immediately** and open the assessment — review the contributors
   and confidence.
2. **Contact the student** per your school's safeguarding policy; involve on-site
   staff if needed.
3. **Imminent risk to safety → contact local emergency services / a crisis
   helpline right away.**
4. **Guardian notification** happens automatically (content-free) per school
   settings; follow up per policy.
5. **Record verdict + outcome** to close and log the assessment.

## How the system supports this

- **Keyword tripwire (synchronous):** explicit self-harm / abuse / violence
  phrasing (English + Hinglish) raises a provisional alert *before* the LLM runs,
  so alerting never depends on the model being up. Hyperbole-prone ("soft")
  phrases are logged but do not alert.
- **Server-side safety floor:** a credible self-harm / suicidal / abuse signal
  from the model forces overall risk to at least the configured floor, so an
  under-scored aggregate can't mask acute risk. Protective factors never lower it.
- **Content-free notifications:** counselors and school admins are alerted on
  every crossing; linked guardians receive a content-free "risk level changed"
  message (gated by school settings). Raw conversation content is never shared.
- **Confidence & inconclusive state:** low-confidence assessments are flagged
  "inconclusive" (not enough signal) rather than reading as low risk.
- **Verdict capture:** counselors record their own level + outcome, building a
  labeled AI-vs-human dataset for calibration and evaluation.

## Configurable thresholds

All safety thresholds are DB-driven (`platform_config`, code fallback in
`app/intelligence/config.py`) and tunable from Admin/Playground with no deploy:
`safety_floors` (`self_harm`, `suicidal_ideation`, `abuse`, `enforced_overall`,
`min_confidence`), `risk_level_bands`, and `crisis`.
