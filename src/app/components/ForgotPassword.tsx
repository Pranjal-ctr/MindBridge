/**
 * Request a password-reset link: /forgot-password
 *
 * The success state is deliberately vague ("if an account exists…"). The API
 * answers identically for known and unknown addresses so it can't be used to
 * discover who has a Kio account, and the copy here must not undo that.
 */

import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Loader2, Mail, MailCheck } from 'lucide-react';
import { KioLogo } from './KioLogo';
import { Disclaimer } from './Disclaimer';
import { authErrorMessage, forgotPassword } from '../../lib/auth-api';

export function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      await forgotPassword(email.trim().toLowerCase());
      setSent(true);
    } catch (err) {
      setError(authErrorMessage(err, 'Something went wrong. Please try again.'));
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
          {sent ? (
            <div className="text-center">
              <div className="w-14 h-14 mx-auto rounded-full bg-accent/15 flex items-center justify-center">
                <MailCheck className="w-8 h-8 text-accent" />
              </div>
              <h1 className="mt-6 text-xl font-semibold text-foreground">Check your inbox</h1>
              <p className="mt-2 text-sm text-muted-foreground">
                If an account exists for <span className="font-medium text-foreground">{email}</span>,
                we've sent a link to reset your password. It expires in one hour.
              </p>
              <p className="mt-4 text-xs text-muted-foreground">
                Don't see it? Check your spam folder, or{' '}
                <button
                  onClick={() => setSent(false)}
                  className="text-primary hover:underline"
                >
                  try a different address
                </button>
                .
              </p>
              <Link
                to="/login"
                className="mt-6 inline-flex items-center gap-2 text-sm text-primary hover:underline"
              >
                <ArrowLeft className="w-4 h-4" /> Back to sign in
              </Link>
            </div>
          ) : (
            <>
              <h1 className="text-xl font-semibold text-foreground">Forgot your password?</h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Enter the email address on your account and we'll send you a link to set a new password.
              </p>

              <form onSubmit={handleSubmit} className="mt-6 space-y-4">
                <div>
                  <label className="text-sm font-medium text-foreground mb-2 block">Email</label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      autoComplete="email"
                      className="w-full pl-11 pr-4 py-3 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-ring bg-input-background"
                      required
                    />
                  </div>
                </div>

                {error && <p className="text-sm text-destructive">{error}</p>}

                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full py-3 rounded-xl bg-primary text-primary-foreground font-medium hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" /> Sending…
                    </>
                  ) : (
                    'Send reset link'
                  )}
                </button>
              </form>

              <p className="mt-4 text-xs text-muted-foreground text-center">
                Signed up with Google? Use <span className="font-medium">Continue with Google</span> on
                the sign-in page instead — those accounts have no password.
              </p>

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
