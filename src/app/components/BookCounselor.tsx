/**
 * Book a counseling session — time-first.
 *
 * The old page was counselor-first: pick a person, then hope they had made a
 * slot by hand. Someone who needs to talk on Thursday evening does not have a
 * counselor in mind; they have a time. So the flow is date → time → whoever is
 * actually free, with "any counselor" as a first-class answer.
 *
 * One component serves students and parents. The steps are identical and the
 * backend runs one booking path for both, so forking here would mean two
 * places for the same bug to live. Parents get one extra step: which child.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertCircle,
  ArrowLeft,
  Calendar,
  CalendarX,
  Check,
  ChevronLeft,
  Clock,
  Loader2,
  RefreshCw,
  User,
  Users,
} from 'lucide-react';
import { KioLogo } from './KioLogo';
import api from '../../lib/api';
import { useAuth } from '../../lib/auth-context';
import {
  TIME_WINDOWS,
  bookSlot,
  groupByCounselor,
  searchAvailability,
  toLocalDateString,
  toUtcWindow,
  viewerTimeZone,
} from '../../lib/availability-api';
import type {
  AvailableSlot,
  BookResponse,
  LinkedChildResponse,
} from '../../lib/types';

type TimeChoice = { id: string; startHour: number; endHour: number; label: string };

/** Today, tomorrow, and the rest of this week — the dates people actually pick. */
function quickDates(): { date: Date; label: string; sublabel: string }[] {
  const out: { date: Date; label: string; sublabel: string }[] = [];
  for (let offset = 0; offset < 7; offset += 1) {
    const date = new Date();
    date.setDate(date.getDate() + offset);
    date.setHours(0, 0, 0, 0);
    out.push({
      date,
      label: offset === 0 ? 'Today' : offset === 1 ? 'Tomorrow' : date.toLocaleDateString(undefined, { weekday: 'short' }),
      sublabel: date.toLocaleDateString(undefined, { day: 'numeric', month: 'short' }),
    });
  }
  return out;
}

export function BookCounselor() {
  const { user } = useAuth();
  const isParent = user?.role === 'parent';
  const timezone = useMemo(() => viewerTimeZone(), []);
  const dates = useMemo(() => quickDates(), []);

  const [children, setChildren] = useState<LinkedChildResponse[]>([]);
  const [childId, setChildId] = useState<string | null>(null);

  const [day, setDay] = useState<Date>(dates[0].date);
  const [customDate, setCustomDate] = useState('');
  const [timeChoice, setTimeChoice] = useState<TimeChoice | null>(null);
  const [customStart, setCustomStart] = useState('18:00');
  const [customEnd, setCustomEnd] = useState('20:00');

  const [slots, setSlots] = useState<AvailableSlot[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState<AvailableSlot | null>(null);
  const [booking, setBooking] = useState(false);
  const [confirmation, setConfirmation] = useState<BookResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);

  // Parents book on behalf of a linked child, so they must pick one first.
  useEffect(() => {
    if (!isParent) return;
    let cancelled = false;
    api
      .get<{ children: LinkedChildResponse[] }>('/linking/children')
      .then(({ data }) => {
        if (cancelled) return;
        setChildren(data.children);
        // Skip the picker entirely when there is only one child.
        if (data.children.length === 1) setChildId(data.children[0].student_id);
      })
      .catch(() => {
        if (!cancelled) setChildren([]);
      });
    return () => {
      cancelled = true;
    };
  }, [isParent]);

  const runSearch = useCallback(
    async (choice: TimeChoice, forDay: Date) => {
      setSearching(true);
      setError(null);
      setSelected(null);
      // Deliberately does NOT clear `conflict`: losing a race re-runs this
      // search, and clearing here would wipe the explanation on the way past,
      // leaving the slot to vanish for no stated reason. Picking a new date or
      // time clears it instead, because by then it no longer applies.
      try {
        const window = toUtcWindow(forDay, choice.startHour, choice.endHour);
        const result = await searchAvailability(window);
        setSlots(result.slots);
      } catch {
        setSlots(null);
        setError('Something went wrong. Please try again.');
      } finally {
        setSearching(false);
      }
    },
    [],
  );

  const chooseTime = (choice: TimeChoice) => {
    setConflict(false);
    setTimeChoice(choice);
    runSearch(choice, day);
  };

  const chooseDay = (next: Date) => {
    setConflict(false);
    setDay(next);
    setSlots(null);
    setSelected(null);
    if (timeChoice) runSearch(timeChoice, next);
  };

  const confirmBooking = async () => {
    if (!selected) return;
    if (isParent && !childId) {
      setError('Please choose which child this session is for.');
      return;
    }
    setBooking(true);
    setError(null);
    setConflict(false);
    try {
      const result = await bookSlot(selected, isParent ? childId ?? undefined : undefined);
      setConfirmation(result);
    } catch (err) {
      const status = (err as { response?: { status?: number } }).response?.status;
      if (status === 409) {
        // Somebody else took it between the search and the click. Re-run the
        // search so the next thing they see is real, not the stale list.
        setConflict(true);
        setSelected(null);
        if (timeChoice) runSearch(timeChoice, day);
      } else {
        setError('Something went wrong. Please try again.');
      }
    } finally {
      setBooking(false);
    }
  };

  const grouped = useMemo(() => (slots ? groupByCounselor(slots) : []), [slots]);
  const earliest = slots && slots.length > 0 ? slots[0] : null;

  // ── Success ────────────────────────────────────────────────────────
  if (confirmation) {
    const when = new Date(confirmation.scheduled_at);
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="max-w-2xl mx-auto px-4 py-16">
          <div className="bg-card border border-border rounded-xl p-8 text-center shadow-sm">
            <div className="w-14 h-14 rounded-full bg-accent/15 flex items-center justify-center mx-auto mb-4">
              <Check className="w-7 h-7 text-accent" />
            </div>
            <h1 className="text-xl font-semibold mb-2">Session booked</h1>
            <p className="text-muted-foreground mb-6">
              You&apos;re all set. We&apos;ve let {confirmation.counselor_name} know.
            </p>

            <div className="rounded-lg border border-border bg-muted/40 p-4 text-left space-y-2 mb-6">
              <Row label="Counselor" value={confirmation.counselor_name} />
              <Row
                label="Date"
                value={when.toLocaleDateString(undefined, {
                  weekday: 'long',
                  day: 'numeric',
                  month: 'long',
                })}
              />
              <Row
                label="Time"
                value={when.toLocaleTimeString(undefined, {
                  hour: 'numeric',
                  minute: '2-digit',
                })}
              />
            </div>

            <div className="flex flex-wrap gap-3 justify-center">
              <Link
                to={isParent ? '/parent' : '/student'}
                className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition"
              >
                Back to dashboard
              </Link>
              <button
                type="button"
                onClick={() => {
                  setConfirmation(null);
                  setSlots(null);
                  setTimeChoice(null);
                }}
                className="px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-muted transition"
              >
                Book another
              </button>
            </div>
          </div>
        </main>
      </div>
    );
  }

  // ── Confirmation step ──────────────────────────────────────────────
  if (selected) {
    const start = new Date(selected.start);
    const end = new Date(selected.end);
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="max-w-2xl mx-auto px-4 py-10">
          <button
            type="button"
            onClick={() => setSelected(null)}
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-4"
          >
            <ChevronLeft className="w-4 h-4" />
            Back to times
          </button>

          <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
            <h1 className="text-lg font-semibold mb-1">Confirm your session</h1>
            <p className="text-sm text-muted-foreground mb-6">
              Nothing is booked until you confirm.
            </p>

            <div className="rounded-lg border border-border bg-muted/40 p-4 space-y-2 mb-6">
              <Row label="Counselor" value={selected.counselor_name} />
              <Row
                label="Date"
                value={start.toLocaleDateString(undefined, {
                  weekday: 'long',
                  day: 'numeric',
                  month: 'long',
                })}
              />
              <Row
                label="Time"
                value={`${start.toLocaleTimeString(undefined, {
                  hour: 'numeric',
                  minute: '2-digit',
                })} – ${end.toLocaleTimeString(undefined, {
                  hour: 'numeric',
                  minute: '2-digit',
                })}`}
              />
              <Row label="Duration" value={`${selected.duration_minutes} minutes`} />
              {isParent && childId && (
                <Row
                  label="For"
                  value={
                    childName(children.find((c) => c.student_id === childId)) ?? 'Your child'
                  }
                />
              )}
            </div>

            {error && (
              <div className="flex items-start gap-2 p-3 mb-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">
                <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="button"
              onClick={confirmBooking}
              disabled={booking}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-primary text-primary-foreground font-medium disabled:opacity-50 hover:bg-primary/90 transition"
            >
              {booking ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              {booking ? 'Booking…' : 'Confirm booking'}
            </button>
          </div>
        </main>
      </div>
    );
  }

  // ── Search steps ───────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="max-w-3xl mx-auto px-4 py-10 space-y-6">
        <div>
          <h1 className="text-2xl font-semibold mb-1">Book a counseling session</h1>
          <p className="text-muted-foreground text-sm">
            Tell us when suits you and we&apos;ll show who&apos;s free. Times are in {timezone}.
          </p>
        </div>

        {isParent && children.length > 1 && (
          <Card>
            <StepTitle icon={<Users className="w-4 h-4" />} step="1" title="Who is this for?" />
            <div className="flex flex-wrap gap-2">
              {children.map((child) => (
                <button
                  key={child.student_id}
                  type="button"
                  onClick={() => setChildId(child.student_id)}
                  className={`px-4 py-2 rounded-lg border text-sm transition ${
                    childId === child.student_id
                      ? 'border-primary bg-primary/5 text-primary font-medium'
                      : 'border-border hover:bg-muted'
                  }`}
                >
                  {childName(child)}
                </button>
              ))}
            </div>
          </Card>
        )}

        {isParent && children.length === 0 && (
          <Card>
            <p className="text-sm text-muted-foreground">
              No linked children yet. Link your child&apos;s account before booking a session.
            </p>
          </Card>
        )}

        <Card>
          <StepTitle
            icon={<Calendar className="w-4 h-4" />}
            step={isParent && children.length > 1 ? '2' : '1'}
            title="Choose a date"
          />
          <div className="flex flex-wrap gap-2">
            {dates.map(({ date, label, sublabel }) => {
              const active = toLocalDateString(date) === toLocalDateString(day);
              return (
                <button
                  key={label + sublabel}
                  type="button"
                  onClick={() => chooseDay(date)}
                  className={`px-4 py-2.5 rounded-lg border text-sm text-left transition ${
                    active
                      ? 'border-primary bg-primary/5 text-primary'
                      : 'border-border hover:bg-muted'
                  }`}
                >
                  <span className="block font-medium">{label}</span>
                  <span className="block text-xs text-muted-foreground">{sublabel}</span>
                </button>
              );
            })}
            <label className="px-3 py-2 rounded-lg border border-dashed border-border text-sm">
              <span className="block text-xs text-muted-foreground mb-0.5">Another date</span>
              <input
                type="date"
                value={customDate}
                min={toLocalDateString(new Date())}
                onChange={(e) => {
                  setCustomDate(e.target.value);
                  if (e.target.value) chooseDay(new Date(`${e.target.value}T00:00:00`));
                }}
                className="bg-transparent text-sm outline-none"
              />
            </label>
          </div>
        </Card>

        <Card>
          <StepTitle
            icon={<Clock className="w-4 h-4" />}
            step={isParent && children.length > 1 ? '3' : '2'}
            title="Choose a time"
          />
          <div className="flex flex-wrap gap-2 mb-4">
            {TIME_WINDOWS.map((window) => (
              <button
                key={window.id}
                type="button"
                onClick={() =>
                  chooseTime({
                    id: window.id,
                    startHour: window.startHour,
                    endHour: window.endHour,
                    label: window.label,
                  })
                }
                className={`px-4 py-2.5 rounded-lg border text-sm text-left transition ${
                  timeChoice?.id === window.id
                    ? 'border-primary bg-primary/5 text-primary'
                    : 'border-border hover:bg-muted'
                }`}
              >
                <span className="block font-medium">{window.label}</span>
                <span className="block text-xs text-muted-foreground">{window.sublabel}</span>
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-end gap-2 pt-3 border-t border-border">
            <span className="text-xs text-muted-foreground w-full">Or a specific window</span>
            <input
              type="time"
              value={customStart}
              aria-label="Window start"
              onChange={(e) => setCustomStart(e.target.value)}
              className="px-3 py-2 border border-border rounded-lg text-sm bg-input-background"
            />
            <span className="text-muted-foreground text-sm pb-2">to</span>
            <input
              type="time"
              value={customEnd}
              aria-label="Window end"
              onChange={(e) => setCustomEnd(e.target.value)}
              className="px-3 py-2 border border-border rounded-lg text-sm bg-input-background"
            />
            <button
              type="button"
              onClick={() =>
                chooseTime({
                  id: 'custom',
                  startHour: Number(customStart.split(':')[0]),
                  endHour: Number(customEnd.split(':')[0]),
                  label: 'Custom',
                })
              }
              className="px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-muted transition"
            >
              Search
            </button>
          </div>
        </Card>

        {/* Results */}
        {conflict && (
          <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded-lg">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>That slot was just booked. Here are the next available options.</span>
          </div>
        )}

        {error && !selected && (
          <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {searching && (
          <Card>
            <div className="flex items-center justify-center gap-2 py-8 text-muted-foreground">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span className="text-sm">Finding available counselors…</span>
            </div>
          </Card>
        )}

        {!searching && slots !== null && slots.length === 0 && (
          <Card>
            <div className="text-center py-8">
              <CalendarX className="w-8 h-8 text-muted-foreground mx-auto mb-3" />
              <p className="font-medium mb-1">No counselors are available during this time.</p>
              <p className="text-sm text-muted-foreground mb-4">
                Try another time or a different day.
              </p>
              <button
                type="button"
                onClick={() => {
                  setSlots(null);
                  setTimeChoice(null);
                }}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-muted transition"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Try another time
              </button>
            </div>
          </Card>
        )}

        {!searching && slots !== null && slots.length > 0 && (
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <h2 className="font-semibold">
                {slots.length} slot{slots.length === 1 ? '' : 's'} available
              </h2>
              {earliest && (
                <button
                  type="button"
                  onClick={() => setSelected(earliest)}
                  className="text-sm font-medium text-primary hover:underline"
                >
                  Earliest: {earliest.display_start} with {earliest.counselor_name}
                </button>
              )}
            </div>

            <div className="space-y-4">
              {grouped.map((group) => (
                <div key={group.counselorId} className="rounded-lg border border-border p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-8 h-8 rounded-full bg-secondary/15 flex items-center justify-center">
                      <User className="w-4 h-4 text-secondary" />
                    </div>
                    <div>
                      <p className="font-medium text-sm">{group.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {group.slots.length} time{group.slots.length === 1 ? '' : 's'} free ·{' '}
                        {group.slots[0].duration_minutes} min sessions
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {group.slots.map((slot) => (
                      <button
                        key={`${slot.counselor_id}-${slot.start}`}
                        type="button"
                        onClick={() => setSelected(slot)}
                        className="px-3 py-1.5 rounded-lg border border-border text-sm hover:border-primary hover:bg-primary/5 hover:text-primary transition"
                      >
                        {slot.display_start}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </main>
    </div>
  );
}

function childName(child?: LinkedChildResponse): string | undefined {
  if (!child) return undefined;
  return `${child.first_name} ${child.last_name}`.trim();
}

function Header() {
  return (
    <header className="border-b border-border bg-card">
      <div className="max-w-3xl mx-auto px-4 h-16 flex items-center justify-between">
        <KioLogo className="h-7" />
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </Link>
      </div>
    </header>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <section className="bg-card border border-border rounded-xl p-6 shadow-sm">{children}</section>
  );
}

function StepTitle({
  icon,
  step,
  title,
}: {
  icon: React.ReactNode;
  step: string;
  title: string;
}) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <span className="w-6 h-6 rounded-full bg-primary/10 text-primary text-xs font-semibold flex items-center justify-center">
        {step}
      </span>
      <h2 className="font-semibold flex items-center gap-1.5">
        {icon}
        {title}
      </h2>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-right">{value}</span>
    </div>
  );
}
