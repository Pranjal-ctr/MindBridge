/**
 * Guardian consent landing page — reached only from the emailed link.
 *
 * Public route: the person deciding is a parent with no Kio account. The signed
 * token in the URL is their authorisation, which is also why a decision is
 * one-shot server-side (a forwarded email must not be able to flip it).
 *
 * The page states the privacy boundary before the buttons, not after. A
 * guardian who approves expecting to read their child's messages has not given
 * informed consent, and the student loses a service they were told was private.
 */

import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, Check, Loader2, ShieldCheck, X } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { decideGuardianConsent, getGuardianContext } from '../../lib/consent-api';
import type { GuardianConsentContext } from '../../lib/types';
import { KioLogo } from './KioLogo';

type Decision = 'granted' | 'denied';

export function GuardianConsent() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';

  const [context, setContext] = useState<GuardianConsentContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [decision, setDecision] = useState<Decision | null>(null);

  const load = useCallback(async () => {
    if (!token) {
      setError('This link is missing its token. Please use the link from the email.');
      setLoading(false);
      return;
    }
    try {
      setContext(await getGuardianContext(token));
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data
        ?.detail;
      setError(detail ?? 'This consent link is invalid or has expired.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const decide = async (granted: boolean) => {
    setSubmitting(true);
    setError(null);
    try {
      const result = await decideGuardianConsent(token, granted);
      setDecision(result.guardian_consent_status as Decision);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data
        ?.detail;
      setError(detail ?? 'Could not record your decision. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const studentName = context
    ? `${context.student_first_name} ${context.student_last_name}`.trim()
    : '';

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-2xl items-center px-4 py-4">
          <KioLogo className="h-7 w-auto" />
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-4 py-10">
        {loading && (
          <div className="flex items-center justify-center py-24 text-muted-foreground">
            <Loader2 className="mr-3 h-5 w-5 animate-spin" />
            Loading…
          </div>
        )}

        {!loading && error && !context && (
          <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-5">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-destructive" />
              <div>
                <h1 className="font-medium text-destructive">Link not valid</h1>
                <p className="mt-1 text-sm text-destructive/90">{error}</p>
                <p className="mt-3 text-sm text-muted-foreground">
                  Ask your child to send a new request from their Kio account.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Decision recorded */}
        {decision && (
          <div
            className={`rounded-xl border p-6 ${
              decision === 'granted'
                ? 'border-emerald-200 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950/40'
                : 'border-border bg-card'
            }`}
          >
            <div className="flex items-start gap-3">
              {decision === 'granted' ? (
                <Check className="mt-0.5 h-6 w-6 flex-shrink-0 text-emerald-600" />
              ) : (
                <X className="mt-0.5 h-6 w-6 flex-shrink-0 text-muted-foreground" />
              )}
              <div>
                <h1 className="text-lg font-semibold">
                  {decision === 'granted' ? 'Approved — thank you' : 'Not approved'}
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  {decision === 'granted'
                    ? `${studentName} can now use their Kio account. You can withdraw this at any time by contacting us.`
                    : `${studentName}'s account will stay inactive. If this was a mistake, ask them to send a new request.`}
                </p>
                <Link
                  to="/"
                  className="mt-4 inline-block text-sm text-primary hover:underline"
                >
                  Learn more about Kio
                </Link>
              </div>
            </div>
          </div>
        )}

        {/* Decide */}
        {!loading && context && !decision && (
          <>
            {context.already_decided ? (
              <div className="rounded-xl border border-border bg-card p-6">
                <h1 className="text-lg font-semibold">Already answered</h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  A decision has already been recorded for {studentName}&apos;s account.
                  If you need to change it, please contact us.
                </p>
              </div>
            ) : (
              <>
                <h1
                  className="text-2xl font-semibold tracking-tight"
                  style={{ fontFamily: 'var(--font-heading)' }}
                >
                  Approve {studentName}&apos;s Kio account
                </h1>
                <p className="mt-2 text-sm text-muted-foreground">
                  {studentName} signed up for Kio
                  {context.school_name ? ` through ${context.school_name}` : ''} and listed
                  you as their parent or guardian. Because they are under 18, we need your
                  permission before their account can be used.
                </p>

                <div className="mt-6 space-y-4 rounded-xl border border-border bg-card p-5 text-sm">
                  <div>
                    <h2 className="font-medium">What Kio is</h2>
                    <p className="mt-1 text-muted-foreground">
                      A private AI companion students can talk to about school stress,
                      friendships, motivation and how they are feeling. It is not a
                      medical or diagnostic service and does not replace professional
                      care.
                    </p>
                  </div>

                  <div>
                    <h2 className="font-medium">What you will see</h2>
                    <p className="mt-1 text-muted-foreground">
                      Wellbeing insights — mood trends, general areas of stress, and
                      suggestions for supporting them.
                    </p>
                  </div>

                  <div>
                    <h2 className="font-medium">What you will not see</h2>
                    <p className="mt-1 text-muted-foreground">
                      Their actual conversations. Those stay private. That privacy is
                      what makes students willing to be honest, which is what makes the
                      support work.
                    </p>
                  </div>

                  <div className="rounded-lg bg-muted p-3">
                    <div className="flex items-start gap-2">
                      <ShieldCheck className="mt-0.5 h-4 w-4 flex-shrink-0 text-primary" />
                      <p className="text-muted-foreground">
                        <strong className="text-foreground">The exception is safety.</strong>{' '}
                        If Kio detects a serious risk, a trained counselor is alerted and
                        you are notified that something needs attention.
                      </p>
                    </div>
                  </div>

                  <p className="text-muted-foreground">
                    Full detail is in our{' '}
                    <Link to="/privacy" target="_blank" className="text-primary hover:underline">
                      Privacy Policy
                    </Link>{' '}
                    and{' '}
                    <Link to="/terms" target="_blank" className="text-primary hover:underline">
                      Terms of Service
                    </Link>
                    .
                  </p>
                </div>

                {error && (
                  <div className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                    {error}
                  </div>
                )}

                <div className="mt-6 flex flex-wrap gap-3">
                  <button
                    onClick={() => decide(true)}
                    disabled={submitting}
                    className="flex items-center gap-2 rounded-xl bg-primary px-6 py-3 font-medium text-primary-foreground transition hover:bg-primary/90 disabled:opacity-60"
                  >
                    {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                    I approve this account
                  </button>
                  <button
                    onClick={() => decide(false)}
                    disabled={submitting}
                    className="rounded-xl border border-border px-6 py-3 font-medium transition hover:bg-accent disabled:opacity-60"
                  >
                    I do not approve
                  </button>
                </div>

                <p className="mt-4 text-xs text-muted-foreground">
                  Your decision is recorded with the date and time. Declining keeps the
                  account inactive.
                </p>
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
