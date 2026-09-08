/**
 * Client-side age gate.
 *
 * This mirrors `calculate_age` / `enforce_age_gate` in
 * backend/app/consent/policy.py. It is advisory — the server is the real gate —
 * but if the two disagree the form either rejects someone the server would
 * accept, or promises an account the server then refuses. The boundary cases
 * below are the ones where a naive implementation drifts.
 */

import { describe, expect, it } from 'vitest';
import { AGE_OF_SELF_CONSENT, MINIMUM_AGE, calculateAge, checkAge } from './policy';

const TODAY = new Date('2026-09-08T12:00:00');

describe('calculateAge', () => {
  it('counts completed years, not rounded ones', () => {
    expect(calculateAge('2013-09-09', TODAY)).toBe(12); // birthday tomorrow
    expect(calculateAge('2013-09-08', TODAY)).toBe(13); // birthday today
    expect(calculateAge('2013-09-07', TODAY)).toBe(13); // birthday yesterday
  });

  it('handles a 29 February birthday', () => {
    expect(calculateAge('2008-02-29', new Date('2026-02-28T12:00:00'))).toBe(17);
    expect(calculateAge('2008-02-29', new Date('2026-03-01T12:00:00'))).toBe(18);
  });

  it('parses the date without timezone drift', () => {
    // A bare `new Date('2013-09-08')` is parsed as UTC midnight, which in a
    // negative-offset timezone is the 7th locally — shifting every age by a day.
    expect(calculateAge('2013-09-08', TODAY)).toBe(13);
  });
});

describe('checkAge', () => {
  it('refuses below the minimum age', () => {
    const result = checkAge('2014-09-09', TODAY); // 11
    expect(result.status).toBe('too-young');
  });

  it('admits exactly the minimum age', () => {
    const result = checkAge(`${TODAY.getFullYear() - MINIMUM_AGE}-09-08`, TODAY);
    expect(result.status).toBe('minor');
  });

  it('flags 13-17 as needing a guardian', () => {
    const result = checkAge('2010-01-01', TODAY); // 16
    expect(result).toEqual({ status: 'minor', age: 16 });
  });

  it('lets an adult consent for themselves', () => {
    const result = checkAge(
      `${TODAY.getFullYear() - AGE_OF_SELF_CONSENT}-09-08`,
      TODAY,
    );
    expect(result).toEqual({ status: 'ok', age: AGE_OF_SELF_CONSENT });
  });

  it('rejects a future date of birth', () => {
    expect(checkAge('2027-01-01', TODAY).status).toBe('invalid');
  });

  it('rejects an empty or malformed value', () => {
    expect(checkAge('', TODAY).status).toBe('invalid');
    expect(checkAge('not-a-date', TODAY).status).toBe('invalid');
  });

  it('rejects an implausible age', () => {
    expect(checkAge('1850-01-01', TODAY).status).toBe('invalid');
  });
});
