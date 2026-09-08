/**
 * Schedule a counselor session with a specific student.
 *
 * Separate from CounselorAvailability: availability slots are open offers any
 * student can book, whereas this books a named student directly — the path a
 * counselor takes after reviewing a risk alert.
 */

import { useState, type FormEvent } from 'react';
import { CalendarPlus, Loader2, X } from 'lucide-react';
import { createSession } from '../../lib/counselor-api';
import { apiErrorDetail } from '../../lib/admin-api';

interface Props {
  studentId: string;
  studentName: string;
  onClose: () => void;
  onScheduled: () => void;
}

/** Local datetime default: tomorrow at 15:00, in the counselor's own timezone. */
function defaultDate(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
}

export function ScheduleSessionDialog({ studentId, studentName, onClose, onScheduled }: Props) {
  const [date, setDate] = useState(defaultDate);
  const [time, setTime] = useState('15:00');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!date || !time) return;

    // `new Date('YYYY-MM-DDTHH:mm')` is parsed as local time, so toISOString()
    // converts the counselor's wall-clock choice to UTC for the API.
    const scheduledAt = new Date(`${date}T${time}`);
    if (Number.isNaN(scheduledAt.getTime())) {
      setError('That date and time is not valid.');
      return;
    }

    setBusy(true);
    setError(null);
    try {
      await createSession(studentId, scheduledAt.toISOString());
      onScheduled();
      onClose();
    } catch (err) {
      setError(apiErrorDetail(err, 'Could not schedule the session. Please try again.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={`Schedule a session with ${studentName}`}
    >
      <div className="w-full max-w-sm bg-card border border-border rounded-xl shadow-lg">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="font-semibold">Schedule session</h2>
          <button onClick={onClose} aria-label="Close" className="p-1 rounded-md hover:bg-muted">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={submit} className="p-4 space-y-4">
          <p className="text-sm text-muted-foreground">
            With <span className="font-medium text-foreground">{studentName}</span>
          </p>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium mb-1.5 block">Date</label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-lg bg-input-background focus:outline-none focus:ring-2 focus:ring-ring"
                required
              />
            </div>
            <div>
              <label className="text-sm font-medium mb-1.5 block">Time</label>
              <input
                type="time"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-lg bg-input-background focus:outline-none focus:ring-2 focus:ring-ring"
                required
              />
            </div>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-muted text-foreground rounded-lg hover:bg-muted/80 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy}
              className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition disabled:opacity-60 flex items-center justify-center gap-2"
            >
              {busy ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CalendarPlus className="w-4 h-4" />
              )}
              Schedule
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
