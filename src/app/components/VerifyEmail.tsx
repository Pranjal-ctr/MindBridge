/**
 * Landing page for the link in a verification email: /verify-email?token=...
 *
 * The token is consumed once on mount. Because links expire, the failure state
 * is a real path rather than a dead end — signed-in users can send themselves a
 * fresh link without leaving the page.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle2, Loader2, MailWarning, RefreshCw } from 'lucide-react';
import { KioLogo } from './KioLogo';
import { Disclaimer } from './Disclaimer';
import { useAuth } from '../../lib/auth-context';
import { getDashboardRoute } from '../../lib/protected-route';
import { authErrorMessage, resendVerification, verifyEmail } from '../../lib/auth-api';

type Status = 'verifying' | 'success' | 'error';

export function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, isAuthenticated, refreshUser } = useAuth();

  const [status, setStatus] = useState<Status>('verifying');
  const [message, setMessage] = useState('');
  const [resendState, setResendState] = useState<'idle' | 'sending' | 'sent' | 'failed'>('idle');

  const token = searchParams.get('token');
  // React 18 StrictMode mounts effects twice in dev; verify only once.
  const hasRun = useRef(false);

  useEffect(() => {
    if (hasRun.current) return;
    hasRun.current = true;

    if (!token) {
      setStatus('error');
      setMessage('This link is missing its verification code. Please open the link from your email.');
      return;
    }

    verifyEmail(token)
      .then(async () => {
        setStatus('success');
        // Clears the banner immediately for an already-signed-in user.
        await refreshUser();
      })
      .catch((error) => {
        setStatus('error');
        setMessage(
          authErrorMessage(error, 'This verification link is invalid or has expired.')
        );
      });
  }, [token, refreshUser]);

  const handleResend = useCallback(async () => {
    setResendState('sending');
    try {
      await resendVerification();
      setResendState('sent');
    } catch {
      setResendState('failed');
    }
  }, []);

  const continueTo = isAuthenticated && user ? getDashboardRoute(user.role) : '/login';

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          <KioLogo className="h-10 w-auto" />
        </div>

        <div className="bg-card border border-border rounded-2xl p-8 shadow-sm text-center">
          {status === 'verifying' && (
            <>
              <Loader2 className="w-12 h-12 mx-auto text-primary animate-spin" />
              <h1 className="mt-6 text-xl font-semibold text-foreground">Verifying your email…</h1>
              <p className="mt-2 text-sm text-muted-foreground">This only takes a moment.</p>
            </>
          )}

          {status === 'success' && (
            <>
              <div className="w-14 h-14 mx-auto rounded-full bg-accent/15 flex items-center justify-center">
                <CheckCircle2 className="w-8 h-8 text-accent" />
              </div>
              <h1 className="mt-6 text-xl font-semibold text-foreground">Email verified</h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Thanks for confirming your address. Your Kio account is all set.
              </p>
              <button
                onClick={() => navigate(continueTo)}
                className="mt-6 w-full py-3 rounded-xl bg-primary text-primary-foreground font-medium hover:opacity-90 transition-opacity"
              >
                {isAuthenticated ? 'Go to dashboard' : 'Sign in'}
              </button>
            </>
          )}

          {status === 'error' && (
            <>
              <div className="w-14 h-14 mx-auto rounded-full bg-destructive/10 flex items-center justify-center">
                <MailWarning className="w-8 h-8 text-destructive" />
              </div>
              <h1 className="mt-6 text-xl font-semibold text-foreground">
                We couldn't verify this link
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">{message}</p>

              {isAuthenticated ? (
                <>
                  <button
                    onClick={handleResend}
                    disabled={resendState === 'sending' || resendState === 'sent'}
                    className="mt-6 w-full py-3 rounded-xl bg-primary text-primary-foreground font-medium hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2"
                  >
                    {resendState === 'sending' ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" /> Sending…
                      </>
                    ) : resendState === 'sent' ? (
                      'New link sent'
                    ) : (
                      <>
                        <RefreshCw className="w-4 h-4" /> Send me a new link
                      </>
                    )}
                  </button>
                  {resendState === 'sent' && (
                    <p className="mt-3 text-xs text-muted-foreground">
                      Check your inbox — the new link is valid for 24 hours.
                    </p>
                  )}
                  {resendState === 'failed' && (
                    <p className="mt-3 text-xs text-destructive">
                      Couldn't send a new link. Please try again shortly.
                    </p>
                  )}
                </>
              ) : (
                <Link
                  to="/login"
                  className="mt-6 block w-full py-3 rounded-xl bg-primary text-primary-foreground font-medium hover:opacity-90 transition-opacity"
                >
                  Sign in to request a new link
                </Link>
              )}
            </>
          )}
        </div>

        <Disclaimer variant="short" className="mt-6 justify-center" />
      </div>
    </div>
  );
}
