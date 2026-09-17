/**
 * Landing-page navigation with a soft edge.
 *
 * Two different problems, because the landing page has two kinds of link:
 *
 * `TransitionLink` — outbound route changes (/login, /privacy, /terms). The app
 * mounts a declarative <BrowserRouter>, so React Router's own `viewTransition`
 * prop is inert here; it needs a data router, and swapping the router over for
 * a cross-fade is not a trade worth making. Instead this calls
 * `document.startViewTransition()` directly. Where the browser has no View
 * Transitions API it simply navigates, exactly as before — no artificial delay
 * is introduced to fake one, because a timer that holds a page back after a
 * click reads as lag, not polish.
 *
 * `AnchorLink` — in-page jumps (#features, #pricing, …). These were instant
 * jumps, which is the jarring part: the reader loses their place because
 * nothing connects where they were to where they landed.
 *
 * Both fall back to instant under `prefers-reduced-motion`. Modified clicks
 * (ctrl/cmd/shift, middle button) are deliberately left to the browser, so
 * "open in new tab" still works — and so a view transition never starts for a
 * navigation that is not happening in this tab, which would leave the page
 * frozen mid-fade.
 */

import { useCallback, type MouseEvent, type ReactNode } from 'react';
import { flushSync } from 'react-dom';
import { Link, useNavigate } from 'react-router-dom';

function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

/** True for clicks the browser should keep: new tab, new window, middle-click. */
function isModifiedClick(e: MouseEvent): boolean {
  return e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0;
}

type DocumentWithViewTransition = Document & {
  startViewTransition?: (callback: () => void) => unknown;
};

export function useTransitionNavigate() {
  const navigate = useNavigate();

  return useCallback(
    (to: string) => {
      const doc = document as DocumentWithViewTransition;
      if (prefersReducedMotion() || typeof doc.startViewTransition !== 'function') {
        navigate(to);
        return;
      }
      // flushSync so the route has actually rendered by the time the browser
      // takes its "after" snapshot — without it the transition captures the
      // old DOM twice and nothing appears to happen.
      doc.startViewTransition(() => {
        flushSync(() => {
          navigate(to);
        });
      });
    },
    [navigate],
  );
}

export function TransitionLink({
  to,
  children,
  className,
  onClick,
}: {
  to: string;
  children: ReactNode;
  className?: string;
  onClick?: (e: MouseEvent<HTMLAnchorElement>) => void;
}) {
  const go = useTransitionNavigate();

  return (
    <Link
      to={to}
      className={className}
      onClick={(e) => {
        onClick?.(e);
        if (isModifiedClick(e)) return;
        e.preventDefault();
        go(to);
      }}
    >
      {children}
    </Link>
  );
}

export function AnchorLink({
  href,
  children,
  className,
  onClick,
}: {
  /** An in-page target, e.g. "#features". */
  href: string;
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <a
      href={href}
      className={className}
      onClick={(e) => {
        onClick?.();
        if (isModifiedClick(e)) return;
        const target = document.getElementById(href.slice(1));
        // No target: leave it to the browser rather than swallowing the click.
        if (!target) return;
        e.preventDefault();
        target.scrollIntoView({
          behavior: prefersReducedMotion() ? 'auto' : 'smooth',
          block: 'start',
        });
        // Keep the URL shareable, but with replaceState — pushing would make
        // Back walk up the page one section at a time instead of leaving.
        window.history.replaceState(null, '', href);
      }}
    >
      {children}
    </a>
  );
}
