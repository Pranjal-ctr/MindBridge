/**
 * Growth Profile — what Kio has understood about you, and what you've kept up.
 *
 * Rebuilt against the Figma reference. The reference is a static mock; every
 * number on this page comes from an endpoint:
 *
 *   memories, areas, strengths, reflections   GET /memory/
 *   check-in heatmap and streaks              GET /wellness/mood-calendar
 *   wellness score and trend                  GET /wellness/score
 *
 * Nothing is seeded, estimated, or filled in when a request fails — a section
 * with no data says so and explains what would put something there, because a
 * growth page that invents progress is worse than an empty one.
 *
 * The wellness score lives here rather than on Home: it is a number a student
 * cannot move today, and meeting it every morning reads as a verdict. Here it
 * is something they came looking for.
 *
 * Managing memories (pin, delete) is kept exactly as it was — it is the one
 * piece of real control a student has over what the AI remembers, and the
 * reference's "You're in control" card is a promise this page has to keep.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertCircle,
  Brain,
  ChevronDown,
  GraduationCap,
  Heart,
  Loader2,
  MessageCircle,
  Pin,
  PinOff,
  Sparkles,
  Star,
  Target,
  Trash2,
  TrendingUp,
  Users,
} from 'lucide-react';
import { useAuth } from '../../lib/auth-context';
import { useMemories } from '../../hooks/useMemory';
import { useWellnessScore } from '../../hooks/useWellness';
import api from '../../lib/api';
import type { MemoryItem, MemoryType, MoodCalendarResponse } from '../../lib/types';
import { StudentLayout } from './student/StudentLayout';
import { KioMascot } from './KioMascot';

const MEMORY_TYPE_CONFIG: Record<
  MemoryType,
  { label: string; sub: string; icon: typeof Target; icon_class: string; bar: string }
> = {
  goal: {
    label: 'Goals & Aspirations',
    sub: 'Your dreams and future',
    icon: Target,
    icon_class: 'bg-amber-50 text-amber-600',
    bar: 'bg-amber-400',
  },
  academic: {
    label: 'Academic',
    sub: 'Studies & learning',
    icon: GraduationCap,
    icon_class: 'bg-blue-50 text-blue-600',
    bar: 'bg-blue-400',
  },
  emotion: {
    label: 'Emotional Wellbeing',
    sub: 'Feelings & challenges',
    icon: Heart,
    icon_class: 'bg-rose-50 text-rose-600',
    bar: 'bg-rose-400',
  },
  relationship: {
    label: 'Relationships',
    sub: 'Family & friends',
    icon: Users,
    icon_class: 'bg-violet-50 text-violet-600',
    bar: 'bg-violet-400',
  },
  preference: {
    label: 'Preferences & Habits',
    sub: 'What works for you',
    icon: Star,
    icon_class: 'bg-teal-50 text-teal-600',
    bar: 'bg-teal-400',
  },
  fact: {
    label: 'About You',
    sub: 'Things that make you, you',
    icon: Sparkles,
    icon_class: 'bg-slate-100 text-slate-600',
    bar: 'bg-slate-400',
  },
};

const TYPE_ORDER: MemoryType[] = ['goal', 'academic', 'emotion', 'relationship', 'preference', 'fact'];

/** Local YYYY-MM-DD — never `toISOString()`, which shifts the day by the UTC offset. */
function dayKey(date: Date): string {
  const m = `${date.getMonth() + 1}`.padStart(2, '0');
  const d = `${date.getDate()}`.padStart(2, '0');
  return `${date.getFullYear()}-${m}-${d}`;
}

function monthKey(date: Date): string {
  return `${date.getFullYear()}-${`${date.getMonth() + 1}`.padStart(2, '0')}`;
}

function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/**
 * The 28 days ending today, oldest first, as four Monday-started weeks.
 *
 * Built from dates rather than from whatever the API returned, so a day with
 * no check-in is a visible gap instead of silently closing up.
 */
function heatmapWeeks(checkedIn: Set<string>): { key: string; date: Date; active: boolean }[][] {
  const today = new Date();
  const end = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  // Wind back to the Monday of the current week, then three weeks before that.
  const start = new Date(end);
  start.setDate(start.getDate() - ((end.getDay() + 6) % 7) - 21);

  const weeks: { key: string; date: Date; active: boolean }[][] = [];
  for (let w = 0; w < 4; w += 1) {
    const week: { key: string; date: Date; active: boolean }[] = [];
    for (let d = 0; d < 7; d += 1) {
      const date = new Date(start);
      date.setDate(start.getDate() + w * 7 + d);
      const key = dayKey(date);
      week.push({ key, date, active: checkedIn.has(key) });
    }
    weeks.push(week);
  }
  return weeks;
}

/** Consecutive weeks with at least one check-in, counting back from this week. */
function weekStreak(checkedIn: Set<string>): number {
  const today = new Date();
  const monday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  monday.setDate(monday.getDate() - ((today.getDay() + 6) % 7));

  let streak = 0;
  for (;;) {
    let found = false;
    for (let d = 0; d < 7; d += 1) {
      const day = new Date(monday);
      day.setDate(monday.getDate() + d);
      if (checkedIn.has(dayKey(day))) {
        found = true;
        break;
      }
    }
    if (!found) break;
    streak += 1;
    monday.setDate(monday.getDate() - 7);
  }
  return streak;
}

/** Longest run of consecutive days inside the fetched window. */
function longestDayRun(checkedIn: Set<string>): number {
  const keys = [...checkedIn].sort();
  let best = 0;
  let run = 0;
  let previous: Date | null = null;
  for (const key of keys) {
    const [y, m, d] = key.split('-').map(Number);
    const date = new Date(y, m - 1, d);
    if (previous && (date.getTime() - previous.getTime()) / 86_400_000 === 1) {
      run += 1;
    } else {
      run = 1;
    }
    best = Math.max(best, run);
    previous = date;
  }
  return best;
}

export function StudentGrowthProfile() {
  const { user } = useAuth();
  const { score: wellness } = useWellnessScore();
  const { memories, groupedMemories, isLoading, error, deleteMemory, togglePin } = useMemories();

  const [openArea, setOpenArea] = useState<MemoryType | null>(null);
  const [checkedIn, setCheckedIn] = useState<Set<string> | null>(null);

  // Four weeks can straddle two months, so both are fetched. A failure leaves
  // `checkedIn` null and the section says it could not load rather than
  // rendering an empty grid that looks like four weeks of nothing.
  const fetchCheckins = useCallback(async () => {
    const now = new Date();
    const previous = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    try {
      const responses = await Promise.all(
        [previous, now].map((month) =>
          api.get<MoodCalendarResponse>('/wellness/mood-calendar', {
            params: { month: monthKey(month) },
          }),
        ),
      );
      const days = new Set<string>();
      for (const { data } of responses) {
        for (const day of data.days) {
          if (day.mood || day.mood_score !== null) days.add(day.date.slice(0, 10));
        }
      }
      setCheckedIn(days);
    } catch {
      setCheckedIn(null);
    }
  }, []);

  useEffect(() => {
    fetchCheckins();
  }, [fetchCheckins]);

  const areas = useMemo(
    () =>
      TYPE_ORDER.map((type) => ({
        type,
        ...MEMORY_TYPE_CONFIG[type],
        items: groupedMemories[type] ?? [],
      })),
    [groupedMemories],
  );

  const activeAreas = areas.filter((a) => a.items.length > 0).length;

  /** Strongest themes first — the memory's own importance score, not a guess. */
  const picture = useMemo(
    () =>
      [...memories]
        .filter((m) => m.importance_score !== null)
        .sort((a, b) => (b.importance_score ?? 0) - (a.importance_score ?? 0))
        .slice(0, 5),
    [memories],
  );

  const reflections = useMemo(
    () =>
      [...memories]
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        .slice(0, 5),
    [memories],
  );

  /** Since the first thing Kio remembered — not the account's creation date. */
  const together = useMemo(() => {
    if (memories.length === 0) return null;
    const earliest = memories.reduce(
      (min, m) => (new Date(m.created_at) < new Date(min) ? m.created_at : min),
      memories[0].created_at,
    );
    return new Date(earliest).toLocaleDateString(undefined, { month: 'short', year: 'numeric' });
  }, [memories]);

  const weeks = checkedIn ? heatmapWeeks(checkedIn) : null;
  const recentCheckins = weeks ? weeks.flat().filter((d) => d.active).length : 0;

  return (
    <StudentLayout>
      {/* ── Hero ───────────────────────────────────────────────────── */}
      <section className="mt-4 overflow-hidden rounded-[24px] bg-gradient-to-br from-secondary/[0.12] via-accent/[0.10] to-secondary/[0.06] p-6 sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white/80 text-secondary">
                <TrendingUp className="h-6 w-6" strokeWidth={1.75} aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <h1 className="font-heading text-2xl font-semibold tracking-tight text-primary sm:text-[1.9rem]">
                  My Growth Profile
                </h1>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  {user?.first_name
                    ? `A reflection of what you've shared with Kio, ${user.first_name}.`
                    : "A reflection of what you've shared with Kio over time."}
                </p>
              </div>
            </div>

            <div className="mt-5 flex flex-wrap gap-2.5">
              <HeroStat value={isLoading ? '—' : `${memories.length}`} label="memories" dot="bg-secondary" />
              <HeroStat value={isLoading ? '—' : `${activeAreas}`} label="life areas" dot="bg-teal-500" />
              {together && <HeroStat value={together} label="since" dot="bg-amber-500" />}
              {wellness?.has_data && wellness.overall !== null && (
                <HeroStat
                  value={`${Math.round(wellness.overall)}/100`}
                  label={
                    wellness.trend === 'improving'
                      ? 'wellness, trending up'
                      : wellness.trend === 'declining'
                        ? 'wellness, a heavier stretch'
                        : 'wellness, steady'
                  }
                  dot="bg-primary"
                />
              )}
            </div>
          </div>

          <div className="hidden shrink-0 flex-col items-end sm:flex">
            <p
              className="max-w-[11rem] -rotate-2 text-right font-handwritten text-xl leading-snug text-secondary/80"
              aria-hidden="true"
            >
              A kinder, brighter you
              <br />
              is a work in progress ♡
            </p>
            <KioMascot size={112} />
          </div>
        </div>
      </section>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-7 w-7 animate-spin text-muted-foreground" aria-hidden="true" />
          <span className="sr-only">Loading your growth profile</span>
        </div>
      ) : error ? (
        <div className="mt-6 flex flex-col items-center justify-center rounded-[20px] border border-border/60 bg-card py-16 text-muted-foreground">
          <AlertCircle className="mb-3 h-8 w-8" aria-hidden="true" />
          <p className="text-sm">{error}</p>
        </div>
      ) : memories.length === 0 ? (
        <div className="mt-6 flex flex-col items-center justify-center rounded-[20px] border border-dashed border-border bg-card/50 py-16 text-center">
          <Brain className="h-9 w-9 text-secondary/50" strokeWidth={1.5} aria-hidden="true" />
          <h2 className="mt-4 font-heading text-lg font-semibold text-primary">Nothing here yet</h2>
          <p className="mt-2 max-w-md px-6 text-sm text-muted-foreground">
            As you talk with Comrade, the things that matter to you — your goals, what you find
            hard, who you care about — will collect here. You decide what stays.
          </p>
          <Link
            to="/student/comrade"
            className="mt-6 rounded-xl bg-secondary px-5 py-2.5 text-sm font-medium text-white transition hover:bg-secondary/90"
          >
            Talk to Comrade
          </Link>
        </div>
      ) : (
        <>
          {/* ── Encouragement ───────────────────────────────────────── */}
          <section className="mt-5 flex flex-wrap items-center gap-4 rounded-[20px] border border-border/60 bg-card p-5">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
              <Star className="h-5 w-5" strokeWidth={1.75} aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-medium text-primary">You’re showing up, and that matters</p>
              <p className="mt-0.5 text-sm text-muted-foreground">
                You’ve been open about your thoughts, feelings and goals. Kio remembers what
                matters to you so conversations can pick up where they left off.
              </p>
            </div>
          </section>

          {/* ── Areas ───────────────────────────────────────────────── */}
          <section className="mt-8" aria-labelledby="areas-heading">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="areas-heading" className="font-heading text-lg font-semibold text-primary">
                Areas of your life
              </h2>
              <p className="text-sm text-muted-foreground">Open one to see what’s in it</p>
            </div>

            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {areas.map((area) => {
                const Icon = area.icon;
                const count = area.items.length;
                const pct = memories.length ? Math.round((count / memories.length) * 100) : 0;
                const open = openArea === area.type;
                return (
                  <button
                    key={area.type}
                    type="button"
                    disabled={count === 0}
                    aria-expanded={open}
                    onClick={() => setOpenArea(open ? null : area.type)}
                    className={`rounded-[20px] border p-4 text-left transition ${
                      open
                        ? 'border-secondary/40 bg-secondary/[0.05]'
                        : 'border-border/60 bg-card hover:border-secondary/30'
                    } ${count === 0 ? 'opacity-55' : ''}`}
                  >
                    <span className="flex items-center justify-between">
                      <span className={`flex h-10 w-10 items-center justify-center rounded-xl ${area.icon_class}`}>
                        <Icon className="h-5 w-5" strokeWidth={1.75} aria-hidden="true" />
                      </span>
                      {count > 0 && (
                        <ChevronDown
                          className={`h-4 w-4 text-muted-foreground transition ${open ? 'rotate-180' : ''}`}
                          aria-hidden="true"
                        />
                      )}
                    </span>
                    <span className="mt-3 block text-sm font-medium text-primary">{area.label}</span>
                    <span className="block text-xs text-muted-foreground">{area.sub}</span>
                    <span className="mt-3 block h-1.5 w-full overflow-hidden rounded-full bg-muted">
                      <span
                        className={`block h-full rounded-full ${area.bar}`}
                        style={{ width: `${pct}%` }}
                      />
                    </span>
                    <span className="mt-1.5 flex items-center justify-between text-xs text-muted-foreground">
                      <span>
                        {count} {count === 1 ? 'memory' : 'memories'}
                      </span>
                      <span className="font-medium">{pct}%</span>
                    </span>
                  </button>
                );
              })}
            </div>

            {/* The opened area's memories, with the controls that make the
                "you're in control" promise further down real. */}
            {openArea && (
              <div className="mt-4 space-y-2.5">
                {(groupedMemories[openArea] ?? []).map((memory) => (
                  <MemoryRow
                    key={memory.memory_id}
                    memory={memory}
                    onTogglePin={() => togglePin(memory.memory_id, memory.is_pinned)}
                    onDelete={() => deleteMemory(memory.memory_id)}
                  />
                ))}
              </div>
            )}
          </section>

          {/* ── Check-in activity ───────────────────────────────────── */}
          <section className="mt-8 rounded-[20px] border border-border/60 bg-card p-5 sm:p-6" aria-labelledby="activity-heading">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <h2 id="activity-heading" className="font-heading text-lg font-semibold text-primary">
                Your check-in activity
              </h2>
              {weeks && (
                <div className="flex gap-6">
                  <MiniStat value={recentCheckins} label="in 4 weeks" tone="text-secondary" />
                  <MiniStat value={weekStreak(checkedIn!)} label="week streak" tone="text-teal-600" />
                  <MiniStat value={longestDayRun(checkedIn!)} label="best run" tone="text-amber-600" />
                </div>
              )}
            </div>

            {weeks ? (
              <div className="mt-4">
                {/* Width-capped so the cells stay square. Left to fill the card
                    they stretch into bars, which reads as a progress meter
                    rather than as days. */}
                <div className="max-w-[300px]">
                  <div className="grid grid-cols-7 gap-1.5 text-center">
                    {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((d, i) => (
                      <span key={i} className="text-[10px] font-medium text-muted-foreground">
                        {d}
                      </span>
                    ))}
                  </div>
                  <div className="mt-1.5 space-y-1.5">
                    {weeks.map((week, wi) => (
                      <div key={wi} className="grid grid-cols-7 gap-1.5">
                        {week.map((day) => (
                          <span
                            key={day.key}
                            title={`${day.date.toLocaleDateString(undefined, {
                              weekday: 'short',
                              month: 'short',
                              day: 'numeric',
                            })} — ${day.active ? 'checked in' : 'no check-in'}`}
                            className={`aspect-square rounded-md ${
                              day.active ? 'bg-secondary/70' : 'bg-muted'
                            }`}
                          />
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
                <p className="mt-3 text-xs text-muted-foreground">
                  A filled square is a day you told Kio how you were doing. Gaps are just gaps —
                  they don’t count against you.
                </p>
              </div>
            ) : (
              <p className="mt-4 text-sm text-muted-foreground">
                We couldn’t load your check-in history just now.{' '}
                <button
                  type="button"
                  onClick={fetchCheckins}
                  className="text-secondary underline-offset-2 hover:underline"
                >
                  Try again
                </button>
              </p>
            )}
          </section>

          {/* ── Picture + reflections ───────────────────────────────── */}
          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <section className="rounded-[20px] border border-border/60 bg-card p-5 sm:p-6" aria-labelledby="picture-heading">
              <h2 id="picture-heading" className="font-heading text-lg font-semibold text-primary">
                Your current picture
              </h2>
              <p className="mt-0.5 text-sm text-muted-foreground">
                The themes Kio weighs most from your conversations
              </p>

              {picture.length === 0 ? (
                <p className="mt-4 text-sm text-muted-foreground">
                  Nothing is weighted yet — this fills in as you talk with Comrade.
                </p>
              ) : (
                <ul className="mt-4 space-y-3.5">
                  {picture.map((memory) => {
                    const config = MEMORY_TYPE_CONFIG[memory.memory_type];
                    const Icon = config.icon;
                    const pct = Math.round((memory.importance_score ?? 0) * 100);
                    return (
                      <li key={memory.memory_id}>
                        <div className="flex items-start gap-2.5">
                          <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${config.icon_class}`}>
                            <Icon className="h-[15px] w-[15px]" strokeWidth={1.75} aria-hidden="true" />
                          </span>
                          <span className="min-w-0 flex-1 text-sm leading-snug text-foreground/90">
                            {memory.content}
                          </span>
                          <span className="shrink-0 text-xs font-medium text-muted-foreground">{pct}%</span>
                        </div>
                        <span className="ml-[38px] mt-1.5 block h-1 overflow-hidden rounded-full bg-muted">
                          <span
                            className={`block h-full rounded-full ${config.bar} opacity-70`}
                            style={{ width: `${pct}%` }}
                          />
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}

              <p className="mt-5 rounded-xl bg-muted/50 p-3 text-xs leading-relaxed text-muted-foreground">
                These come from what you’ve chosen to share. The percentage is how much weight Kio
                gives a memory when it replies — you can remove any of them above.
              </p>
            </section>

            <section className="rounded-[20px] border border-border/60 bg-card p-5 sm:p-6" aria-labelledby="reflections-heading">
              <h2 id="reflections-heading" className="font-heading text-lg font-semibold text-primary">
                Recent reflections
              </h2>
              <p className="mt-0.5 text-sm text-muted-foreground">
                Some of the things you’ve talked about lately
              </p>

              <ol className="relative mt-4 space-y-4 border-l border-border/70 pl-5">
                {reflections.map((memory) => {
                  const config = MEMORY_TYPE_CONFIG[memory.memory_type];
                  return (
                    <li key={memory.memory_id} className="relative">
                      <span
                        className={`absolute -left-[26px] top-1.5 h-2.5 w-2.5 rounded-full ring-2 ring-card ${config.bar}`}
                        aria-hidden="true"
                      />
                      <div className="flex items-start justify-between gap-3">
                        <p className="min-w-0 text-sm leading-snug text-foreground/90">{memory.content}</p>
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {shortDate(memory.created_at)}
                        </span>
                      </div>
                      <span className="mt-1.5 inline-block rounded-full bg-muted px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground">
                        {config.label}
                      </span>
                    </li>
                  );
                })}
              </ol>
            </section>
          </div>

          {/* ── Control + sign-off ──────────────────────────────────── */}
          <section className="mt-5 flex flex-wrap items-center gap-4 rounded-[20px] border border-border/60 bg-gradient-to-br from-secondary/[0.08] to-accent/[0.08] p-5">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/80 text-secondary">
              <MessageCircle className="h-5 w-5" strokeWidth={1.75} aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-medium text-primary">You’re in control</p>
              <p className="mt-0.5 text-sm text-muted-foreground">
                Open any area above to pin what you want Kio to keep in mind, or delete anything you
                would rather it forgot. Deleting is immediate and permanent.
              </p>
            </div>
          </section>

          <div className="mt-8 overflow-hidden rounded-[24px] bg-gradient-to-br from-primary to-secondary p-6 sm:p-8">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="font-heading text-lg font-semibold text-white">
                  This is your story, and it’s still being written.
                </p>
                <p className="mt-1 max-w-xl text-sm text-white/75">
                  You’re learning, growing and navigating life — and Kio is here to support you
                  along the way.
                </p>
              </div>
              <p className="font-handwritten text-2xl leading-tight text-white/85" aria-hidden="true">
                Small steps
                <br />
                still count ♡
              </p>
            </div>
          </div>
        </>
      )}
    </StudentLayout>
  );
}

/* ── Small pieces ──────────────────────────────────────────────── */

function HeroStat({ value, label, dot }: { value: string; label: string; dot: string }) {
  return (
    <div className="flex items-center gap-2.5 rounded-2xl bg-white/80 px-3.5 py-2">
      <span className={`h-2 w-2 shrink-0 rounded-full ${dot}`} aria-hidden="true" />
      <div>
        <div className="font-heading text-base font-semibold leading-tight text-primary">{value}</div>
        <div className="text-[11px] text-muted-foreground">{label}</div>
      </div>
    </div>
  );
}

function MiniStat({ value, label, tone }: { value: number; label: string; tone: string }) {
  return (
    <div className="text-center">
      <div className={`font-heading text-base font-semibold ${tone}`}>{value}</div>
      <div className="text-[11px] text-muted-foreground">{label}</div>
    </div>
  );
}

function MemoryRow({
  memory,
  onTogglePin,
  onDelete,
}: {
  memory: MemoryItem;
  onTogglePin: () => void;
  onDelete: () => void;
}) {
  const config = MEMORY_TYPE_CONFIG[memory.memory_type];
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-border/60 bg-card p-4">
      <div className="min-w-0 flex-1">
        <p className="text-sm text-foreground/90">{memory.content}</p>
        <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <span>{shortDate(memory.created_at)}</span>
          {memory.importance_score !== null && (
            <span>{Math.round(memory.importance_score * 100)}% weight</span>
          )}
          {memory.is_pinned && (
            <span className="rounded-full bg-amber-50 px-2 py-0.5 font-medium text-amber-700">Pinned</span>
          )}
          <span className={`rounded-full px-2 py-0.5 ${config.icon_class}`}>{config.label}</span>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <button
          type="button"
          onClick={onTogglePin}
          title={memory.is_pinned ? 'Unpin memory' : 'Pin memory'}
          className={`rounded-lg p-2 transition ${
            memory.is_pinned
              ? 'bg-amber-50 text-amber-700 hover:bg-amber-100'
              : 'text-muted-foreground hover:bg-muted'
          }`}
        >
          {memory.is_pinned ? (
            <PinOff className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Pin className="h-4 w-4" aria-hidden="true" />
          )}
          <span className="sr-only">{memory.is_pinned ? 'Unpin memory' : 'Pin memory'}</span>
        </button>
        <button
          type="button"
          onClick={onDelete}
          title="Delete memory"
          className="rounded-lg p-2 text-muted-foreground transition hover:bg-destructive/10 hover:text-destructive"
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
          <span className="sr-only">Delete memory</span>
        </button>
      </div>
    </div>
  );
}
