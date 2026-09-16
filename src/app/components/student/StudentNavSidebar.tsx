/**
 * The student's primary navigation — the default contents of the shell's one
 * sidebar.
 *
 * Kio / profile → primary destinations → Settings / Sign out. Recent Chats
 * used to sit in the middle of that list and no longer does: a history of
 * conversations is only useful once you are in Comrade, and keeping it here
 * meant the chat screen had to grow a second rail beside this one. It now
 * lives in `ConversationSidebar`, which replaces this component when Comrade
 * is open.
 *
 * Collapsed, the rail is icon-only. The labels are what make the destinations
 * legible, so each link keeps its accessible name and gains a native `title`
 * — a collapsed sidebar where nothing is named is a memory test.
 */

import { Link } from 'react-router-dom';
import {
  Home,
  LogOut,
  type LucideIcon,
  MessageCircle,
  NotebookPen,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Sparkles,
  TrendingUp,
  UserRound,
} from 'lucide-react';
import { KioLogo } from '../KioLogo';
import { KioMascot } from '../KioMascot';
import { useAuth } from '../../../lib/auth-context';

export interface NavItem {
  to: string;
  label: string;
  hint: string;
  Icon: LucideIcon;
}

/** Primary destinations, in the order the design shows them. */
export const PRIMARY_NAV: NavItem[] = [
  { to: '/student', label: 'Home', hint: 'Your starting point', Icon: Home },
  { to: '/student/comrade', label: 'Comrade', hint: 'Talk to Kio', Icon: MessageCircle },
  { to: '/student/growth', label: 'Growth', hint: 'Your progress', Icon: TrendingUp },
  { to: '/student/journal', label: 'Journal', hint: 'Your space', Icon: NotebookPen },
  { to: '/student/activities', label: 'Activities', hint: 'Small steps', Icon: Sparkles },
  { to: '/book-counselor', label: 'Counselor', hint: 'Book a session', Icon: UserRound },
];

/** The five that fit a thumb. Journal is reachable from Home's action cards. */
export const MOBILE_NAV = PRIMARY_NAV.filter((item) => item.to !== '/student/journal');

export function isNavActive(pathname: string, to: string): boolean {
  // Exact match for Home, prefix for the rest — otherwise every route
  // beginning `/student` would light Home up as well.
  return to === '/student' ? pathname === to : pathname.startsWith(to);
}

interface StudentNavSidebarProps {
  pathname: string;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}

export function StudentNavSidebar({
  pathname,
  collapsed,
  onToggleCollapsed,
}: StudentNavSidebarProps) {
  const { user, logout } = useAuth();
  const firstName = user?.first_name ?? '';

  return (
    <>
      <div
        className={`flex items-center pt-6 pb-4 ${collapsed ? 'flex-col gap-3 px-2' : 'justify-between px-5'}`}
      >
        <Link to="/student" aria-label="Kio home">
          {/* Collapsed, the wordmark has nowhere to go, so Kio itself stands
              in for it — the same character, at icon size. */}
          {collapsed ? (
            <KioMascot size={30} withParticles={false} />
          ) : (
            <KioLogo className="h-8 w-auto" />
          )}
        </Link>
        <button
          type="button"
          onClick={onToggleCollapsed}
          aria-expanded={!collapsed}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="rounded-lg p-1.5 text-muted-foreground transition hover:bg-muted/60 hover:text-foreground"
        >
          {collapsed ? (
            <PanelLeftOpen className="h-[18px] w-[18px]" strokeWidth={1.75} aria-hidden="true" />
          ) : (
            <PanelLeftClose className="h-[18px] w-[18px]" strokeWidth={1.75} aria-hidden="true" />
          )}
        </button>
      </div>

      {/* Who you are. Quiet, not a profile card. */}
      <Link
        to="/student/profile"
        title={collapsed ? (user ? `${user.first_name} ${user.last_name}` : 'Your profile') : undefined}
        className={`mx-3 flex items-center gap-3 rounded-xl py-2 transition hover:bg-muted/60 ${
          collapsed ? 'justify-center px-0' : 'px-2'
        }`}
      >
        <span
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-secondary/15 text-sm font-medium text-secondary"
          aria-hidden="true"
        >
          {firstName ? firstName[0].toUpperCase() : '·'}
        </span>
        {collapsed ? (
          <span className="sr-only">{user ? `${user.first_name} ${user.last_name}` : 'Your profile'}</span>
        ) : (
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium">
              {user ? `${user.first_name} ${user.last_name}` : '—'}
            </span>
            <span className="block text-xs text-muted-foreground">Student</span>
          </span>
        )}
      </Link>

      <nav className="mt-4 flex-1 space-y-0.5 px-3" aria-label="Student sections">
        {PRIMARY_NAV.map(({ to, label, hint, Icon }) => {
          const active = isNavActive(pathname, to);
          return (
            <Link
              key={to}
              to={to}
              aria-current={active ? 'page' : undefined}
              title={collapsed ? label : undefined}
              className={`flex items-center gap-3 rounded-xl py-2.5 transition ${
                collapsed ? 'justify-center px-0' : 'px-3'
              } ${active ? 'bg-secondary/10 text-secondary' : 'text-foreground hover:bg-muted/60'}`}
            >
              <Icon className="h-5 w-5 shrink-0" strokeWidth={1.75} aria-hidden="true" />
              {collapsed ? (
                <span className="sr-only">{label}</span>
              ) : (
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
              )}
            </Link>
          );
        })}
      </nav>

      <div className="space-y-0.5 border-t border-border/60 p-3">
        <Link
          to="/student/profile"
          title={collapsed ? 'Settings' : undefined}
          className={`flex items-center gap-3 rounded-xl py-2 text-sm text-muted-foreground transition hover:bg-muted/60 hover:text-foreground ${
            collapsed ? 'justify-center px-0' : 'px-3'
          }`}
        >
          <Settings className="h-[18px] w-[18px] shrink-0" strokeWidth={1.75} aria-hidden="true" />
          {collapsed ? <span className="sr-only">Settings</span> : 'Settings'}
        </Link>
        <button
          type="button"
          onClick={logout}
          title={collapsed ? 'Sign out' : undefined}
          className={`flex w-full items-center gap-3 rounded-xl py-2 text-sm text-muted-foreground transition hover:bg-muted/60 hover:text-foreground ${
            collapsed ? 'justify-center px-0' : 'px-3'
          }`}
        >
          <LogOut className="h-[18px] w-[18px] shrink-0" strokeWidth={1.75} aria-hidden="true" />
          {collapsed ? <span className="sr-only">Sign out</span> : 'Sign Out'}
        </button>
      </div>
    </>
  );
}
