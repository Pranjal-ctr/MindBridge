/**
 * Frontend error reporting.
 *
 * Off unless VITE_SENTRY_DSN is set, so a developer's console errors and CI
 * runs never reach a production project. What gets sent is deliberately
 * narrow: Kio's frontend renders counseling conversations, wellness scores and
 * children's names, and an error report is not the place for any of it.
 *
 * VITE_* values are inlined at build time, so a build without a DSN contains
 * no reporting configuration at all.
 */

import * as Sentry from '@sentry/react';

const DSN = import.meta.env.VITE_SENTRY_DSN ?? '';
const ENVIRONMENT = import.meta.env.VITE_SENTRY_ENVIRONMENT ?? import.meta.env.MODE;

let started = false;

/** Fields whose values must never leave the browser in an error report. */
const SENSITIVE_KEYS = [
  'password',
  'token',
  'access_token',
  'refresh_token',
  'authorization',
  'message',
  'content',
  'reflection',
  'note',
  'notes',
  'transcript',
];

function redact(value: unknown, depth = 0): unknown {
  if (depth > 4 || value === null || typeof value !== 'object') return value;
  if (Array.isArray(value)) return value.map((item) => redact(item, depth + 1));

  const out: Record<string, unknown> = {};
  for (const [key, inner] of Object.entries(value as Record<string, unknown>)) {
    out[key] = SENSITIVE_KEYS.includes(key.toLowerCase())
      ? '[redacted]'
      : redact(inner, depth + 1);
  }
  return out;
}

/**
 * Strip the query string from a URL.
 *
 * Email verification, password reset and guardian consent links all carry a
 * one-time token there. A breadcrumb recording the navigation would otherwise
 * hand over a working credential.
 */
function stripQuery(url: string): string {
  const cut = url.indexOf('?');
  return cut === -1 ? url : url.slice(0, cut);
}

export function initMonitoring(): boolean {
  if (started || !DSN) return false;

  Sentry.init({
    dsn: DSN,
    environment: ENVIRONMENT,
    // No session replay and no performance tracing. Replay would record the
    // chat screen, which is the single most sensitive surface in the product.
    tracesSampleRate: 0,
    sendDefaultPii: false,

    beforeSend(event) {
      if (event.request?.url) event.request.url = stripQuery(event.request.url);
      if (event.request) {
        delete event.request.cookies;
        delete (event.request as { data?: unknown }).data;
        if (event.request.headers) delete event.request.headers.Authorization;
      }
      if (event.user) {
        delete event.user.email;
        delete event.user.username;
        delete event.user.ip_address;
      }
      if (event.extra) event.extra = redact(event.extra) as Record<string, unknown>;
      return event;
    },

    beforeBreadcrumb(breadcrumb) {
      // Console breadcrumbs capture whatever the app logged, which during
      // development includes API payloads. Drop them entirely.
      if (breadcrumb.category === 'console') return null;
      if (typeof breadcrumb.data?.url === 'string') {
        breadcrumb.data.url = stripQuery(breadcrumb.data.url);
      }
      return breadcrumb;
    },

    // Expected auth failures are not defects. A 401 on a stale token is the
    // system working; reporting it buries the errors that are real.
    ignoreErrors: [
      'Request failed with status code 401',
      'Request failed with status code 403',
      'Non-Error promise rejection captured',
      'ResizeObserver loop limit exceeded',
    ],
  });

  // The ErrorBoundary looks for window.Sentry so it stays decoupled from this
  // module and keeps working if reporting is not configured.
  (window as unknown as { Sentry: typeof Sentry }).Sentry = Sentry;
  started = true;
  return true;
}

/** Report a handled error that the user should not have to describe. */
export function reportError(error: unknown, context?: Record<string, unknown>): void {
  if (!started) return;
  try {
    Sentry.withScope((scope) => {
      if (context) scope.setContext('kio', redact(context) as Record<string, unknown>);
      Sentry.captureException(error);
    });
  } catch {
    // Reporting must never break the surface it is reporting on.
  }
}
