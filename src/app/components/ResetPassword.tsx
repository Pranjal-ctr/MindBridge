/**
 * Set a new password from an emailed link: /reset-password?token=...
 *
 * Reset links are single-use and short-lived, so an expired/replayed token is a
 * normal outcome, not an edge case — it routes straight back to /forgot-password.
 */

import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, CheckCircle2, Loader2, Lock } from 'lucide-react';
import { KioLogo } from './KioLogo';
import { Disclaimer } from './Disclaimer';
import { authErrorMessage, resetPassword } from '../../lib/auth-api';

const MIN_PASSWORD_LENGTH = 8;

export function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (password !== confirm) {
      setError('The two passwords do not match.');
      return;
    }
    if (!token) {
      setError('This link is missing its reset code. Please open the link from your email.');
      return;
    }

    setIsSubmitting(true);
    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(
        authErrorMessage(err, 'This reset link is invalid or has expired. Please request a new one.')
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          <KioLogo className="h-10 w-auto" />
        </div>

        <div className="bg-card border border-border rounded-2xl p-8 shadow-sm">
          {done ? (
            <div className="text-center">
              <div className="w-14 h-14 mx-auto rounded-full bg-accent/15 flex items-center justify-center">
                <CheckCircle2 className="w-8 h-8 text-accent" />
              </div>
              <h1 className="mt-6 text-xl font-semibold text-foreground">Password updated</h1>
              <p className="mt-2 text-sm text-muted-foreground">
                You can now sign in with your new password.
              </p>
              <button
                onClick={() => navigate('/login')}
                className="mt-6 w-full py-3 rounded-xl bg-primary text-primary-foreground font-medium hover:opacity-90 transition-opacity"
              >
                Sign in
              </button>
            </div>
          ) : (
            <>
              <h1 className="text-xl font-semibold text-foreground">Choose a new password</h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Pick something you haven't used before. This link works only once.
              </p>

              <form onSubmit={handleSubmit} className="mt-6 space-y-4">
                <div>
                  <label className="text-sm font-medium text-foreground mb-2 block">
                    New password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder={`Min ${MIN_PASSWORD_LENGTH} characters`}
                      autoComplete="new-password"
                      className="w-full pl-11 pr-4 py-3 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-ring bg-input-background"
                      required
                      minLength={MIN_PASSWORD_LENGTH}
                    />
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium text-foreground mb-2 block">
                    Confirm new password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <input
                      type="password"
                      value={confirm}
                      onChange={(e) => setConfirm(e.target.value)}
                      placeholder="Re-enter your new password"
                      autoComplete="new-password"
                      className="w-full pl-11 pr-4 py-3 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-ring bg-input-background"
                      required
                    />
                  </div>
                </div>

                {error && (
                  <div className="text-sm text-destructive">
                    <p>{error}</p>
                    <Link to="/forgot-password" className="underline">
                      Request a new reset link
                    </Link>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full py-3 rounded-xl bg-primary text-primary-foreground font-medium hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" /> Updating…
                    </>
                  ) : (
                    'Update password'
                  )}
                </button>
              </form>

              <Link
                to="/login"
                className="mt-6 flex items-center justify-center gap-2 text-sm text-primary hover:underline"
              >
                <ArrowLeft className="w-4 h-4" /> Back to sign in
              </Link>
            </>
          )}
        </div>

        <Disclaimer variant="short" className="mt-6 justify-center" />
      </div>
    </div>
  );
}
