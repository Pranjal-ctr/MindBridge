/**
 * Journal — the student's private space, rebuilt against the Figma reference.
 *
 * The API (`POST`/`GET /wellness/journal`) has existed since the wellness
 * module shipped; this page is still its only client. What changed is the
 * surface around it: a hero with Kio in it, an optional mood for the entry, a
 * month strip showing the days written on, prompts for the blank-page problem,
 * and the writing stats the reference puts in the right rail.
 *
 * Three deliberate departures from the reference:
 *
 * 1. **No tags.** The design shows School / Family / Friends chips. The table
 *    has no column for them, so they would be decoration that silently
 *    discards what the student picked. Better absent than fake — when a tags
 *    column exists, the chips are a small addition here.
 * 2. **Mood is optional.** The reference asks for a mood before the writing
 *    box. Mood is already collected by the twice-daily check-in, which is
 *    mandatory; requiring it again would turn writing into a form. It is
 *    offered, stored as `mood_score` when given, and skipped without comment.
 * 3. **The stats are computed from entries, not asserted.** Total comes from
 *    the API's own count. "This month" and the week streak are derived from
 *    the entries actually fetched (the most recent 100 — the API's ceiling),
 *    which for a journal of this kind is all of them; a student past that
 *    point sees a streak measured over their recent history, never a number
 *    that was made up.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Flame,
  Heart,
  Leaf,
  Loader2,
  Lock,
  NotebookPen,
  PenLine,
  Sparkles,
  Sun,
  Target,
} from 'lucide-react';
import { StudentLayout } from './StudentLayout';
import { MoodFace, moodForScore } from './MoodFace';
import { KioMascot } from '../KioMascot';
import { MOOD_META, MOOD_ORDER } from '../../../lib/mood';
import api from '../../../lib/api';
import type { DailyMood, JournalEntryResponse, JournalListResponse } from '../../../lib/types';

/** The API stores 1–10; the five faces are the scale students actually see. */
const MOOD_SCORE: Record<DailyMood, number> = {
  amazing: 9,
  good: 7,
  okay: 5,
  low: 3,
  very_difficult: 1,
};

const PROMPTS = [
  { title: 'My day', text: 'What happened today?', Icon: Sun, tint: 'text-amber-600 bg-amber-50' },
  { title: 'On my mind', text: 'What’s been on your mind lately?', Icon: Heart, tint: 'text-pink-600 bg-pink-50' },
  { title: 'Gratitude', text: 'What are you grateful for today?', Icon: Leaf, tint: 'text-teal-600 bg-teal-50' },
  { title: 'Looking ahead', text: 'What do you want for the coming week?', Icon: Target, tint: 'text-secondary bg-secondary/10' },
] as const;

const MAX_CHARS = 2000;

function entryDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });
}

function entryTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

/** Local YYYY-MM-DD. Not `toISOString()`, which would shift the day by the UTC offset. */
function dayKey(date: Date): string {
  const m = `${date.getMonth() + 1}`.padStart(2, '0');
  const d = `${date.getDate()}`.padStart(2, '0');
  return `${date.getFullYear()}-${m}-${d}`;
}

/** Monday-based index, matching the calendar header. */
function mondayIndex(date: Date): number {
  return (date.getDay() + 6) % 7;
}

/** The Monday of the week a date falls in, at midnight. */
function weekStart(date: Date): Date {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  d.setDate(d.getDate() - mondayIndex(d));
  return d;
}

/**
 * Consecutive weeks with at least one entry, counting back from this week.
 *
 * A gap ends the streak. This week counts only if something was written in it,
 * so the number never claims a week that has not happened yet.
 */
function weekStreak(entries: JournalEntryResponse[]): number {
  if (entries.length === 0) return 0;
  const weeks = new Set(entries.map((e) => dayKey(weekStart(new Date(e.created_at)))));
  let streak = 0;
  const cursor = weekStart(new Date());
  while (weeks.has(dayKey(cursor))) {
    streak += 1;
    cursor.setDate(cursor.getDate() - 7);
  }
  return streak;
}

export function StudentJournal() {
  const [entries, setEntries] = useState<JournalEntryResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [mood, setMood] = useState<DailyMood | null>(null);
  const [activePrompt, setActivePrompt] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [justSaved, setJustSaved] = useState(false);

  const [expanded, setExpanded] = useState<string | null>(null);
  const [monthCursor, setMonthCursor] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  const fetchEntries = useCallback(async () => {
    setIsLoading(true);
    try {
      // 100 is the endpoint's ceiling. The month strip and the stats below are
      // derived from what this returns, so asking for the maximum keeps them
      // right for every realistic history.
      const { data } = await api.get<JournalListResponse>('/wellness/journal', {
        params: { page: 1, page_size: 100 },
      });
      setEntries(data.entries);
      setTotal(data.total);
      setLoadError(false);
    } catch {
      setLoadError(true);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  const handleSave = async () => {
    const text = content.trim();
    if (!text || isSaving) return;

    setIsSaving(true);
    setSaveError(null);
    try {
      const { data } = await api.post<JournalEntryResponse>('/wellness/journal', {
        content: text,
        title: title.trim() || null,
        mood_score: mood ? MOOD_SCORE[mood] : null,
      });
      // Prepend rather than refetch: the entry is already in hand, and the
      // list is newest-first, so a round trip would only add latency to the
      // one moment the student is waiting.
      setEntries((prev) => [data, ...prev]);
      setTotal((prev) => prev + 1);
      setContent('');
      setTitle('');
      setMood(null);
      setActivePrompt(null);
      setJustSaved(true);
      setTimeout(() => setJustSaved(false), 2500);
    } catch {
      // The draft is deliberately left in the box. Losing what someone just
      // wrote because a request failed is the worst thing this screen could do.
      setSaveError('We couldn’t save that just now. Your writing is still here — try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const writtenDays = useMemo(
    () => new Set(entries.map((e) => dayKey(new Date(e.created_at)))),
    [entries],
  );

  const thisMonthCount = useMemo(() => {
    const now = new Date();
    return entries.filter((e) => {
      const d = new Date(e.created_at);
      return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
    }).length;
  }, [entries]);

  const streak = useMemo(() => weekStreak(entries), [entries]);

  return (
    <StudentLayout>
      {/* ── Hero ───────────────────────────────────────────────────── */}
      <section className="mt-4 overflow-hidden rounded-[24px] bg-gradient-to-br from-secondary/[0.12] via-accent/[0.10] to-secondary/[0.06] p-6 sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white/80 text-secondary">
                <NotebookPen className="h-6 w-6" strokeWidth={1.75} aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <h1 className="font-heading text-2xl font-semibold tracking-tight text-primary sm:text-[1.9rem]">
                  My Journal
                </h1>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  A space for your thoughts, feelings and everything in between.
                </p>
              </div>
            </div>

            <div className="mt-5 flex flex-wrap gap-2.5">
              <StatChip Icon={PenLine} value={isLoading ? '—' : `${total}`} label="entries" tone="text-secondary" />
              <StatChip
                Icon={CalendarDays}
                value={isLoading ? '—' : `${thisMonthCount}`}
                label="this month"
                tone="text-teal-600"
              />
              <StatChip Icon={Leaf} value="Keep going" label="Small steps matter" tone="text-amber-600" />
            </div>
          </div>

          <div className="hidden shrink-0 flex-col items-end sm:flex">
            <p
              className="max-w-[10rem] -rotate-2 text-right font-handwritten text-xl leading-snug text-secondary/80"
              aria-hidden="true"
            >
              A safe space
              <br />
              Brighter days ahead ♡
            </p>
            <KioMascot size={104} />
          </div>
        </div>
      </section>

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
        {/* ── Left column ─────────────────────────────────────────── */}
        <div className="space-y-5">
          {/* Write */}
          <section className="rounded-[20px] border border-border/60 bg-card p-5 sm:p-6" aria-labelledby="write-heading">
            <div className="flex items-center gap-2">
              <PenLine className="h-[18px] w-[18px] text-secondary" strokeWidth={1.75} aria-hidden="true" />
              <h2 id="write-heading" className="font-medium text-primary">
                What would you like to write about?
              </h2>
              <span className="ml-auto inline-flex items-center gap-1.5 rounded-lg bg-secondary/10 px-2.5 py-1 text-xs font-medium text-secondary">
                <Lock className="h-3 w-3" strokeWidth={2} aria-hidden="true" />
                Private to you
              </span>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Write freely — your thoughts, your feelings, your day, or anything on your mind.
            </p>

            <label htmlFor="journal-title" className="sr-only">
              Give this entry a title (optional)
            </label>
            <input
              id="journal-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={255}
              placeholder="Give it a title (optional)"
              className="mt-4 w-full border-0 border-b border-border/60 bg-transparent px-0 pb-2 font-heading text-lg text-primary placeholder:font-sans placeholder:text-base placeholder:font-normal placeholder:text-muted-foreground/70 focus:border-secondary/60 focus:outline-none focus:ring-0"
            />

            <label htmlFor="journal-entry" className="sr-only">
              Your entry
            </label>
            <textarea
              id="journal-entry"
              value={content}
              onChange={(e) => setContent(e.target.value.slice(0, MAX_CHARS))}
              rows={7}
              placeholder={activePrompt ?? 'Start writing…'}
              className="mt-3 w-full resize-y border-0 bg-transparent p-0 text-base leading-relaxed placeholder:text-muted-foreground/70 focus:outline-none focus:ring-0"
            />

            {/* Optional mood for this entry. */}
            <fieldset className="mt-3 border-t border-border/50 pt-4">
              <legend className="sr-only">How are you feeling as you write? (optional)</legend>
              <p className="text-xs text-muted-foreground">How are you feeling as you write? (optional)</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {MOOD_ORDER.map((value) => {
                  const active = mood === value;
                  return (
                    <button
                      key={value}
                      type="button"
                      aria-pressed={active}
                      onClick={() => setMood(active ? null : value)}
                      className={`flex items-center gap-2 rounded-full border px-2.5 py-1.5 text-xs transition ${
                        active
                          ? 'border-secondary/40 bg-secondary/[0.07] font-medium text-primary'
                          : 'border-transparent text-muted-foreground hover:bg-muted/60'
                      }`}
                    >
                      <MoodFace mood={value} size={26} selected={active} />
                      {MOOD_META[value].label}
                    </button>
                  );
                })}
              </div>
            </fieldset>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border/50 pt-4">
              <p aria-live="polite" className="text-sm">
                {saveError ? (
                  <span className="text-destructive">{saveError}</span>
                ) : justSaved ? (
                  <span className="text-teal-600">Saved.</span>
                ) : (
                  <span className="text-muted-foreground">
                    There’s no right or wrong way to journal. This is your space.
                  </span>
                )}
              </p>
              <div className="flex items-center gap-3">
                <span className="text-xs text-muted-foreground">
                  {content.length}/{MAX_CHARS}
                </span>
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={!content.trim() || isSaving}
                  className="inline-flex items-center gap-2 rounded-xl bg-secondary px-4 py-2 text-sm font-medium text-white transition hover:bg-secondary/90 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {isSaving && <Loader2 className="h-4 w-4 motion-safe:animate-spin" aria-hidden="true" />}
                  {isSaving ? 'Saving…' : 'Save entry'}
                </button>
              </div>
            </div>
          </section>

          {/* Prompts */}
          <section className="rounded-[20px] border border-border/60 bg-card p-5 sm:p-6" aria-labelledby="prompts-heading">
            <div className="flex items-center gap-2">
              <Sparkles className="h-[18px] w-[18px] text-secondary" strokeWidth={1.75} aria-hidden="true" />
              <h2 id="prompts-heading" className="font-medium text-primary">
                Not sure where to start?
              </h2>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Try a prompt, or write about anything on your mind.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {PROMPTS.map(({ title: promptTitle, text, Icon, tint }) => {
                const active = activePrompt === text;
                return (
                  <button
                    key={promptTitle}
                    type="button"
                    aria-pressed={active}
                    // Prompts only steer the empty page: they set the
                    // placeholder, never the text, so choosing one can't
                    // overwrite something already written.
                    onClick={() => setActivePrompt(active ? null : text)}
                    className={`rounded-2xl border p-4 text-left transition ${
                      active
                        ? 'border-secondary/40 bg-secondary/[0.06]'
                        : 'border-border/60 bg-background hover:border-secondary/30 hover:bg-muted/40'
                    }`}
                  >
                    <span className={`flex h-9 w-9 items-center justify-center rounded-xl ${tint}`}>
                      <Icon className="h-[18px] w-[18px]" strokeWidth={1.75} aria-hidden="true" />
                    </span>
                    <span className="mt-2.5 block text-sm font-medium text-primary">{promptTitle}</span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">{text}</span>
                  </button>
                );
              })}
            </div>
          </section>

          {/* Entries */}
          <section className="rounded-[20px] border border-border/60 bg-card p-5 sm:p-6" aria-labelledby="entries-heading">
            <div className="flex items-center gap-2">
              <NotebookPen className="h-[18px] w-[18px] text-secondary" strokeWidth={1.75} aria-hidden="true" />
              <h2 id="entries-heading" className="font-medium text-primary">
                Earlier entries
              </h2>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Come back to your thoughts whenever you want to.
            </p>

            {isLoading ? (
              <div className="mt-4 space-y-3">
                {[0, 1].map((i) => (
                  <div key={i} className="rounded-2xl border border-border/50 p-4">
                    <div className="h-3 w-40 rounded bg-muted motion-safe:animate-pulse" />
                    <div className="mt-3 h-3 w-full rounded bg-muted motion-safe:animate-pulse" />
                    <div className="mt-2 h-3 w-2/3 rounded bg-muted motion-safe:animate-pulse" />
                  </div>
                ))}
              </div>
            ) : loadError ? (
              <div className="mt-4 rounded-2xl border border-border/60 p-6 text-center">
                <p className="text-sm text-muted-foreground">We couldn’t load your earlier entries.</p>
                <button
                  type="button"
                  onClick={fetchEntries}
                  className="mt-3 rounded-full bg-secondary/10 px-4 py-2 text-sm font-medium text-secondary transition hover:bg-secondary/15"
                >
                  Try again
                </button>
              </div>
            ) : entries.length === 0 ? (
              <div className="mt-4 rounded-2xl border border-dashed border-border p-8 text-center">
                <NotebookPen
                  className="mx-auto h-6 w-6 text-muted-foreground/60"
                  strokeWidth={1.5}
                  aria-hidden="true"
                />
                <p className="mt-3 text-sm text-muted-foreground">
                  Nothing here yet. Whatever you write stays private.
                </p>
              </div>
            ) : (
              <ol className="mt-3 divide-y divide-border/50">
                {entries.map((entry) => {
                  const created = new Date(entry.created_at);
                  const face = moodForScore(entry.mood_score);
                  const isOpen = expanded === entry.journal_id;
                  return (
                    <li key={entry.journal_id} className="py-3.5">
                      <button
                        type="button"
                        onClick={() => setExpanded(isOpen ? null : entry.journal_id)}
                        aria-expanded={isOpen}
                        className="flex w-full items-center gap-4 text-left"
                      >
                        <span className="w-10 shrink-0 text-center" aria-hidden="true">
                          <span className="block text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                            {created.toLocaleDateString(undefined, { month: 'short' })}
                          </span>
                          <span className="block font-heading text-lg font-semibold leading-tight text-primary">
                            {created.getDate()}
                          </span>
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium text-primary">
                            {entry.title || entryDate(entry.created_at)}
                          </span>
                          <span className={`mt-0.5 block text-sm text-muted-foreground ${isOpen ? '' : 'truncate'}`}>
                            {isOpen ? entryTime(entry.created_at) : entry.content}
                          </span>
                        </span>
                        {face && <MoodFace mood={face} size={28} className="shrink-0" />}
                      </button>
                      {isOpen && (
                        <p className="mt-2 whitespace-pre-wrap pl-14 text-sm leading-relaxed text-foreground/90">
                          {entry.content}
                        </p>
                      )}
                    </li>
                  );
                })}
              </ol>
            )}
          </section>
        </div>

        {/* ── Right rail ──────────────────────────────────────────── */}
        <div className="space-y-4">
          <MonthStrip
            cursor={monthCursor}
            onCursorChange={setMonthCursor}
            writtenDays={writtenDays}
          />

          <div className="rounded-[20px] border border-border/60 bg-secondary/[0.06] p-5">
            <Leaf className="h-5 w-5 text-secondary" strokeWidth={1.75} aria-hidden="true" />
            <p className="mt-2 font-handwritten text-2xl leading-tight text-primary">
              “Progress, not perfection.”
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Every thought you write is a step towards a better you.
            </p>
          </div>

          <div className="rounded-[20px] border border-border/60 bg-card p-5">
            <h2 className="text-sm font-medium text-primary">Your journal stats</h2>
            <dl className="mt-3 space-y-3">
              <StatRow Icon={PenLine} tone="text-secondary" value={isLoading ? '—' : total} label="Total entries" />
              <StatRow
                Icon={Leaf}
                tone="text-teal-600"
                value={isLoading ? '—' : thisMonthCount}
                label="This month"
              />
              <StatRow
                Icon={Flame}
                tone="text-amber-600"
                value={isLoading ? '—' : streak}
                label={streak === 1 ? 'Week in a row' : 'Weeks in a row'}
              />
            </dl>
          </div>

          <div className="rounded-[20px] border border-border/60 bg-muted/40 p-5">
            <div className="flex items-center justify-between">
              <Lock className="h-5 w-5 text-secondary" strokeWidth={1.75} aria-hidden="true" />
            </div>
            <p className="mt-2 text-sm font-medium text-primary">Your thoughts are safe here</p>
            {/* Accurate, not reassuring-sounding: the words are never shown to
                anyone else, and the only thing that leaves this page is how
                often you write, which is one small input to the wellness
                score. Claiming more than that would be a lie a student could
                eventually catch us in. */}
            <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
              Only you can read your entries — they aren’t shown to your parents, your school or
              your counselor. Kio counts how often you write as one small part of your wellness
              score; the words themselves stay here.
            </p>
          </div>
        </div>
      </div>
    </StudentLayout>
  );
}

/* ── Small pieces ──────────────────────────────────────────────── */

function StatChip({
  Icon,
  value,
  label,
  tone,
}: {
  Icon: typeof PenLine;
  value: string;
  label: string;
  tone: string;
}) {
  return (
    <div className="flex items-center gap-2.5 rounded-2xl bg-white/80 px-3.5 py-2">
      <Icon className={`h-[18px] w-[18px] ${tone}`} strokeWidth={1.75} aria-hidden="true" />
      <div>
        <div className="text-sm font-semibold text-primary">{value}</div>
        <div className="text-[11px] text-muted-foreground">{label}</div>
      </div>
    </div>
  );
}

function StatRow({
  Icon,
  value,
  label,
  tone,
}: {
  Icon: typeof PenLine;
  value: number | string;
  label: string;
  tone: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted/60">
        <Icon className={`h-[17px] w-[17px] ${tone}`} strokeWidth={1.75} aria-hidden="true" />
      </span>
      <dt className="sr-only">{label}</dt>
      <dd className="flex items-baseline gap-2">
        <span className="font-heading text-lg font-semibold text-primary">{value}</span>
        <span className="text-sm text-muted-foreground">{label}</span>
      </dd>
    </div>
  );
}

/**
 * The month strip — which days were written on.
 *
 * Dots come from the entries already fetched, so moving back through months
 * costs no request. A month with nothing in it simply has no dots.
 */
function MonthStrip({
  cursor,
  onCursorChange,
  writtenDays,
}: {
  cursor: Date;
  onCursorChange: (next: Date) => void;
  writtenDays: Set<string>;
}) {
  const year = cursor.getFullYear();
  const month = cursor.getMonth();
  const todayKey = dayKey(new Date());

  const cells: (Date | null)[] = [];
  const first = new Date(year, month, 1);
  for (let i = 0; i < mondayIndex(first); i += 1) cells.push(null);
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  for (let d = 1; d <= daysInMonth; d += 1) cells.push(new Date(year, month, d));

  const atCurrentMonth = () => {
    const now = new Date();
    return year === now.getFullYear() && month === now.getMonth();
  };

  return (
    <div className="rounded-[20px] border border-border/60 bg-card p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-primary">
          {cursor.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
        </h2>
        <div className="flex gap-1.5">
          <button
            type="button"
            aria-label="Previous month"
            onClick={() => onCursorChange(new Date(year, month - 1, 1))}
            className="flex h-7 w-7 items-center justify-center rounded-lg bg-muted/60 text-secondary transition hover:bg-muted"
          >
            <ChevronLeft className="h-4 w-4" strokeWidth={2} aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-label="Next month"
            disabled={atCurrentMonth()}
            onClick={() => onCursorChange(new Date(year, month + 1, 1))}
            className="flex h-7 w-7 items-center justify-center rounded-lg bg-muted/60 text-secondary transition hover:bg-muted disabled:opacity-40"
          >
            <ChevronRight className="h-4 w-4" strokeWidth={2} aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-7 gap-y-1 text-center">
        {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((d, i) => (
          <span key={i} className="pb-1 text-[10px] font-medium text-muted-foreground">
            {d}
          </span>
        ))}
        {cells.map((date, i) => {
          if (!date) return <span key={`pad-${i}`} />;
          const key = dayKey(date);
          const isToday = key === todayKey;
          const written = writtenDays.has(key);
          return (
            <span key={key} className="relative mx-auto flex h-7 w-7 items-center justify-center">
              <span
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs ${
                  isToday ? 'bg-secondary font-semibold text-white' : 'text-foreground'
                }`}
              >
                {date.getDate()}
              </span>
              {written && !isToday && (
                <span
                  className="absolute bottom-0 h-1 w-1 rounded-full bg-secondary"
                  aria-hidden="true"
                />
              )}
            </span>
          );
        })}
      </div>

      <p className="mt-3 text-[11px] text-muted-foreground">
        <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-secondary align-middle" />
        A day you wrote something
      </p>
    </div>
  );
}
