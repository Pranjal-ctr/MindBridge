/**
 * The shell every signed-in student screen sits inside.
 *
 * Before this existed the sidebar lived only inside StudentDashboard, and the
 * other four student pages had no navigation at all — just a back-arrow to
 * `/student`. So moving between Growth, Activities and Journal meant going
 * home first every time. Extracting the shell is what makes the hierarchy in
 * the redesign possible; it is the same navigation, in one place.
 *
 * Structure follows the Kio home reference:
 *   primary nav  →  Recent Chats  →  secondary (Settings / Profile / Sign out)
 *
 * On phones the sidebar is replaced by a bottom bar rather than a drawer.
 * A drawer costs two taps to reach anything and hides where you are; a bottom
 * bar is one tap, always visible, and sits under the thumb. Recent Chats moves
 * into the Comrade screen there, since a phone has no room for a history list
 * that is only useful once you are already in a conversation.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Clock,
  Home,
  LogOut,
  type LucideIcon,
  MessageCircle,
  NotebookPen,
  Settings,
  Sparkles,
  TrendingUp,
  UserRound,
} from 'lucide-react';
import { KioLogo } from '../KioLogo';
import { NotificationBell } from '../NotificationBell';
import { useAuth } from '../../../lib/auth-context';
import { useConversations } from '../../../hooks/useConversations';

/** Primary destinations, in the order the reference shows them. */
const PRIMARY_NAV: {
  to: string;
  label: string;
  hint: string;
  Icon: LucideIcon;
}[] = [
  { to: '/student', label: 'Home', hint: 'Your starting point', Icon: Home },
  { to: '/student/comrade', label: 'Comrade', hint: 'Talk to Kio', Icon: MessageCircle },
  { to: '/student/growth', label: 'Growth', hint: 'Your progress', Icon: TrendingUp },
  { to: '/student/journal', label: 'Journal', hint: 'Your space', Icon: NotebookPen },
  { to: '/student/activities', label: 'Activities', hint: 'Small steps', Icon: Sparkles },
  { to: '/book-counselor', label: 'Counselor', hint: 'Book a session', Icon: UserRound },
];

/** The five that fit a thumb. Journal is reachable from Home's action cards. */
const MOBILE_NAV = PRIMARY_NAV.filter((item) => item.to !== '/student/journal');

function isActive(pathname: string, to: string): boolean {
  // Exact match for Home, prefix for the rest — otherwise every route
  // beginning `/student` would light Home up as well.
  return to === '/student' ? pathname === to : pathname.startsWith(to);
}

/** Relative day label for the chat list: Today / Yesterday / "Sep 12". */
function shortDate(iso: string | null | undefined): string {
  if (!iso) return '';
  const date = new Date(iso);
  const today = new Date();
  const days = Math.floor(
    (new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime() -
      new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()) /
      86_400_000,
  );
  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

interface StudentLayoutProps {
  children: React.ReactNode;
  /** Right-hand header content. Defaults to the safe-and-private reassurance. */
  headerRight?: React.ReactNode;
  /**
   * 'page'  — centred content column with padding (Home, Journal).
   * 'full'  — content manages its own scrolling (chat).
   * 'bare'  — nav chrome only, no header. For the older student pages that
   *           still carry their own full-width header; they gain the sidebar
   *           and the mobile bottom bar without growing a second header.
   */
  variant?: 'page' | 'full' | 'bare';
}

export function StudentLayout({
  children,
  headerRight,
  variant = 'page',
}: StudentLayoutProps) {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const { conversations } = useConversations();

  const firstName = user?.first_name ?? '';
  const recent = conversations.slice(0, 5);

  return (
    <div className="min-h-screen bg-background">
      {/* ── Desktop sidebar ─────────────────────────────────────────── */}
      <aside
        className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-border/60 bg-card md:flex"
        aria-label="Main navigation"
      >
        <div className="px-5 pt-6 pb-4">
          <Link to="/student" aria-label="Kio home">
            <KioLogo className="h-8 w-auto" />
          </Link>
        </div>

        {/* Who you are. Quiet, not a profile card. */}
        <Link
          to="/student/profile"
          className="mx-3 flex items-center gap-3 rounded-xl px-2 py-2 transition hover:bg-muted/60"
        >
          <span
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-secondary/15 text-sm font-medium text-secondary"
            aria-hidden="true"
          >
            {firstName ? firstName[0].toUpperCase() : '·'}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium">
              {user ? `${user.first_name} ${user.last_name}` : '—'}
            </span>
            <span className="block text-xs text-muted-foreground">Student</span>
          </span>
        </Link>

        <nav className="mt-4 space-y-0.5 px-3">
          {PRIMARY_NAV.map(({ to, label, hint, Icon }) => {
            const active = isActive(pathname, to);
            return (
              <Link
                key={to}
                to={to}
                aria-current={active ? 'page' : undefined}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 transition ${
                  active
                    ? 'bg-secondary/10 text-secondary'
                    : 'text-foreground hover:bg-muted/60'
                }`}
              >
                <Icon className="h-5 w-5 shrink-0" strokeWidth={1.75} />
                <span className="min-w-0">
                  <span className="block text-sm font-medium leading-tight">{label}</span>
                  <span
                    className={`block text-xs leading-tight ${
                      active ? 'text-secondary/70' : 'text-muted-foreground'
                    }`}
                  >
                    {hint}
                  </span>
                </span>
              </Link>
            );
          })}
        </nav>

        {/* ── Recent chats ──────────────────────────────────────────── */}
        <div className="mt-5 min-h-0 flex-1 border-t border-border/60 px-3 pt-4">
          <div className="flex items-center gap-2 px-2 pb-2 text-xs font-medium text-muted-foreground">
            <Clock className="h-3.5 w-3.5" strokeWidth={1.75} />
            Recent Chats
          </div>

          {recent.length === 0 ? (
            <p className="px-2 py-1 text-xs text-muted-foreground">
              Your conversations will appear here.
            </p>
          ) : (
            <ul className="space-y-0.5">
              {recent.map((conv) => (
                <li key={conv.conversation_id}>
                  <Link
                    to={`/student/comrade?c=${conv.conversation_id}`}
                    className="flex items-baseline justify-between gap-2 rounded-lg px-2 py-1.5 transition hover:bg-muted/60"
                  >
                    <span className="min-w-0 truncate text-sm text-foreground/80">
                      {conv.title || 'New Conversation'}
                    </span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {shortDate(conv.updated_at ?? conv.created_at)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}

          <Link
            to="/student/comrade"
            className="mt-1 inline-block px-2 py-1.5 text-sm text-secondary transition hover:text-secondary/80"
          >
            View all chats →
          </Link>
        </div>

        {/* ── Secondary ─────────────────────────────────────────────── */}
        <div className="space-y-0.5 border-t border-border/60 p-3">
          <Link
            to="/student/profile"
            className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-muted-foreground transition hover:bg-muted/60 hover:text-foreground"
          >
            <Settings className="h-[18px] w-[18px]" strokeWidth={1.75} />
            Settings
          </Link>
          <button
            type="button"
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm text-muted-foreground transition hover:bg-muted/60 hover:text-foreground"
          >
            <LogOut className="h-[18px] w-[18px]" strokeWidth={1.75} />
            Sign Out
          </button>
        </div>
      </aside>

      {/* ── Content column ──────────────────────────────────────────── */}
      <div className="flex min-h-screen flex-col md:pl-64">
        {variant !== 'bare' && (
        <header className="flex h-16 shrink-0 items-center justify-between gap-3 px-4 md:px-8">
          {/* The wordmark rides in the header on phones, where there is no
              sidebar to hold it. */}
          <Link to="/student" className="md:hidden" aria-label="Kio home">
            <KioLogo className="h-7 w-auto" />
          </Link>
          <div className="hidden md:block" />

          <div className="flex items-center gap-3">
            {headerRight ?? (
              <span className="text-xs text-muted-foreground sm:text-sm">
                <span className="hidden sm:inline">Always here to listen • </span>
                Safe &amp; Private
              </span>
            )}
            <NotificationBell />
          </div>
        </header>
        )}

        <main
          className={
            variant === 'full'
              ? 'flex min-h-0 flex-1 flex-col pb-16 md:pb-0'
              : variant === 'bare'
                // Bottom padding clears the mobile bar; these pages bring
                // their own horizontal padding.
                ? 'flex-1 pb-20 md:pb-0'
                : 'flex-1 px-4 pb-24 md:px-8 md:pb-12'
          }
        >
          {variant === 'page' ? (
            <div className="mx-auto w-full max-w-5xl">{children}</div>
          ) : (
            children
          )}
        </main>
      </div>

      {/* ── Mobile bottom navigation ────────────────────────────────── */}
      <nav
        className="fixed inset-x-0 bottom-0 z-30 border-t border-border/60 bg-card/95 backdrop-blur md:hidden"
        aria-label="Main navigation"
      >
        <ul
          className="mx-auto flex max-w-lg items-stretch justify-around"
          // Keeps the bar clear of the iOS home indicator.
          style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
        >
          {MOBILE_NAV.map(({ to, label, Icon }) => {
            const active = isActive(pathname, to);
            return (
              <li key={to} className="flex-1">
                <Link
                  to={to}
                  aria-current={active ? 'page' : undefined}
                  // 56px tall: comfortably over the 44px touch-target minimum.
                  className={`flex h-14 flex-col items-center justify-center gap-1 text-[11px] transition ${
                    active ? 'text-secondary' : 'text-muted-foreground'
                  }`}
                >
                  <Icon className="h-5 w-5" strokeWidth={active ? 2 : 1.75} />
                  {label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
