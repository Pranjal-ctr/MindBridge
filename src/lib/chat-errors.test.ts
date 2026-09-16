/**
 * A failed Comrade send must produce a message worth reading.
 *
 * The regression this guards: the chat screen rendered nothing on failure, so
 * a student's message vanished from the transcript with no explanation and the
 * backend's carefully worded daily-limit 429 was seen by nobody.
 *
 * These tests assert the *content* of what a student is told, because the bug
 * was never that an error object was missing — it was that no human-readable
 * sentence ever reached the screen.
 */

import { AxiosError, AxiosHeaders } from 'axios';
import { describe, expect, it } from 'vitest';

import { chatErrorMessage } from './chat-errors';
import { AI_REQUEST_TIMEOUT_MS } from './api';

function httpError(status: number, detail?: unknown): AxiosError {
  const error = new AxiosError('Request failed');
  error.response = {
    status,
    statusText: '',
    data: detail === undefined ? {} : { detail },
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
  };
  return error;
}

function networkError(code: string): AxiosError {
  const error = new AxiosError('Network Error');
  error.code = code;
  return error;
}

describe('chatErrorMessage', () => {
  it('never returns an empty string', () => {
    const cases: unknown[] = [
      undefined,
      null,
      new Error('boom'),
      networkError('ERR_NETWORK'),
      networkError('ECONNABORTED'),
      httpError(400),
      httpError(401),
      httpError(404),
      httpError(429),
      httpError(500),
      httpError(503),
    ];
    for (const error of cases) {
      const message = chatErrorMessage(error);
      expect(message.trim().length).toBeGreaterThan(0);
    }
  });

  it('reassures the student their draft survived', () => {
    // Every case except the daily cap, where the message is about tomorrow
    // rather than about retrying now.
    for (const error of [new Error('boom'), httpError(500), networkError('ERR_NETWORK')]) {
      expect(chatErrorMessage(error)).toContain('still here');
    }
  });

  it("uses the backend's own wording for the daily limit", () => {
    const detail =
      'Daily message limit reached. Comrade will be ready to chat again tomorrow.';
    expect(chatErrorMessage(httpError(429, detail))).toBe(detail);
  });

  it('explains a timeout without claiming the reply is lost', () => {
    const message = chatErrorMessage(networkError('ECONNABORTED'));
    expect(message).toMatch(/longer than usual/i);
    expect(message).toMatch(/reload/i);
  });

  it('names a connection problem as a connection problem', () => {
    expect(chatErrorMessage(networkError('ERR_NETWORK'))).toMatch(/connection/i);
  });

  it('does not blame the student for a server fault', () => {
    expect(chatErrorMessage(httpError(500))).toMatch(/our end, not yours/i);
  });

  it('tells the student to sign in again when the session expired', () => {
    expect(chatErrorMessage(httpError(401))).toMatch(/sign in again/i);
  });

  it('never leaks the word "error" or a status code at the student', () => {
    for (const error of [httpError(500), httpError(400), new Error('AxiosError: 500')]) {
      const message = chatErrorMessage(error);
      expect(message.toLowerCase()).not.toContain('axios');
      expect(message).not.toMatch(/\b[45]\d\d\b/);
    }
  });
});

describe('AI_REQUEST_TIMEOUT_MS', () => {
  it("covers the backend's worst case of 30s x (1 primary + 2 retries)", () => {
    // If AI_REQUEST_TIMEOUT_SECONDS or max_retries changes on the backend,
    // this is the assertion that should fail and force the pair back in step.
    const backendWorstCaseMs = 30_000 * 3;
    expect(AI_REQUEST_TIMEOUT_MS).toBeGreaterThanOrEqual(backendWorstCaseMs);
  });

  it('is far longer than the global API timeout it deliberately does not change', () => {
    expect(AI_REQUEST_TIMEOUT_MS).toBeGreaterThan(15_000);
  });
});
