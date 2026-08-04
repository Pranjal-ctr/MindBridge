/**
 * Counselor response SLA + emergency escalation flow.
 *
 * Single source of truth for the target response window per risk level and the
 * escalation steps for acute cases. Surfaced in the counselor review queue and
 * mirrored in docs/safety-sla-and-escalation.md for internal reference.
 *
 * Levels match the backend's four bands (no "orange").
 */

export interface RiskSla {
  label: string;
  /** Target response window for this level. */
  window: string;
  /** What the counselor is expected to do. */
  action: string;
  /** True for levels that trigger the emergency escalation flow. */
  emergency: boolean;
}

export const RISK_SLA: Record<string, RiskSla> = {
  critical: {
    label: 'Critical',
    window: 'Immediately',
    action: "Follow your school's emergency escalation policy now.",
    emergency: true,
  },
  red: {
    label: 'Red',
    window: 'Same working day',
    action: 'Review and reach out to the student today.',
    emergency: false,
  },
  yellow: {
    label: 'Yellow',
    window: 'Within 48 hours',
    action: 'Review and monitor; check in if the pattern persists.',
    emergency: false,
  },
  green: {
    label: 'Green',
    window: 'Routine',
    action: 'No action required beyond routine monitoring.',
    emergency: false,
  },
};

/** Ordered emergency escalation steps for acute (critical) assessments. */
export const ESCALATION_STEPS = [
  'Acknowledge the alert immediately and open the assessment (review the contributors and confidence).',
  "Contact the student per your school's safeguarding policy; involve on-site staff if needed.",
  'If there is imminent risk to safety, contact local emergency services or a crisis helpline right away.',
  'Notify the student’s guardian per school settings (Kio sends a content-free alert automatically).',
  'Record your verdict and outcome so the assessment is closed and logged.',
];

export function slaFor(level: string): RiskSla {
  return RISK_SLA[level] ?? RISK_SLA.yellow;
}
