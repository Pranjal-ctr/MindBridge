/**
 * The shell every signed-in student screen sits inside.
 *
 * Before this existed the sidebar lived only inside StudentDashboard, and the
 * other student pages had no navigation at all — just a back-arrow to
 * `/student`. So moving between Growth, Activities and Journal meant going
 * home first every time. Extracting the shell is what makes the hierarchy in
 * the redesign possible; it is the same navigation, in one place.
 *
 * **There is exactly one sidebar, and this component owns it.** Its contents
 * are swappable: by default the student navigation (`StudentNavSidebar`), and
 * on Comrade the conversation rail passed in through `sidebar`. That prop is
 * the whole mechanism — Comrade used to render its own rail inside the content
 * area, which at desktop width put two sidebars on screen arguing about what
 * the left edge of the app is for.
 *
 * The collapse state lives here rather than in the nav, because the content
 * column's left offset has to move with it and only this component knows about
 * both. It is remembered per browser; a preference about the width of a rail is
 * not worth a column on `users`.
 *
 * On phones the sidebar is replaced by a bottom bar rather than a drawer.
 * A drawer costs two taps to reach anything and hides where you are; a bottom
 * bar is one tap, always visible, and sits under the thumb. It stays put on
 * Comrade too, so the chat screen is never a place a student can get stuck.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { KioLogo } from '../KioLogo';
import { NotificationBell } from '../NotificationBell';
import { MOBILE_NAV, StudentNavSidebar, isNavActive } from './StudentNavSidebar';

/** Remembered per browser, never on the server. */
const COLLAPSE_KEY = 'kio_student_sidebar_collapsed';

function readCollapsed(): boolean {
  // Private windows and blocked site data both throw here rather than
  // returning null, so the expanded default has to survive an exception.
  try {
    return window.localStorage.getItem(COLLAPSE_KEY) === '1';
  } catch {
    return false;
  }
}

interface StudentLayoutProps {
  children: React.ReactNode;
  /** Right-hand header content. Defaults to the safe-and-private reassurance. */
  headerRight?: React.ReactNode;
  /**
   * Contents of the one sidebar. Defaults to the student navigation; Comrade
   * passes its conversation rail so the two never appear together.
   */
  sidebar?: React.ReactNode;
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
  sidebar,
  variant = 'page',
}: StudentLayoutProps) {
  const { pathname } = useLocation();
  const [collapsed, setCollapsed] = useState(readCollapsed);

  const toggleCollapsed = useCallback(() => {
    setCollapsed((previous) => {
      const next = !previous;
      try {
        window.localStorage.setItem(COLLAPSE_KEY, next ? '1' : '0');
      } catch {
        // A remembered width is a convenience; losing it changes nothing.
      }
      return next;
    });
  }, []);

  // Another tab (or another student page in the same tab's history) may have
  // changed the preference; keep the rails in step rather than having one
  // screen disagree with the next.
  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === COLLAPSE_KEY) setCollapsed(event.newValue === '1');
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  // A conversation list cannot be icon-only, so the custom sidebar always
  // gets full width — and the content offset has to agree with whatever is
  // actually rendered, which is why this is computed in one place.
  const railCollapsed = sidebar === undefined && collapsed;
  const asideWidth = railCollapsed ? 'md:w-[4.5rem]' : 'md:w-64';
  const contentOffset = railCollapsed ? 'md:pl-[4.5rem]' : 'md:pl-64';

  return (
    <div className="min-h-screen bg-background">
      {/* ── Desktop sidebar — the only one on the page ──────────────── */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-border/60 bg-card md:flex ${asideWidth}`}
        aria-label={sidebar ? 'Conversations' : 'Main navigation'}
      >
        {sidebar ?? (
          <StudentNavSidebar
            pathname={pathname}
            collapsed={collapsed}
            onToggleCollapsed={toggleCollapsed}
          />
        )}
      </aside>

      {/* ── Content column ──────────────────────────────────────────── */}
      <div className={`flex min-h-screen flex-col ${contentOffset}`}>
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
            const active = isNavActive(pathname, to);
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
                  <Icon className="h-5 w-5" strokeWidth={active ? 2 : 1.75} aria-hidden="true" />
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
