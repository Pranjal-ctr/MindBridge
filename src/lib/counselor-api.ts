/**
 * Kio Counselor API — sessions and session notes.
 *
 * Availability lives in CounselorAvailability.tsx, which talks to
 * /counselors/availability directly; this module covers the session lifecycle
 * (schedule → run → complete) and the notes attached to each session.
 */

import api from './api';
import type {
  CounselorNoteListResponse,
  CounselorSession,
  CounselorSessionListResponse,
  CounselorSessionNote,
  CounselorSessionStatus,
} from './types';

/** All sessions for the signed-in counselor, newest first. */
export async function listSessions(
  status?: CounselorSessionStatus
): Promise<CounselorSessionListResponse> {
  const { data } = await api.get<CounselorSessionListResponse>('/counselors/sessions', {
    params: status ? { status } : undefined,
  });
  return data;
}

/** Schedule a session with a student. `scheduledAt` must be an ISO string. */
export async function createSession(
  studentId: string,
  scheduledAt: string
): Promise<CounselorSession> {
  const { data } = await api.post<CounselorSession>('/counselors/sessions', {
    student_id: studentId,
    scheduled_at: scheduledAt,
  });
  return data;
}

/** Move a session through its lifecycle. The API requires `status` on every update. */
export async function updateSessionStatus(
  sessionId: string,
  status: CounselorSessionStatus,
  aiSummary?: string
): Promise<CounselorSession> {
  const { data } = await api.put<CounselorSession>(`/counselors/sessions/${sessionId}`, {
    status,
    ai_summary: aiSummary ?? null,
  });
  return data;
}

export async function listSessionNotes(sessionId: string): Promise<CounselorSessionNote[]> {
  const { data } = await api.get<CounselorNoteListResponse>(
    `/counselors/sessions/${sessionId}/notes`
  );
  return data.notes;
}

export async function addSessionNote(
  sessionId: string,
  noteText: string
): Promise<CounselorSessionNote> {
  const { data } = await api.post<CounselorSessionNote>(
    `/counselors/sessions/${sessionId}/notes`,
    { note_text: noteText }
  );
  return data;
}

/** Split a session list into upcoming (soonest first) and past (most recent first). */
export function splitSessions(sessions: CounselorSession[]) {
  const now = Date.now();
  const isOpen = (s: CounselorSession) =>
    s.status === 'scheduled' || s.status === 'in_progress';

  const upcoming = sessions
    .filter((s) => isOpen(s) && new Date(s.scheduled_at).getTime() >= now)
    .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime());

  const past = sessions
    .filter((s) => !upcoming.includes(s))
    .sort((a, b) => new Date(b.scheduled_at).getTime() - new Date(a.scheduled_at).getTime());

  return { upcoming, past };
}
