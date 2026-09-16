/**
 * Turning a failed chat send into something worth reading.
 *
 * Every message here is written for a teenager who has just watched their own
 * words vanish, so each one says what happened, whether their text is safe,
 * and what to do next. None of them blames the student, and none of them says
 * "error".
 *
 * The daily-limit case is the reason this file is not just a default string:
 * the backend returns a carefully worded 429 that no user had ever seen,
 * because the chat screen rendered nothing at all on failure.
 */

import axios from 'axios';

/** What the student's draft is doing while this message is on screen. */
const DRAFT_IS_SAFE = 'Your message is still here.';

export function chatErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) {
    return `Something went wrong sending that. ${DRAFT_IS_SAFE} Try again in a moment.`;
  }

  // Aborted client-side. After AI_REQUEST_TIMEOUT_MS the server has almost
  // certainly given up too, but a reply that lands late will appear on reload,
  // so the wording does not promise it is gone.
  if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
    return `Comrade is taking longer than usual to reply. ${DRAFT_IS_SAFE} Try again, or reload to see if the reply arrived.`;
  }

  if (error.code === 'ERR_NETWORK') {
    return `Can't reach Kio right now — check your connection. ${DRAFT_IS_SAFE}`;
  }

  const status = error.response?.status;
  const detail = error.response?.data?.detail;

  // The backend writes these for the student, not for a developer: the daily
  // cap and the guardrail refusals all arrive this way. Prefer its wording.
  if (typeof detail === 'string' && detail.trim()) {
    return status === 429 ? detail : `${detail} ${DRAFT_IS_SAFE}`;
  }

  if (status === 429) {
    return 'Comrade needs a short break. Try again in a minute.';
  }
  if (status === 401 || status === 403) {
    return 'Your session expired. Sign in again and your message will still be here.';
  }
  if (status === 404) {
    return `That conversation is no longer available. ${DRAFT_IS_SAFE} Start a new chat to send it.`;
  }
  if (typeof status === 'number' && status >= 500) {
    return `Kio had a problem on our end, not yours. ${DRAFT_IS_SAFE} Try again in a moment.`;
  }

  return `Something went wrong sending that. ${DRAFT_IS_SAFE} Try again in a moment.`;
}
