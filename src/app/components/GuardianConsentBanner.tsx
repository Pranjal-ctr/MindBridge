/**
 * Banner shown to a minor whose guardian has not yet approved their account.
 *
 * Mounted once inside ProtectedRoute, alongside VerifyBanner, so every
 * signed-in surface gets it from one place.
 *
 * Deliberately NOT a hard block. The account exists, the student can look
 * around, and the prompt is persistent rather than a wall. A blocked screen
 * teaches a struggling 15-year-old that the thing they reached for does not
 * work; a banner tells them what is missing and how to fix it. Whether soft
 * enforcement is legally sufficient is one of the open questions flagged in
 * backend/app/consent/policy.py — if the answer is no, this is the component
 * that becomes a gate.
 */

import { useEffect, useState } from 'react';
import { AlertCircle, Check, Loader2, Send, X } from 'lucide-react';
import { getMyConsentStatus, requestGuardianConsent } from '../../lib/consent-api';
import { useAuth } from '../../lib/auth-context';

export function GuardianConsentBanner() {
  const { user } = useAuth();

  const [dismissed, setDismissed] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [guardianEmail, setGuardianEmail] = useState('');
  const [sending, setSending] = useState(false);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Only fetch when the user object already says consent may be outstanding —
  // no extra request for the adults who are the majority of sessions.
  const maybePending =
    user?.guardian_consent_status === 'pending' ||
    user?.guardian_consent_status === 'denied';

  useEffect(() => {
    if (!maybePending) return;
    let cancelled = false;
    getMyConsentStatus()
      .then((s) => {
        if (!cancelled) {
          setStatus(s.guardian_consent_status);
          if (s.guardian_email) setSentTo(s.guardian_email);
        }
      })
      .catch(() => {/* banner just stays hidden if this fails */});
    return () => {
      cancelled = true;
    };
  }, [maybePending]);

  const effective = status ?? user?.guardian_consent_status ?? null;

  if (!maybePending || dismissed) return null;
  if (effective !== 'pending' && effective !== 'denied') return null;

  const send = async () => {
    setSending(true);
    setError(null);
    try {
      await requestGuardianConsent(guardianEmail.trim());
      setSentTo(guardianEmail.trim());
      setGuardianEmail('');
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data
        ?.detail;
      setError(detail ?? 'Could not send the request. Please check the address.');
    } finally {
      setSending(false);
    }
  };

  const denied = effective === 'denied';

  return (
    <div
      className={`border-b px-4 py-3 ${
        denied
          ? 'border-destructive/30 bg-destructive/10'
          : 'border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/40'
      }`}
    >
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-3 text-sm">
        <AlertCircle
          className={`h-4 w-4 flex-shrink-0 ${denied ? 'text-destructive' : 'text-amber-600'}`}
        />

        <div className="min-w-0 flex-1">
          {denied ? (
            <span className="text-destructive">
              Your parent or guardian did not approve this account. Contact your school
              counselor if you think this is a mistake.
            </span>
          ) : sentTo ? (
            <span className="flex items-center gap-1.5 text-amber-900 dark:text-amber-200">
              <Check className="h-3.5 w-3.5" />
              Approval request sent to <strong>{sentTo}</strong>. We&apos;ll unlock your
              account as soon as they confirm.
            </span>
          ) : (
            <span className="text-amber-900 dark:text-amber-200">
              Because you&apos;re under 18, a parent or guardian needs to approve your
              account. Enter their email and we&apos;ll send them a link.
            </span>
          )}
          {error && <div className="mt-1 text-xs text-destructive">{error}</div>}
        </div>

        {!denied && !sentTo && (
          <div className="flex items-center gap-2">
            <input
              type="email"
              value={guardianEmail}
              onChange={(e) => setGuardianEmail(e.target.value)}
              placeholder="parent@example.com"
              className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-sm dark:border-amber-800 dark:bg-transparent"
              aria-label="Parent or guardian email"
            />
            <button
              onClick={send}
              disabled={sending || !guardianEmail.includes('@')}
              className="flex items-center gap-1.5 rounded-lg bg-amber-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-amber-700 disabled:opacity-50"
            >
              {sending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Send className="h-3.5 w-3.5" />
              )}
              Send
            </button>
          </div>
        )}

        {sentTo && (
          <button
            onClick={() => setSentTo(null)}
            className="text-xs text-amber-700 underline dark:text-amber-300"
          >
            Use a different address
          </button>
        )}

        <button
          onClick={() => setDismissed(true)}
          className="ml-auto text-muted-foreground hover:text-foreground"
          aria-label="Dismiss"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
