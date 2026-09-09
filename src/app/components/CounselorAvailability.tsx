/**
 * Counselor availability manager.
 *
 * Schedule-first: a counselor states the hours they work each week and Kio
 * derives bookable slots from that. This replaces the old screen, where every
 * individual slot had to be created by hand and a forgotten week meant a
 * counselor silently vanished from the booking page.
 *
 * Three things live here because they are one decision in the counselor's
 * head — "when am I available?": the weekly pattern, the session settings that
 * divide it into slots, and the dated exceptions that override it.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  CalendarOff,
  CalendarPlus,
  Check,
  Clock,
  Loader2,
  Moon,
  Plus,
  Settings2,
  Trash2,
} from 'lucide-react';
import {
  DAY_NAMES,
  createException,
  createSchedule,
  deleteException,
  deleteSchedule,
  formatTime,
  getSessionSettings,
  listExceptions,
  listSchedules,
  toLocalDateString,
  updateSchedule,
  updateSessionSettings,
} from '../../lib/availability-api';
import type {
  CounselorSchedule,
  CounselorScheduleException,
  DayOfWeek,
  SessionSettings,
} from '../../lib/types';

const DURATIONS = [30, 45, 60];
const BUFFERS = [0, 5, 10, 15];

/**
 * A short list rather than the full IANA set: Kio is India-focused today, and
 * a 400-entry dropdown is a worse answer than five relevant ones plus whatever
 * the counselor already has saved.
 */
const TIMEZONES = [
  'Asia/Kolkata',
  'Asia/Dubai',
  'Asia/Singapore',
  'Europe/London',
  'America/New_York',
  'UTC',
];

export function CounselorAvailability() {
  const [schedules, setSchedules] = useState<CounselorSchedule[]>([]);
  const [exceptions, setExceptions] = useState<CounselorScheduleException[]>([]);
  const [settings, setSettings] = useState<SessionSettings | null>(null);
  const [timezone, setTimezone] = useState('Asia/Kolkata');

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const [addingDay, setAddingDay] = useState<DayOfWeek | null>(null);
  const [newStart, setNewStart] = useState('09:00');
  const [newEnd, setNewEnd] = useState('17:00');

  const [showTimeOff, setShowTimeOff] = useState(false);
  const [offDate, setOffDate] = useState('');
  const [offAllDay, setOffAllDay] = useState(true);
  const [offStart, setOffStart] = useState('09:00');
  const [offEnd, setOffEnd] = useState('13:00');
  const [offReason, setOffReason] = useState('');
  const [offIsExtra, setOffIsExtra] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [scheduleData, exceptionData, settingsData] = await Promise.all([
        listSchedules(),
        listExceptions(),
        getSessionSettings(),
      ]);
      setSchedules(scheduleData.schedules);
      setExceptions(exceptionData.exceptions);
      setSettings(settingsData);
      setTimezone(settingsData.timezone);
    } catch {
      setError('Could not load your availability. Please refresh and try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const flash = (message: string) => {
    setSaved(message);
    window.setTimeout(() => setSaved(null), 2500);
  };

  const byDay = useMemo(() => {
    const grouped = new Map<number, CounselorSchedule[]>();
    for (const schedule of schedules) {
      const list = grouped.get(schedule.day_of_week) ?? [];
      list.push(schedule);
      grouped.set(schedule.day_of_week, list);
    }
    for (const list of grouped.values()) {
      list.sort((a, b) => a.start_time.localeCompare(b.start_time));
    }
    return grouped;
  }, [schedules]);

  const addInterval = async (day: DayOfWeek) => {
    if (newStart === newEnd) {
      setError('Start and end cannot be the same time.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await createSchedule({
        day_of_week: day,
        start_time: `${newStart}:00`,
        end_time: `${newEnd}:00`,
      });
      setSchedules((prev) => [...prev, created]);
      setAddingDay(null);
      flash('Schedule added');
    } catch {
      setError('Could not add that interval. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const toggleActive = async (schedule: CounselorSchedule) => {
    setBusy(true);
    try {
      const updated = await updateSchedule(schedule.schedule_id, {
        is_active: !schedule.is_active,
      });
      setSchedules((prev) =>
        prev.map((s) => (s.schedule_id === updated.schedule_id ? updated : s)),
      );
    } catch {
      setError('Could not update that interval.');
    } finally {
      setBusy(false);
    }
  };

  const removeInterval = async (scheduleId: string) => {
    setBusy(true);
    try {
      await deleteSchedule(scheduleId);
      setSchedules((prev) => prev.filter((s) => s.schedule_id !== scheduleId));
      flash('Schedule removed');
    } catch {
      setError('Could not remove that interval.');
    } finally {
      setBusy(false);
    }
  };

  const saveSettings = async (patch: Partial<SessionSettings>) => {
    setBusy(true);
    setError(null);
    try {
      const updated = await updateSessionSettings(patch);
      setSettings(updated);
      setTimezone(updated.timezone);
      flash('Settings saved');
    } catch {
      setError('Could not save those settings.');
    } finally {
      setBusy(false);
    }
  };

  const addException = async () => {
    if (!offDate) return;
    if (offIsExtra && offAllDay) {
      setError('Extra availability needs a start and end time.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await createException({
        exception_date: offDate,
        start_time: offAllDay && !offIsExtra ? null : `${offStart}:00`,
        end_time: offAllDay && !offIsExtra ? null : `${offEnd}:00`,
        is_available: offIsExtra,
        reason: offReason.trim() || null,
      });
      setExceptions((prev) =>
        [...prev, created].sort((a, b) => a.exception_date.localeCompare(b.exception_date)),
      );
      setShowTimeOff(false);
      setOffDate('');
      setOffReason('');
      flash(offIsExtra ? 'Extra availability added' : 'Time off added');
    } catch {
      setError('Could not save that. Check the date and times.');
    } finally {
      setBusy(false);
    }
  };

  const removeException = async (exceptionId: string) => {
    setBusy(true);
    try {
      await deleteException(exceptionId);
      setExceptions((prev) => prev.filter((e) => e.exception_id !== exceptionId));
    } catch {
      setError('Could not remove that exception.');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
        <div className="flex items-center justify-center py-10 gap-2 text-muted-foreground">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm">Loading your availability…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {saved && (
        <div className="flex items-center gap-2 p-3 bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm rounded-lg">
          <Check className="w-4 h-4" />
          {saved}
        </div>
      )}

      {/* ── Weekly schedule ─────────────────────────────────────────── */}
      <section className="bg-card border border-border rounded-xl p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4 mb-1">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Clock className="w-5 h-5 text-primary" /> My Availability
          </h2>
          <span className="text-xs text-muted-foreground text-right">
            Times shown in
            <br />
            <span className="font-medium text-foreground">{timezone}</span>
          </span>
        </div>
        <p className="text-sm text-muted-foreground mb-5">
          Students book inside these hours. Kio creates the individual slots for you.
        </p>

        <div className="space-y-2">
          {DAY_NAMES.map((dayName, index) => {
            const day = index as DayOfWeek;
            const intervals = byDay.get(day) ?? [];
            return (
              <div
                key={dayName}
                className="flex flex-wrap items-center gap-3 py-2.5 border-b border-border last:border-0"
              >
                <span className="w-24 text-sm font-medium shrink-0">{dayName}</span>

                <div className="flex flex-wrap items-center gap-2 flex-1 min-w-0">
                  {intervals.length === 0 && addingDay !== day && (
                    <span className="text-sm text-muted-foreground">Not working</span>
                  )}

                  {intervals.map((interval) => (
                    <span
                      key={interval.schedule_id}
                      className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm ${
                        interval.is_active
                          ? 'bg-muted border-border'
                          : 'bg-transparent border-dashed border-border text-muted-foreground line-through'
                      }`}
                    >
                      {formatTime(interval.start_time)} – {formatTime(interval.end_time)}
                      {interval.crosses_midnight && (
                        <span
                          className="inline-flex items-center gap-1 text-xs text-secondary"
                          title="This interval runs past midnight into the next day"
                        >
                          <Moon className="w-3 h-3" />
                          next day
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={() => toggleActive(interval)}
                        disabled={busy}
                        className="text-xs text-muted-foreground hover:text-foreground"
                        title={interval.is_active ? 'Disable' : 'Enable'}
                      >
                        {interval.is_active ? 'Disable' : 'Enable'}
                      </button>
                      <button
                        type="button"
                        onClick={() => removeInterval(interval.schedule_id)}
                        disabled={busy}
                        className="text-muted-foreground hover:text-red-600"
                        title="Remove"
                        aria-label={`Remove ${dayName} ${formatTime(interval.start_time)}`}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </span>
                  ))}

                  {addingDay === day ? (
                    <span className="inline-flex flex-wrap items-center gap-2">
                      <input
                        type="time"
                        value={newStart}
                        onChange={(e) => setNewStart(e.target.value)}
                        aria-label="Start time"
                        className="px-2 py-1.5 border border-border rounded-lg text-sm bg-input-background"
                      />
                      <span className="text-muted-foreground text-sm">to</span>
                      <input
                        type="time"
                        value={newEnd}
                        onChange={(e) => setNewEnd(e.target.value)}
                        aria-label="End time"
                        className="px-2 py-1.5 border border-border rounded-lg text-sm bg-input-background"
                      />
                      <button
                        type="button"
                        onClick={() => addInterval(day)}
                        disabled={busy}
                        className="px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-50"
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        onClick={() => setAddingDay(null)}
                        className="px-2 py-1.5 text-sm text-muted-foreground hover:text-foreground"
                      >
                        Cancel
                      </button>
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        setAddingDay(day);
                        setError(null);
                      }}
                      className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-sm text-primary hover:bg-muted transition"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Add
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <p className="text-xs text-muted-foreground mt-4">
          An end time earlier than the start means the interval runs past midnight — 5:00 PM
          to 1:00 AM is that evening through 1am the next day.
        </p>
      </section>

      {/* ── Session settings ────────────────────────────────────────── */}
      {settings && (
        <section className="bg-card border border-border rounded-xl p-6 shadow-sm">
          <h2 className="text-lg font-semibold mb-1 flex items-center gap-2">
            <Settings2 className="w-5 h-5 text-primary" /> Session settings
          </h2>
          <p className="text-sm text-muted-foreground mb-5">
            How your working hours are divided into bookable slots.
          </p>

          <div className="flex flex-wrap gap-5">
            <label className="block">
              <span className="text-xs font-medium text-muted-foreground block mb-1">
                Session duration
              </span>
              <select
                value={settings.session_duration_minutes}
                disabled={busy}
                onChange={(e) =>
                  saveSettings({ session_duration_minutes: Number(e.target.value) })
                }
                className="px-3 py-2 border border-border rounded-lg text-sm bg-input-background"
              >
                {DURATIONS.map((d) => (
                  <option key={d} value={d}>
                    {d} min
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="text-xs font-medium text-muted-foreground block mb-1">
                Buffer between sessions
              </span>
              <select
                value={settings.buffer_minutes}
                disabled={busy}
                onChange={(e) => saveSettings({ buffer_minutes: Number(e.target.value) })}
                className="px-3 py-2 border border-border rounded-lg text-sm bg-input-background"
              >
                {BUFFERS.map((b) => (
                  <option key={b} value={b}>
                    {b === 0 ? 'None' : `${b} min`}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="text-xs font-medium text-muted-foreground block mb-1">
                Timezone
              </span>
              <select
                value={settings.timezone}
                disabled={busy}
                onChange={(e) => saveSettings({ timezone: e.target.value })}
                className="px-3 py-2 border border-border rounded-lg text-sm bg-input-background"
              >
                {[...new Set([settings.timezone, ...TIMEZONES])].map((tz) => (
                  <option key={tz} value={tz}>
                    {tz}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <p className="text-xs text-muted-foreground mt-4">
            Your hours are interpreted in this timezone, not the server's or a student's.
          </p>
        </section>
      )}

      {/* ── Exceptions ──────────────────────────────────────────────── */}
      <section className="bg-card border border-border rounded-xl p-6 shadow-sm">
        <div className="flex items-center justify-between gap-4 mb-1">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <CalendarOff className="w-5 h-5 text-primary" /> Time off &amp; extra hours
          </h2>
          {!showTimeOff && (
            <button
              type="button"
              onClick={() => {
                setShowTimeOff(true);
                setOffDate(toLocalDateString(new Date()));
                setError(null);
              }}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition"
            >
              <CalendarPlus className="w-4 h-4" />
              Add
            </button>
          )}
        </div>
        <p className="text-sm text-muted-foreground mb-5">
          Overrides your weekly pattern for one date. Sessions already booked are not
          cancelled by adding time off — cancel those from Sessions.
        </p>

        {showTimeOff && (
          <div className="mb-5 p-4 rounded-lg border border-border bg-muted/40 space-y-3">
            <div className="flex flex-wrap items-end gap-3">
              <label className="block">
                <span className="text-xs font-medium text-muted-foreground block mb-1">Date</span>
                <input
                  type="date"
                  value={offDate}
                  min={toLocalDateString(new Date())}
                  onChange={(e) => setOffDate(e.target.value)}
                  className="px-3 py-2 border border-border rounded-lg text-sm bg-input-background"
                />
              </label>

              <label className="block">
                <span className="text-xs font-medium text-muted-foreground block mb-1">Type</span>
                <select
                  value={offIsExtra ? 'extra' : 'off'}
                  onChange={(e) => {
                    const extra = e.target.value === 'extra';
                    setOffIsExtra(extra);
                    if (extra) setOffAllDay(false);
                  }}
                  className="px-3 py-2 border border-border rounded-lg text-sm bg-input-background"
                >
                  <option value="off">Time off</option>
                  <option value="extra">Extra availability</option>
                </select>
              </label>

              {!offIsExtra && (
                <label className="flex items-center gap-2 pb-2.5 text-sm">
                  <input
                    type="checkbox"
                    checked={offAllDay}
                    onChange={(e) => setOffAllDay(e.target.checked)}
                    className="rounded border-border"
                  />
                  All day
                </label>
              )}

              {(!offAllDay || offIsExtra) && (
                <>
                  <label className="block">
                    <span className="text-xs font-medium text-muted-foreground block mb-1">
                      From
                    </span>
                    <input
                      type="time"
                      value={offStart}
                      onChange={(e) => setOffStart(e.target.value)}
                      className="px-3 py-2 border border-border rounded-lg text-sm bg-input-background"
                    />
                  </label>
                  <label className="block">
                    <span className="text-xs font-medium text-muted-foreground block mb-1">To</span>
                    <input
                      type="time"
                      value={offEnd}
                      onChange={(e) => setOffEnd(e.target.value)}
                      className="px-3 py-2 border border-border rounded-lg text-sm bg-input-background"
                    />
                  </label>
                </>
              )}
            </div>

            <div className="flex flex-wrap items-end gap-3">
              <label className="block flex-1 min-w-[200px]">
                <span className="text-xs font-medium text-muted-foreground block mb-1">
                  Reason (optional)
                </span>
                <input
                  type="text"
                  value={offReason}
                  maxLength={200}
                  placeholder="Leave, training, appointment…"
                  onChange={(e) => setOffReason(e.target.value)}
                  className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-input-background"
                />
              </label>
              <button
                type="button"
                onClick={addException}
                disabled={busy || !offDate}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-primary/90 transition"
              >
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save'}
              </button>
              <button
                type="button"
                onClick={() => setShowTimeOff(false)}
                className="px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {exceptions.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No upcoming time off. Your weekly schedule applies as-is.
          </p>
        ) : (
          <ul className="space-y-2">
            {exceptions.map((exception) => (
              <li
                key={exception.exception_id}
                className="flex flex-wrap items-center gap-3 px-3 py-2.5 rounded-lg border border-border bg-muted/40 text-sm"
              >
                <span
                  className={`px-2 py-0.5 rounded text-xs font-medium ${
                    exception.is_available
                      ? 'bg-accent/15 text-accent-foreground'
                      : 'bg-amber-100 text-amber-800'
                  }`}
                >
                  {exception.is_available ? 'Extra hours' : 'Time off'}
                </span>
                <span className="font-medium">
                  {new Date(`${exception.exception_date}T00:00:00`).toLocaleDateString(undefined, {
                    weekday: 'short',
                    day: 'numeric',
                    month: 'short',
                    year: 'numeric',
                  })}
                </span>
                <span className="text-muted-foreground">
                  {exception.start_time && exception.end_time
                    ? `${formatTime(exception.start_time)} – ${formatTime(exception.end_time)}`
                    : 'All day'}
                </span>
                {exception.reason && (
                  <span className="text-muted-foreground italic truncate">
                    {exception.reason}
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => removeException(exception.exception_id)}
                  disabled={busy}
                  className="ml-auto text-muted-foreground hover:text-red-600"
                  title="Remove"
                  aria-label="Remove exception"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
