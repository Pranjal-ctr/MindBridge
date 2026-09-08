/**
 * Soft "please verify your email" nag.
 *
 * Rendered once inside ProtectedRoute so every signed-in surface picks it up.
 * Nothing is blocked while unverified — this is a reminder, not a gate. Dismissal
 * is per browser session, so it reappears next sign-in until the address is confirmed.
 */

import { useCallback, useState } from 'react';
import { Loader2, MailWarning, X } from 'lucide-react';
import { useAuth } from '../../lib/auth-context';
import { resendVerification } from '../../lib/auth-api';

const DISMISS_KEY = 'kio_verify_banner_dismissed';

type SendState = 'idle' | 'sending' | 'sent' | 'failed';

export function VerifyBanner() {
  const { user, isAuthenticated } = useAuth();
  const [dismissed, setDismissed] = useState(
    () => sessionStorage.getItem(DISMISS_KEY) === '1'
  );
  const [sendState, setSendState] = useState<SendState>('idle');

  const handleResend = useCallback(async () => {
    setSendState('sending');
    try {
      await resendVerification();
      setSendState('sent');
    } catch {
      setSendState('failed');
    }
  }, []);

  const handleDismiss = useCallback(() => {
    sessionStorage.setItem(DISMISS_KEY, '1');
    setDismissed(true);
  }, []);

  if (!isAuthenticated || !user || user.is_verified || dismissed) return null;

  return (
    <div className="bg-amber-50 border-b border-amber-200 dark:bg-amber-950/40 dark:border-amber-900">
      <div className="max-w-7xl mx-auto px-4 py-2.5 flex items-center gap-3 text-sm">
        <MailWarning className="w-4 h-4 shrink-0 text-amber-600 dark:text-amber-500" />

        <p className="flex-1 text-amber-900 dark:text-amber-200">
          {sendState === 'sent' ? (
            <>
              Verification email sent to{' '}
              <span className="font-medium">{user.email}</span>. Check your inbox and spam folder.
            </>
          ) : (
            <>
              Please verify your email address{' '}
              <span className="font-medium">{user.email}</span> to secure your account.
            </>
          )}
        </p>

        {sendState !== 'sent' && (
          <button
            onClick={handleResend}
            disabled={sendState === 'sending'}
            className="shrink-0 font-medium text-amber-900 dark:text-amber-200 underline underline-offset-2 hover:no-underline disabled:opacity-60 flex items-center gap-1.5"
          >
            {sendState === 'sending' && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            {sendState === 'failed' ? 'Try again' : 'Resend email'}
          </button>
        )}

        <button
          onClick={handleDismiss}
          aria-label="Dismiss verification reminder"
          className="shrink-0 p-1 rounded-md text-amber-700 hover:bg-amber-100 dark:text-amber-400 dark:hover:bg-amber-900/50"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
