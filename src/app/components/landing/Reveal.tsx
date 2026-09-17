/**
 * Reveal-on-scroll for the landing page.
 *
 * Deliberately an IntersectionObserver and a CSS transition rather than
 * `motion` (already a dependency, used by ChatMessage): the landing page is the
 * first thing an unauthenticated visitor downloads, and a fade-and-rise does
 * not justify pulling an animation runtime into that chunk.
 *
 * Reduced motion is checked in JS rather than only via a CSS variant, matching
 * KioMascot: under `prefers-reduced-motion` the content is rendered visible
 * immediately with no transition attached at all. The same branch covers
 * environments with no IntersectionObserver (jsdom, older browsers) — content
 * is never left invisible because an observer failed to fire.
 */

import { useEffect, useRef, useState, type ReactNode } from 'react';

interface RevealProps {
  children: ReactNode;
  /** Stagger, in ms. Keep under ~250 — beyond that it reads as a queue. */
  delay?: number;
  className?: string;
  /** Horizontal drift instead of vertical; for two-column compositions. */
  from?: 'bottom' | 'left' | 'right';
  as?: 'div' | 'li';
}

const OFFSETS: Record<NonNullable<RevealProps['from']>, string> = {
  bottom: 'translate3d(0, 18px, 0)',
  left: 'translate3d(-18px, 0, 0)',
  right: 'translate3d(18px, 0, 0)',
};

export function Reveal({
  children,
  delay = 0,
  className = '',
  from = 'bottom',
  as: Tag = 'div',
}: RevealProps) {
  const ref = useRef<HTMLElement | null>(null);
  const [visible, setVisible] = useState(false);
  const [animated, setAnimated] = useState(false);

  useEffect(() => {
    const reduced =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reduced || typeof IntersectionObserver === 'undefined') {
      setVisible(true);
      return;
    }

    setAnimated(true);
    const el = ref.current;
    if (!el) {
      setVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      // Fire a little before the element reaches the fold, so the motion has
      // finished by the time the reader's eye arrives.
      { threshold: 0.08, rootMargin: '0px 0px -8% 0px' },
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <Tag
      ref={ref as never}
      className={className}
      style={
        animated
          ? {
              opacity: visible ? 1 : 0,
              transform: visible ? 'translate3d(0, 0, 0)' : OFFSETS[from],
              transition: `opacity 700ms cubic-bezier(0.22, 1, 0.36, 1) ${delay}ms, transform 700ms cubic-bezier(0.22, 1, 0.36, 1) ${delay}ms`,
              willChange: visible ? undefined : 'opacity, transform',
            }
          : undefined
      }
    >
      {children}
    </Tag>
  );
}
