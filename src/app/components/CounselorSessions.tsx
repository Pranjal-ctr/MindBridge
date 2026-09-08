/**
 * Counselor sessions — upcoming and past, with per-session notes and status.
 *
 * Presentational: the dashboard owns the session list so the stat cards and this
 * list share a single fetch. Notes are loaded lazily per session, since most
 * sessions are never expanded.
 */

import { useCallback, useState } from 'react';
import {
  CalendarClock,
  ChevronDown,
  ChevronRight,
  Clock,
  Loader2,
  NotebookPen,
} from 'lucide-react';
import {
  addSessionNote,
  listSessionNotes,
  updateSessionStatus,
} from '../../lib/counselor-api';
import { splitSessions } from '../../lib/counselor-api';
import type {
  CounselorSession,
  CounselorSessionNote,
  CounselorSessionStatus,
} from '../../lib/types';

const STATUS_OPTIONS: { value: CounselorSessionStatus; label: string }[] = [
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'no_show', label: 'No show' },
];

const STATUS_STYLES: Record<CounselorSessionStatus, string> = {
  scheduled: 'bg-blue-100 text-blue-700',
  in_progress: 'bg-amber-100 text-amber-700',
  completed: 'bg-emerald-100 text-emerald-700',
  cancelled: 'bg-muted text-muted-foreground',
  no_show: 'bg-red-100 text-red-700',
};

function formatWhen(iso: string): string {
  const date = new Date(iso);
  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);

  const time = date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  const sameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString();

  if (sameDay(date, today)) return `${time} today`;
  if (sameDay(date, tomorrow)) return `${time} tomorrow`;
  return `${date.toLocaleDateString([], { month: 'short', day: 'numeric' })}, ${time}`;
}

interface Props {
  sessions: CounselorSession[];
  isLoading: boolean;
  /** Called after a status change so the parent can refetch. */
  onChanged: () => void;
}

export function CounselorSessions({ sessions, isLoading, onChanged }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, CounselorSessionNote[] | 'loading'>>({});
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { upcoming, past } = splitSessions(sessions);

  const toggle = useCallback(
    async (sessionId: string) => {
      if (expanded === sessionId) {
        setExpanded(null);
        return;
      }
      setExpanded(sessionId);
      setDraft('');
      setError(null);
      if (notes[sessionId] && notes[sessionId] !== 'loading') return;

      setNotes((prev) => ({ ...prev, [sessionId]: 'loading' }));
      try {
        const loaded = await listSessionNotes(sessionId);
        setNotes((prev) => ({ ...prev, [sessionId]: loaded }));
      } catch {
        setNotes((prev) => ({ ...prev, [sessionId]: [] }));
        setError('Could not load notes for this session.');
      }
    },
    [expanded, notes]
  );

  const submitNote = async (sessionId: string) => {
    if (!draft.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const note = await addSessionNote(sessionId, draft.trim());
      setNotes((prev) => {
        const existing = prev[sessionId];
        const list = existing && existing !== 'loading' ? existing : [];
        return { ...prev, [sessionId]: [...list, note] };
      });
      setDraft('');
    } catch {
      setError('Could not save the note. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const changeStatus = async (sessionId: string, status: CounselorSessionStatus) => {
    setBusy(true);
    setError(null);
    try {
      await updateSessionStatus(sessionId, status);
      onChanged();
    } catch {
      setError('Could not update the session status.');
    } finally {
      setBusy(false);
    }
  };

  const renderSession = (session: CounselorSession) => {
    const isOpen = expanded === session.counselor_session_id;
    const sessionNotes = notes[session.counselor_session_id];

    return (
      <div
        key={session.counselor_session_id}
        className="border border-border rounded-lg overflow-hidden"
      >
        <div className="flex items-center justify-between gap-3 p-4 bg-muted/50">
          <button
            onClick={() => toggle(session.counselor_session_id)}
            className="flex items-center gap-3 flex-1 text-left min-w-0"
          >
            {isOpen ? (
              <ChevronDown className="w-4 h-4 shrink-0 text-muted-foreground" />
            ) : (
              <ChevronRight className="w-4 h-4 shrink-0 text-muted-foreground" />
            )}
            <div className="min-w-0">
              <div className="font-medium truncate">
                {session.student_name || 'Unnamed student'}
              </div>
              <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <Clock className="w-3.5 h-3.5" />
                {formatWhen(session.scheduled_at)}
              </div>
            </div>
          </button>

          <span
            className={`px-2.5 py-1 rounded-full text-xs font-medium shrink-0 ${
              STATUS_STYLES[session.status]
            }`}
          >
            {STATUS_OPTIONS.find((o) => o.value === session.status)?.label ?? session.status}
          </span>

          <select
            value={session.status}
            disabled={busy}
            onChange={(e) =>
              changeStatus(
                session.counselor_session_id,
                e.target.value as CounselorSessionStatus
              )
            }
            aria-label="Change session status"
            className="shrink-0 text-sm border border-border rounded-lg px-2 py-1.5 bg-input-background disabled:opacity-60"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {isOpen && (
          <div className="p-4 space-y-3 border-t border-border">
            {sessionNotes === 'loading' || sessionNotes === undefined ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading notes…
              </div>
            ) : sessionNotes.length === 0 ? (
              <p className="text-sm text-muted-foreground">No notes on this session yet.</p>
            ) : (
              <ul className="space-y-2">
                {sessionNotes.map((note) => (
                  <li key={note.note_id} className="text-sm bg-muted/60 rounded-lg p-3">
                    <p className="whitespace-pre-wrap">{note.note_text}</p>
                    <div className="mt-1.5 text-xs text-muted-foreground">
                      {new Date(note.created_at).toLocaleString()}
                    </div>
                  </li>
                ))}
              </ul>
            )}

            <div className="flex gap-2">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={2}
                placeholder="Add a session note…"
                className="flex-1 text-sm border border-border rounded-lg px-3 py-2 bg-input-background focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <button
                onClick={() => submitNote(session.counselor_session_id)}
                disabled={busy || !draft.trim()}
                className="px-4 py-2 self-end bg-primary text-primary-foreground rounded-lg text-sm hover:bg-primary/90 transition disabled:opacity-60 flex items-center gap-2"
              >
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <NotebookPen className="w-4 h-4" />}
                Save
              </button>
            </div>

            <p className="text-xs text-muted-foreground">
              Session notes are clinical records. They are visible to you and platform
              administrators — never to the student or their guardians.
            </p>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
      <h2 className="text-lg font-semibold mb-4">Sessions</h2>

      {error && <p className="mb-3 text-sm text-destructive">{error}</p>}

      {isLoading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      ) : sessions.length === 0 ? (
        <div className="border border-dashed border-border rounded-lg py-10 text-center">
          <CalendarClock className="w-8 h-8 mx-auto text-muted-foreground" />
          <p className="mt-3 text-sm text-muted-foreground">
            No sessions yet. Schedule one from a student's profile below.
          </p>
        </div>
      ) : (
        <div className="space-y-5">
          <div>
            <h3 className="text-sm font-medium text-muted-foreground mb-2">
              Upcoming ({upcoming.length})
            </h3>
            {upcoming.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nothing scheduled ahead.</p>
            ) : (
              <div className="space-y-2">{upcoming.map(renderSession)}</div>
            )}
          </div>

          {past.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-muted-foreground mb-2">
                Past ({past.length})
              </h3>
              <div className="space-y-2">{past.map(renderSession)}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
