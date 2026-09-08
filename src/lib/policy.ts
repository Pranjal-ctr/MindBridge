/**
 * Policy versions and age thresholds, mirrored from backend/app/consent/policy.py.
 *
 * These MUST stay in step with the Python constants. They are duplicated rather
 * than fetched because the signup form needs them before any request is made,
 * and a mismatch would let the UI record consent against a version the server
 * does not recognise. `GET /consent/policies` returns the authoritative values
 * if you ever need to assert they agree.
 */

export const TERMS_VERSION = '2026-09-08';
export const PRIVACY_VERSION = '2026-09-08';

/** No account below this age, consent or not. */
export const MINIMUM_AGE = 13;

/** At or above this, a user consents for themselves. Below it, a guardian must. */
export const AGE_OF_SELF_CONSENT = 18;

/** Completed years between `dob` and today. Mirrors calculate_age() in Python. */
export function calculateAge(dob: string | Date, today: Date = new Date()): number {
  const birth = typeof dob === 'string' ? new Date(`${dob}T00:00:00`) : dob;
  if (Number.isNaN(birth.getTime())) return NaN;

  const hadBirthday =
    today.getMonth() > birth.getMonth() ||
    (today.getMonth() === birth.getMonth() && today.getDate() >= birth.getDate());

  return today.getFullYear() - birth.getFullYear() - (hadBirthday ? 0 : 1);
}

export type AgeCheck =
  | { status: 'ok'; age: number }
  | { status: 'minor'; age: number }
  | { status: 'too-young'; age: number }
  | { status: 'invalid' };

/**
 * Client-side mirror of the server's age gate.
 *
 * Advisory only — it exists so someone does not fill in a whole form to be
 * rejected on submit. `enforce_age_gate` on the server is the real gate, and
 * this never replaces it.
 */
export function checkAge(dob: string, today: Date = new Date()): AgeCheck {
  if (!dob) return { status: 'invalid' };

  const birth = new Date(`${dob}T00:00:00`);
  if (Number.isNaN(birth.getTime()) || birth > today) return { status: 'invalid' };

  const age = calculateAge(birth, today);
  if (age > 120) return { status: 'invalid' };
  if (age < MINIMUM_AGE) return { status: 'too-young', age };
  if (age < AGE_OF_SELF_CONSENT) return { status: 'minor', age };
  return { status: 'ok', age };
}
