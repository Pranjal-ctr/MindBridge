/**
 * Student Home — the calm starting point, not a dashboard.
 *
 * The page answers one question: *how are you doing, and what would you like
 * to do today?* Everything here is arranged around that and nothing else.
 *
 * Two deliberate absences:
 *
 * 1. **No wellness score.** The old `/student` opened with `58/100` in large
 *    type. A number a teenager cannot move today, staring at them every time
 *    they open the app, is a way to feel measured rather than supported — and
 *    on a bad day it reads as a verdict. The score is intact and now lives in
 *    Growth, where someone has gone looking for it. What survives here is at
 *    most one gentle sentence about direction.
 *
 * 2. **No mood collection.** The check-in stays a mandatory step immediately
 *    after login (it needs a reason as well as a mood, and it feeds the
 *    wellness engine and parent insights). By the time Home renders it is
 *    normally done, so this page *reflects* it — today's mood, when it was
 *    recorded, and a quiet way to update it. If the window is somehow still
 *    open, Home offers the same existing modal rather than a second mechanism.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  type LucideIcon,
  MessageCircle,
  NotebookPen,
  Sparkles,
  UserRound,
} from 'lucide-react';
import { KioMascot } from '../KioMascot';
import { StudentLayout } from './StudentLayout';
import { DailyCheckinModal } from '../DailyCheckinModal';
import { MoodCalendarModal } from '../MoodCalendarModal';
import { useAuth } from '../../../lib/auth-context';
import { useConversations } from '../../../hooks/useConversations';
import { useWellnessScore } from '../../../hooks/useWellness';
import { MOOD_META, formatTime } from '../../../lib/mood';
import { MoodFace } from './MoodFace';
import api from '../../../lib/api';
import type { DailyCheckinStatusResponse } from '../../../lib/types';

/** Greeting that matches the clock, so Home reads as *this* moment. */
function greetingFor(date: Date): string {
  const hour = date.getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

function greetingEmoji(date: Date): string {
  const hour = date.getHours();
  if (hour < 12) return '☀️';
  if (hour < 17) return '🌤️';
  return '🌙';
}

/**
 * The four things a student can actually do.
 *
 * They sit together on one soft panel rather than floating as four separate
 * bordered tiles, which is what stopped the row reading as a stats grid.
 *
 * Colour lives in the icon tile, not the card. Tinting the cards themselves
 * was tried first and looked patchy: indigo-50 and teal-50 are perceptually
 * near-white while amber-50 and rose-50 are not, so at equal opacity the row
 * came out half plain and half coloured. White cards on the tinted panel give
 * the cohesion without that unevenness — and match the reference, where the
 * cards are white and the pastel sits in the icon.
 */
const ACTIONS: {
  to: string;
  title: string;
  body: string;
  cta: string;
  Icon: LucideIcon;
  card: string;
  tile: string;
  cta_class: string;
}[] = [
  {
    to: '/student/comrade',
    title: 'Talk to Comrade',
    body: "Share what's on your mind. Kio is here to listen.",
    cta: 'Start chat',
    Icon: MessageCircle,
    card: 'bg-card shadow-[0_1px_2px_rgb(35_43_109_/_0.05)] hover:shadow-[0_6px_20px_-10px_rgb(35_43_109_/_0.18)]',
    tile: 'bg-indigo-50 text-indigo-500',
    cta_class: 'text-indigo-700',
  },
  {
    to: '/student/journal',
    title: 'Write in Journal',
    body: 'A private space for your thoughts.',
    cta: 'Open journal',
    Icon: NotebookPen,
    card: 'bg-card shadow-[0_1px_2px_rgb(35_43_109_/_0.05)] hover:shadow-[0_6px_20px_-10px_rgb(35_43_109_/_0.18)]',
    tile: 'bg-teal-50 text-teal-600',
    cta_class: 'text-teal-700',
  },
  {
    to: '/student/activities',
    title: 'Take a small step',
    body: 'Simple activities to feel a little better.',
    cta: 'Explore activities',
    Icon: Sparkles,
    card: 'bg-card shadow-[0_1px_2px_rgb(35_43_109_/_0.05)] hover:shadow-[0_6px_20px_-10px_rgb(35_43_109_/_0.18)]',
    tile: 'bg-amber-50 text-amber-500',
    cta_class: 'text-amber-700',
  },
  {
    to: '/book-counselor',
    title: 'Talk to a counselor',
    body: 'Book a session with a trusted counselor.',
    cta: 'Book session',
    Icon: UserRound,
    card: 'bg-card shadow-[0_1px_2px_rgb(35_43_109_/_0.05)] hover:shadow-[0_6px_20px_-10px_rgb(35_43_109_/_0.18)]',
    tile: 'bg-rose-50 text-rose-500',
    cta_class: 'text-rose-700',
  },
];

/**
 * Soft organic field behind the hero — the pastel wash from the brand sheet.
 *
 * Blobs rather than circles: irregular border-radii read as organic, and three
 * even circles read as a loading state. They drift very slowly so the page
 * feels alive when still, and not at all under reduced motion.
 *
 * Opacity is kept low enough that text contrast is never affected — the shapes
 * sit behind content that is already on an opaque background.
 */
function BrandAtmosphere() {
  return (
    // No `overflow-hidden`: the hero section is shorter than these blobs, so
    // clipping them cut the blur into a visible rectangle with hard edges —
    // which read as a rendering fault rather than atmosphere. They are laid
    // out from the right inside the content column, so letting them spill
    // cannot push the page sideways.
    <div
      aria-hidden="true"
      className="pointer-events-none absolute -top-10 right-0 hidden h-[280px] w-2/3 md:block"
      style={{
        // The three blobs' falloffs land at similar heights, which left a
        // faint straight seam where the wash met the page. A radial mask
        // dissolves the whole field at its edges, so the atmosphere has no
        // boundary regardless of how the blobs are positioned.
        maskImage:
          'radial-gradient(70% 65% at 62% 42%, #000 35%, transparent 100%)',
        WebkitMaskImage:
          'radial-gradient(70% 65% at 62% 42%, #000 35%, transparent 100%)',
      }}
    >
      <div
        className="absolute right-2 top-0 h-56 w-56 bg-secondary/[0.07] blur-3xl motion-safe:animate-kio-drift"
        style={{ borderRadius: '58% 42% 45% 55% / 52% 48% 52% 48%' }}
      />
      <div
        className="absolute right-40 top-16 h-44 w-44 bg-accent/[0.10] blur-3xl motion-safe:animate-kio-drift"
        style={{
          borderRadius: '44% 56% 62% 38% / 47% 55% 45% 53%',
          animationDelay: '-5s',
        }}
      />
      <div
        className="absolute right-24 -top-6 h-36 w-36 bg-[#8B7CF6]/[0.07] blur-2xl motion-safe:animate-kio-drift"
        style={{
          borderRadius: '52% 48% 38% 62% / 58% 42% 58% 42%',
          animationDelay: '-9s',
        }}
      />
    </div>
  );
}

function SkeletonLine({ className = '' }: { className?: string }) {
  // motion-safe: a pulsing block is exactly what vestibular sensitivity and
  // reduced-motion settings exist to suppress.
  return <div className={`motion-safe:animate-pulse rounded-lg bg-muted ${className}`} />;
}

export function StudentHome() {
  const { user } = useAuth();
  const { conversations, isLoading: convsLoading } = useConversations();
  const { score: wellness } = useWellnessScore();

  const [checkin, setCheckin] = useState<DailyCheckinStatusResponse | null>(null);
  const [checkinLoading, setCheckinLoading] = useState(true);
  const [checkinError, setCheckinError] = useState(false);
  const [showUpdate, setShowUpdate] = useState(false);
  const [showCalendar, setShowCalendar] = useState(false);

  const fetchCheckin = useCallback(async () => {
    setCheckinLoading(true);
    try {
      const { data } = await api.get<DailyCheckinStatusResponse>('/wellness/checkin/today');
      setCheckin(data);
      setCheckinError(false);
    } catch {
      // Home must still render. The check-in card degrades to a gentle
      // prompt rather than taking the page down with it.
      setCheckinError(true);
    } finally {
      setCheckinLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCheckin();
  }, [fetchCheckin]);

  const now = useMemo(() => new Date(), []);
  const mostRecent = conversations[0];
  const mood = checkin?.checkin?.mood ? MOOD_META[checkin.checkin.mood] : null;
  const canUpdate = (checkin?.updates_remaining ?? 0) > 0;

  /**
   * One short, non-numeric line about direction — or nothing at all.
   *
   * Gated on a real week of history, because `trend` on its own does not
   * mean what the copy would imply. The engine compares against the newest
   * score older than seven days, but when none exists it falls back to the
   * *oldest available* score — which can be from this morning — and still
   * reports "improving". And `stable` is what it returns when there is no
   * baseline at all, so an untouched account would otherwise be told things
   * had been "steady this week" on its first day.
   *
   * `streak_days` counts consecutive days carrying a wellness record, so
   * >= 7 guarantees scores actually spanning the week the sentence claims.
   * It is a conservative gate — someone who checked in 10 of the last 14 days
   * with one gap is excluded — but under-showing a gentle sentence is a much
   * better failure here than confidently narrating a week that never happened.
   */
  const WEEK = 7;
  const hasWeekOfHistory = (wellness?.streak_days ?? 0) >= WEEK;
  const wellnessNote = (() => {
    if (!wellness?.has_data || !hasWeekOfHistory) return null;
    if (wellness.trend === 'improving') return 'Things have been trending upward this week.';
    if (wellness.trend === 'declining') return "It's been a heavier week. That's worth being gentle about.";
    if (wellness.trend === 'stable') return 'Things have been fairly steady this week.';
    return null;
  })();

  return (
    <StudentLayout>
      {/* ── Greeting ───────────────────────────────────────────────── */}
      <section className="relative pt-4 sm:pt-6">
        <BrandAtmosphere />
        <div className="relative flex items-center justify-between gap-4">
          <div className="min-w-0 max-w-2xl">
            <h1 className="font-heading text-[2rem] font-semibold leading-[1.15] tracking-tight text-primary sm:text-[2.6rem]">
              {greetingFor(now)}
              {/* Name and emoji stay on one line together. Left to wrap freely
                  the emoji orphans onto a line of its own at phone width, which
                  reads like a mistake. */}
              <span className="whitespace-nowrap">
                {user?.first_name ? `, ${user.first_name}` : ''}
                {/* Hidden at the narrowest width, where it sits right beside
                    the mascot — two smiling faces an inch apart is clutter,
                    and the character is the better one to keep. */}
                <span aria-hidden="true" className="hidden sm:inline">
                  {' '}
                  {greetingEmoji(now)}
                </span>
              </span>
            </h1>
          </div>

          {/* Kio itself, greeting the student back. Present at every width —
              a companion that vanishes on a phone is not much of a companion —
              but smaller, and without the orbiting dots, where space is tight. */}
          <div className="relative shrink-0">
            {/* Responsive visibility lives on wrappers, not on the mascot:
                its own span sets `display`, so a `hidden` class handed to it
                would be a coin toss. Motes are dropped below ~88px, where
                they blur into noise rather than reading as anything. */}
            <span className="block sm:hidden">
              <KioMascot size={76} withParticles={false} />
            </span>
            <span className="hidden sm:block lg:hidden">
              <KioMascot size={124} />
            </span>
            <div className="hidden items-center gap-6 lg:flex">
              <KioMascot size={148} />
              {/* The design's handwritten margin note, in the script face
                  it specifies (Caveat). It ships in the same Google Fonts
                  request as Inter and Poppins rather than a second one, and it
                  is decorative only — nothing a student has to read is set in
                  it, and `aria-hidden` keeps it out of the screen reader. */}
              <p
                className="max-w-[11rem] -rotate-2 font-handwritten text-xl leading-snug text-secondary/80"
                aria-hidden="true"
              >
                You're doing better than you think
                <span className="mt-1 block text-accent">♡</span>
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Today's check-in ───────────────────────────────────────── */}
      <section className="relative mt-6" aria-labelledby="checkin-heading">
        <h2
          id="checkin-heading"
          className="font-heading text-xl font-semibold text-primary"
        >
          How are you feeling today?
        </h2>
        {/* The reference's supporting line. It does the emotional work the
            heading alone cannot: it says the question is an invitation, not a
            form to complete. */}
        <p className="mt-1 text-sm text-muted-foreground">
          Your feelings matter. Take a moment to check in with yourself.
        </p>

        {checkinLoading ? (
          <div className="mt-4 rounded-[20px] bg-gradient-to-br from-secondary/[0.05] to-accent/[0.05] p-5 sm:p-6">
            <div className="flex items-center gap-4">
              <SkeletonLine className="h-12 w-12 rounded-full" />
              <div className="flex-1">
                <SkeletonLine className="h-4 w-52 max-w-full" />
                <SkeletonLine className="mt-2 h-3 w-40 max-w-full" />
              </div>
            </div>
          </div>
        ) : mood && checkin?.checkin ? (
          // Deliberately not a receipt. It leads with how they said they feel,
          // in their words not ours, and keeps the timestamp and the controls
          // quiet underneath — the point is acknowledgement, not confirmation
          // of a completed task.
          <div className="mt-4 rounded-[20px] bg-gradient-to-br from-secondary/[0.05] to-accent/[0.05] p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-4">
              <div className="flex items-center gap-4">
                <span
                  className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-white shadow-[0_1px_3px_rgb(35_43_109_/_0.07)]"
                  aria-hidden="true"
                >
                  <MoodFace mood={checkin.checkin.mood} size={38} />
                </span>
                <div className="min-w-0">
                  <p className="font-heading text-lg font-semibold text-primary">
                    You're feeling {mood.label.toLowerCase()} today
                  </p>
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    Thanks for taking a moment
                    {checkin.checkin.created_at
                      ? ` — you checked in at ${formatTime(checkin.checkin.created_at)}.`
                      : '.'}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setShowCalendar(true)}
                  className="rounded-full px-3 py-1.5 text-sm text-muted-foreground transition hover:bg-white/70 hover:text-foreground"
                >
                  See your month
                </button>
                {canUpdate && (
                  <button
                    type="button"
                    onClick={() => setShowUpdate(true)}
                    className="rounded-full px-3 py-1.5 text-sm font-medium text-secondary transition hover:bg-white/70"
                  >
                    Update
                  </button>
                )}
              </div>
            </div>

            {wellnessNote && (
              <p className="mt-5 border-t border-primary/[0.07] pt-4 text-sm text-muted-foreground">
                {wellnessNote}{' '}
                <Link
                  to="/student/growth"
                  className="text-secondary underline-offset-2 hover:underline"
                >
                  See your growth
                </Link>
              </p>
            )}
          </div>
        ) : (
          // No check-in in this window — or the status call failed. Either way
          // the same existing modal is the way in; Home never invents a second.
          <div className="mt-4 rounded-[20px] bg-gradient-to-br from-secondary/[0.05] to-accent/[0.05] p-5 sm:p-6">
            <p className="text-sm text-muted-foreground">
              {checkinError
                ? "We couldn't load today's check-in just now."
                : "Whenever you're ready, it only takes a moment."}
            </p>
            <button
              type="button"
              onClick={() => (checkinError ? fetchCheckin() : setShowUpdate(true))}
              className="mt-3 rounded-full bg-white px-4 py-2 text-sm font-medium text-secondary shadow-[0_1px_3px_rgb(35_43_109_/_0.07)] transition hover:bg-white/80"
            >
              {checkinError ? 'Try again' : 'Check in'}
            </button>
          </div>
        )}
      </section>

      {/* ── What would you like to do ──────────────────────────────── */}
      <section className="mt-12" aria-labelledby="actions-heading">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2
            id="actions-heading"
            className="font-heading text-xl font-semibold text-primary"
          >
            What would you like to do today?
          </h2>
          <p className="text-sm text-muted-foreground">Small steps. A brighter you.</p>
        </div>

        {/* One panel holding four tinted cards, rather than four bordered
            tiles on the page background. The shared surface is what makes this
            read as a single place to choose from instead of a stats grid. */}
        <div className="mt-4 rounded-[24px] bg-muted/40 p-2 sm:p-3">
          <div className="grid gap-2 sm:grid-cols-2 sm:gap-3 xl:grid-cols-4">
            {ACTIONS.map(({ to, title, body, cta, Icon, card, tile, cta_class }) => (
              <Link
                key={to}
                to={to}
                className={`group flex flex-col rounded-[18px] p-5 transition duration-200 motion-safe:hover:-translate-y-0.5 ${card}`}
              >
                <span
                  className={`flex h-11 w-11 items-center justify-center rounded-[14px] ${tile}`}
                  aria-hidden="true"
                >
                  <Icon className="h-[22px] w-[22px]" strokeWidth={1.6} />
                </span>
                <span className="mt-5 font-heading text-[15px] font-semibold leading-snug text-primary">
                  {title}
                </span>
                <span className="mt-1.5 flex-1 text-[13.5px] leading-relaxed text-muted-foreground">
                  {body}
                </span>
                {/* A text link, not a filled pill. Four solid buttons in a row
                    is what made this look like a control panel. */}
                <span
                  className={`mt-5 inline-flex items-center gap-1.5 text-sm font-medium ${cta_class}`}
                >
                  {cta}
                  <ArrowRight
                    className="h-4 w-4 transition-transform motion-safe:group-hover:translate-x-0.5"
                    strokeWidth={2}
                  />
                </span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* ── Continue where you left off ────────────────────────────── */}
      <section className="mt-12" aria-labelledby="continue-heading">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2
            id="continue-heading"
            className="font-heading text-xl font-semibold text-primary"
          >
            Continue where you left off
          </h2>
          {conversations.length > 0 && (
            <Link
              to="/student/comrade"
              className="text-sm text-secondary transition hover:text-secondary/80"
            >
              View all chats →
            </Link>
          )}
        </div>

        {convsLoading ? (
          <div className="mt-4 rounded-[20px] bg-muted/40 p-5">
            <SkeletonLine className="h-4 w-52 max-w-full" />
            <SkeletonLine className="mt-3 h-3 w-72 max-w-full" />
          </div>
        ) : mostRecent ? (
          <Link
            to={`/student/comrade?c=${mostRecent.conversation_id}`}
            className="group mt-4 flex flex-wrap items-center gap-4 rounded-[20px] bg-muted/40 p-5 transition hover:bg-muted/60"
          >
            <span
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] bg-white text-indigo-500 shadow-[0_1px_2px_rgb(35_43_109_/_0.06)]"
              aria-hidden="true"
            >
              <MessageCircle className="h-[22px] w-[22px]" strokeWidth={1.6} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium text-primary">
                {mostRecent.title || 'New Conversation'}
              </span>
              <span className="mt-0.5 block text-sm text-muted-foreground">
                {mostRecent.total_messages > 0
                  ? `${mostRecent.total_messages} message${mostRecent.total_messages === 1 ? '' : 's'}`
                  : 'No messages yet'}
                {mostRecent.updated_at && ` · ${formatTime(mostRecent.updated_at)}`}
              </span>
            </span>
            <span className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-white px-3.5 py-2 text-sm font-medium text-indigo-700 shadow-[0_1px_2px_rgb(35_43_109_/_0.06)] transition">
              Continue chat
              <ArrowRight
                className="h-4 w-4 transition-transform motion-safe:group-hover:translate-x-0.5"
                strokeWidth={2}
              />
            </span>
          </Link>
        ) : (
          <div className="mt-4 rounded-[20px] border border-dashed border-border/70 bg-muted/20 p-8 text-center">
            <p className="text-sm text-muted-foreground">
              You haven't started a conversation yet. Comrade is here whenever you're ready.
            </p>
            <Link
              to="/student/comrade"
              className="mt-4 inline-flex items-center gap-1.5 rounded-xl bg-white px-4 py-2 text-sm font-medium text-indigo-700 shadow-[0_1px_3px_rgb(35_43_109_/_0.07)] transition hover:bg-white/80"
            >
              Start your first chat
              <ArrowRight className="h-4 w-4" strokeWidth={2} />
            </Link>
          </div>
        )}
      </section>

      {/* Sign-off, mirroring the brand sheet's closing bar. Small, warm, and
          the last thing on the page rather than another call to action. */}
      <div className="mt-12 flex items-center gap-3">
        <KioMascot size={52} withParticles={false} className="shrink-0" />
        <p className="font-handwritten text-xl leading-snug text-muted-foreground">
          “Progress, not perfection.” — Kio
        </p>
      </div>

      {showUpdate && (
        <DailyCheckinModal
          mode="update"
          onClose={() => setShowUpdate(false)}
          onComplete={() => {
            setShowUpdate(false);
            fetchCheckin();
          }}
        />
      )}
      {showCalendar && <MoodCalendarModal onClose={() => setShowCalendar(false)} />}
    </StudentLayout>
  );
}
