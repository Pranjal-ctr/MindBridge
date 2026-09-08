/**
 * Kio Auth API — emailed one-time link flows.
 *
 * Email verification and password reset live here rather than in auth-context
 * because none of them change the logged-in session: they are one-shot calls
 * made from public pages (/verify-email, /forgot-password, /reset-password)
 * or from the verification banner.
 */

import type { AxiosError } from 'axios';
import api from './api';
import type { ApiError } from './types';

/** Confirm an email address using the token from a verification email. */
export async function verifyEmail(token: string): Promise<void> {
  await api.post('/auth/verify', { token });
}

/** Re-send the verification email to the signed-in user. */
export async function resendVerification(): Promise<void> {
  await api.post('/auth/verify/resend');
}

/**
 * Request a password-reset link.
 *
 * Always resolves for any well-formed address — the backend deliberately gives
 * the same answer whether or not an account exists, so the UI must not imply
 * that a success means "this email is registered".
 */
export async function forgotPassword(email: string): Promise<void> {
  await api.post('/auth/password/forgot', { email });
}

/** Set a new password using the token from a reset email. */
export async function resetPassword(token: string, password: string): Promise<void> {
  await api.post('/auth/password/reset', { token, password });
}

/** Pull a readable message out of an API error, with a caller-supplied fallback. */
export function authErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as AxiosError<ApiError>)?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  return fallback;
}
