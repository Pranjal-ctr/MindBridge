/**
 * The shell every signed-in parent screen sits inside.
 *
 * It exists for the same reason `StudentLayout` does. The parent sidebar lived
 * inside ParentDashboard, so `/book-counselor` — reached from a button in that
 * very sidebar — rendered with no navigation at all: a parent who followed it
 * lost the dashboard, their children, and every way back except the browser's
 * own button.
 *
 * What was lifted out is the *chrome*: who you are, where you can go, book a
 * counselor, sign out. What stayed behind is everything that is really
 * dashboard state rather than navigation — the child selector and the
 * link-a-child form — which arrive here through `sidebarExtras` and appear only
 * on the page that owns them. Putting the child selector on the booking page
 * would have meant two different "which child" controls on one screen, each
 * with its own answer.
 *
 * Because the destinations have to work from another page, the dashboard's
 * three tabs are addressed as `/parent?view=…` rather than by local state.
 * They were `useState`, which cannot be linked to from anywhere else.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  CalendarPlus,
  Heart,
  Lightbulb,
  type LucideIcon,
  Menu,
  TrendingUp,
  X,
} from 'lucide-react';
import { KioLogo } from '../KioLogo';
import { NotificationBell } from '../NotificationBell';
import { useAuth } from '../../../lib/auth-context';

/** The dashboard's three views, as URL-addressable destinations. */
export type ParentView = 'overview' | 'recommendations' | 'activities';

/** Which nav row is current. 'booking' is a page of its own, not a view. */
export type ParentSection = ParentView | 'booking';

const PARENT_NAV: { view: ParentView; label: string; Icon: LucideIcon }[] = [
  { view: 'overview', label: 'Overview', Icon: TrendingUp },
  { view: 'recommendations', label: 'Recommendations', Icon: Lightbulb },
  { view: 'activities', label: 'Family Activities', Icon: Heart },
];

interface ParentLayoutProps {
  children: React.ReactNode;
  /** Highlights the current destination. */
  active: ParentSection;
  /** Page title in the header bar. */
  title: string;
  /** Right-hand header content (the dashboard's refresh control). */
  headerRight?: React.ReactNode;
  /**
   * Dashboard-only sidebar content — the child selector and the link-a-child
   * form. Absent everywhere else, because neither means anything off the
   * dashboard.
   */
  sidebarExtras?: React.ReactNode;
  /**
   * Called when a nav item is chosen while already on the dashboard, so it can
   * switch view without a navigation. Pages that are not the dashboard leave
   * this unset and the links navigate normally.
   */
  onSelectView?: (view: ParentView) => void;
}

export function ParentLayout({
  children,
  active,
  title,
  headerRight,
  sidebarExtras,
  onSelectView,
}: ParentLayoutProps) {
  const { user, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* ── Sidebar ─────────────────────────────────────────────────── */}
      <div
        className={`${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        } fixed inset-y-0 left-0 z-50 w-64 border-r border-sidebar-border bg-sidebar transition-transform duration-300 ease-in-out md:static md:translate-x-0`}
      >
        <div className="flex h-full flex-col">
          <div className="border-b border-sidebar-border p-4">
            <div className="flex items-center justify-between">
              <Link to="/parent" aria-label="Kio home">
                <KioLogo className="h-7 w-auto" />
              </Link>
              <button
                className="md:hidden"
                onClick={() => setSidebarOpen(false)}
                aria-label="Close menu"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="mt-3 rounded-lg bg-sidebar-accent px-3 py-2">
              <div className="text-sm font-medium">
                {user ? `${user.first_name} ${user.last_name}` : 'Parent Portal'}
              </div>
              <div className="text-xs text-muted-foreground">Parent</div>
            </div>
          </div>

          {sidebarExtras}

          <nav className="flex-1 space-y-2 p-4" aria-label="Parent sections">
            {PARENT_NAV.map(({ view, label, Icon }) => {
              const current = active === view;
              return (
                <Link
                  key={view}
                  to={`/parent?view=${view}`}
                  aria-current={current ? 'page' : undefined}
                  onClick={(event) => {
                    setSidebarOpen(false);
                    // On the dashboard itself this is a view switch, not a
                    // page load: navigating would discard the insights already
                    // fetched for the selected child.
                    if (onSelectView) {
                      event.preventDefault();
                      onSelectView(view);
                    }
                  }}
                  className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition ${
                    current
                      ? 'bg-sidebar-primary text-sidebar-primary-foreground'
                      : 'text-sidebar-foreground hover:bg-sidebar-accent'
                  }`}
                >
                  <Icon className="h-5 w-5" />
                  <span>{label}</span>
                </Link>
              );
            })}
          </nav>

          <div className="space-y-2 border-t border-sidebar-border p-4">
            <Link
              to="/book-counselor"
              onClick={() => setSidebarOpen(false)}
              aria-current={active === 'booking' ? 'page' : undefined}
              className={`flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm transition ${
                active === 'booking'
                  ? 'bg-accent/90 text-accent-foreground ring-2 ring-accent/40'
                  : 'bg-accent text-accent-foreground hover:bg-accent/90'
              }`}
            >
              <CalendarPlus className="h-4 w-4" />
              Book a Counselor
            </Link>
            <button
              onClick={logout}
              className="flex w-full items-center justify-center rounded-lg px-3 py-2 text-sm text-muted-foreground transition hover:bg-sidebar-accent"
            >
              Sign Out
            </button>
          </div>
        </div>
      </div>

      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* ── Content ─────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-border bg-card px-4 md:px-6">
          <div className="flex items-center gap-4">
            <button
              className="md:hidden"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open menu"
            >
              <Menu className="h-6 w-6" />
            </button>
            <h1 className="text-lg font-semibold">{title}</h1>
          </div>
          <div className="flex items-center gap-3">
            {headerRight}
            <NotificationBell />
          </div>
        </header>

        {children}
      </div>
    </div>
  );
}
