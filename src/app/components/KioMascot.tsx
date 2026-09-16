/**
 * Kio — the luminous companion, as a live component rather than an image.
 *
 * Every value below was measured off the brand artwork rather than eyeballed.
 * Sampling `Rebranding/Branding.png` around the orb gave:
 *
 *   eyes          #1E0871  (deep violet — not the navy used elsewhere)
 *   mouth         #5939CA  (violet, ~3px stroke)
 *   purple glow   #D9BCFC  peaking just OUTSIDE the left edge, strongest low
 *   cyan glow     #96F1EE  peaking outside the lower-right
 *   body          white at the upper-left, drifting lavender toward lower-right
 *   boundary      no hard edge — the body fades through #F5F0FC into the glow
 *
 * Which is why this is not a circle with a box-shadow. The volume comes from a
 * radial gradient offset to the upper left; the atmosphere from three large
 * blurred ellipses of different hue, size and position; and the soft boundary
 * from the body gradient reaching zero alpha *before* its own radius, so there
 * is no edge to see. Asymmetry throughout is deliberate — the reference is lit
 * from one side and reads as a being rather than a shape because of it.
 *
 * Motion: all of it is suppressed under `prefers-reduced-motion`, checked at
 * runtime rather than via a CSS variant, because the blink is driven by a
 * timer in JS and a media-query class cannot stop it.
 */

import { useEffect, useId, useRef, useState } from 'react';

/** What Kio is doing. The UI drives this; Kio never decides it. */
export type KioState = 'idle' | 'thinking' | 'responding' | 'success';

interface KioMascotProps {
  size?: number;
  className?: string;
  state?: KioState;
  /** Tiny drifting motes. Worth switching off below ~48px, where they blur. */
  withParticles?: boolean;
  /**
   * Accessible name. Kio is decorative by default and hidden from screen
   * readers; pass this only where it carries meaning a sighted user gets
   * and a screen-reader user otherwise would not (a loading state, say).
   */
  label?: string;
}

/** Live `prefers-reduced-motion`, so a mid-session change is respected. */
function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(query.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    query.addEventListener('change', onChange);
    return () => query.removeEventListener('change', onChange);
  }, []);

  return reduced;
}

/**
 * Natural blinking.
 *
 * Human blinks are irregular — roughly every 2–7 seconds, occasionally twice
 * in quick succession. A fixed interval is the single thing that makes a face
 * read as a machine, so each delay is drawn fresh and doubles are allowed.
 */
function useBlink(enabled: boolean): boolean {
  const [blinking, setBlinking] = useState(false);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    if (!enabled) {
      setBlinking(false);
      return;
    }

    let cancelled = false;
    const clearAll = () => {
      timers.current.forEach(clearTimeout);
      timers.current = [];
    };

    const blinkOnce = (then: () => void) => {
      setBlinking(true);
      timers.current.push(
        window.setTimeout(() => {
          if (cancelled) return;
          setBlinking(false);
          then();
        }, 130),
      );
    };

    const schedule = () => {
      const delay = 2200 + Math.random() * 4800;
      timers.current.push(
        window.setTimeout(() => {
          if (cancelled) return;
          blinkOnce(() => {
            // Occasional double blink — the detail that stops it feeling timed.
            if (Math.random() < 0.18) {
              timers.current.push(
                window.setTimeout(() => {
                  if (cancelled) return;
                  blinkOnce(schedule);
                }, 180),
              );
            } else {
              schedule();
            }
          });
        }, delay),
      );
    };

    schedule();
    return () => {
      cancelled = true;
      clearAll();
    };
  }, [enabled]);

  return blinking;
}

/** Mouth per state. Measured rest curve: ends (93,96), control (100.5,104.5). */
const MOUTH: Record<KioState, string> = {
  idle: 'M93 96 Q100.5 104.5 108 96',
  // Thinking: flatter, a fraction off-centre. Not a frown — just less certain.
  thinking: 'M94 98 Q101 101.5 108 97.5',
  responding: 'M93 96 Q100.5 105.5 108 96',
  // Success: a touch fuller. Still a small smile, never a grin.
  success: 'M91 95 Q100.5 107 109.5 95',
};

export function KioMascot({
  size = 96,
  className = '',
  state = 'idle',
  withParticles = true,
  label,
}: KioMascotProps) {
  // React-generated so several Kios on one page cannot collide on gradient or
  // filter ids, which are document-global in SVG.
  const raw = useId();
  const uid = `kio${raw.replace(/[^a-zA-Z0-9]/g, '')}`;

  const reduced = usePrefersReducedMotion();
  const blinking = useBlink(!reduced);

  // Calm throughout. "thinking" breathes a little quicker, "responding" a
  // little brighter — no state spins, bounces, or changes size sharply.
  const glowDuration = state === 'thinking' ? '3.4s' : state === 'responding' ? '2.6s' : '7s';
  const glowOpacity = state === 'responding' || state === 'success' ? 1 : state === 'thinking' ? 0.92 : 0.85;

  const a11y = label
    ? { role: 'img' as const, 'aria-label': label }
    : { 'aria-hidden': true as const };

  return (
    // No display utility in the base: `inline-block` here would fight a
    // `hidden`/`sm:block` passed in via className, and which one wins depends
    // on Tailwind's output order rather than anything the caller can see.
    // Callers that need responsive visibility wrap this instead.
    <span
      className={`relative shrink-0 ${className}`}
      style={{ width: size, height: size, display: 'inline-block' }}
      {...a11y}
    >
      <svg
        viewBox="0 0 200 200"
        width={size}
        height={size}
        focusable="false"
        aria-hidden="true"
        style={{
          display: 'block',
          animation: reduced ? undefined : 'kio-float 7s ease-in-out infinite',
          overflow: 'visible',
        }}
      >
        <defs>
          {/* Body. Highlight offset up and left, exactly as measured; the
              final stop reaches zero alpha inside the drawn radius, so the
              silhouette feathers instead of ending. */}
          <radialGradient id={`${uid}-body`} cx="37%" cy="29%" r="76%">
            <stop offset="0%" stopColor="#FFFFFF" />
            <stop offset="42%" stopColor="#FEFCFF" />
            <stop offset="70%" stopColor="#F7F2FD" />
            <stop offset="86%" stopColor="#EDE4FA" stopOpacity="0.96" />
            <stop offset="95%" stopColor="#E2D5F5" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#DCCDF3" stopOpacity="0" />
          </radialGradient>

          {/* Atmosphere. Three hues, three positions, three sizes — the
              asymmetry is what stops it reading as a halo. */}
          <radialGradient id={`${uid}-violet`} cx="50%" cy="50%" r="50%">
            <stop offset="38%" stopColor="#A855F7" stopOpacity="0" />
            <stop offset="58%" stopColor="#A855F7" stopOpacity="0.48" />
            <stop offset="72%" stopColor="#BE85F7" stopOpacity="0.24" />
            <stop offset="100%" stopColor="#D9BCFC" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={`${uid}-cyan`} cx="50%" cy="50%" r="50%">
            <stop offset="38%" stopColor="#22D3C8" stopOpacity="0" />
            <stop offset="58%" stopColor="#22D3C8" stopOpacity="0.42" />
            <stop offset="72%" stopColor="#6BE6DC" stopOpacity="0.21" />
            <stop offset="100%" stopColor="#96F1EE" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={`${uid}-sky`} cx="50%" cy="50%" r="50%">
            <stop offset="45%" stopColor="#7FA8FC" stopOpacity="0" />
            <stop offset="65%" stopColor="#7FA8FC" stopOpacity="0.16" />
            <stop offset="100%" stopColor="#C7DBFE" stopOpacity="0" />
          </radialGradient>

          {/* Specular sheen across the upper left of the sphere. */}
          <radialGradient id={`${uid}-sheen`} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
          </radialGradient>

          {/* Large enough to spread well past the orb — the reference's glow
              extends roughly a full radius beyond the body. */}
          <filter id={`${uid}-soft`} x="-75%" y="-75%" width="250%" height="250%">
            <feGaussianBlur stdDeviation="7" />
          </filter>
          <filter id={`${uid}-mote`} x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="1.6" />
          </filter>
        </defs>

        {/* ── Atmosphere ─────────────────────────────────────────── */}
        <g
          filter={`url(#${uid}-soft)`}
          opacity={glowOpacity}
          style={
            reduced
              ? undefined
              : { animation: `kio-breathe ${glowDuration} ease-in-out infinite`,
                  transformOrigin: '100px 100px' }
          }
        >
          {/* Two rings, offset apart. Where they overlap the hues blend, so
              the halo runs violet down the left and cyan down the right
              without either ever detaching from the orb.

              Both are pushed down and outward rather than sitting concentric:
              in the reference the light gathers around 8 and 4 o'clock and the
              crown stays almost clean, which is what stops it reading as a
              halo ring and starts it reading as light falling on a body. */}
          <circle cx="80" cy="108" r="74" fill={`url(#${uid}-violet)`} />
          <circle cx="122" cy="116" r="70" fill={`url(#${uid}-cyan)`} />
          {/* The faintest cool breath, kept low and weak so the top stays open. */}
          <ellipse cx="100" cy="92" rx="70" ry="62" fill={`url(#${uid}-sky)`} />
        </g>

        {/* ── Body ───────────────────────────────────────────────── */}
        <circle cx="100" cy="100" r="48" fill={`url(#${uid}-body)`} />
        <ellipse cx="84" cy="80" rx="20" ry="15" fill={`url(#${uid}-sheen)`} />

        {/* ── Face ───────────────────────────────────────────────── */}
        <g
          style={{
            // Blink closes the lids from the top, so the eyes scale about
            // their own centre line rather than sliding.
            transform: blinking ? 'scaleY(0.12)' : 'scaleY(1)',
            transformOrigin: '100px 83px',
            transition: 'transform 65ms ease-in-out',
          }}
        >
          <ellipse cx="84.5" cy="83" rx="5.6" ry="6.4" fill="#1E0871" />
          <ellipse cx="117.5" cy="83" rx="5.6" ry="6.4" fill="#1E0871" />
          <circle cx="82.6" cy="80.6" r="1.7" fill="#FFFFFF" fillOpacity="0.75" />
          <circle cx="115.6" cy="80.6" r="1.7" fill="#FFFFFF" fillOpacity="0.75" />
        </g>

        <path
          d={MOUTH[state]}
          fill="none"
          stroke="#5939CA"
          strokeWidth="3.2"
          strokeLinecap="round"
          style={{ transition: 'd 420ms ease-in-out' }}
        />

        {/* ── Motes ──────────────────────────────────────────────── */}
        {withParticles && (
          <g filter={`url(#${uid}-mote)`}>
            {[
              { cx: 28, cy: 92, r: 4.4, fill: '#B57BF5', o: 0.30, dur: 17, delay: 0 },
              { cx: 176, cy: 74, r: 3.6, fill: '#93B8FD', o: 0.28, dur: 21, delay: -6 },
              { cx: 163, cy: 141, r: 5.6, fill: '#4FE0D8', o: 0.30, dur: 24, delay: -12 },
              { cx: 46, cy: 150, r: 3.2, fill: '#4FE0D8', o: 0.22, dur: 19, delay: -3 },
              { cx: 128, cy: 30, r: 2.8, fill: '#B57BF5', o: 0.24, dur: 26, delay: -15 },
            ].map((m, i) => (
              <circle
                key={i}
                cx={m.cx}
                cy={m.cy}
                r={m.r}
                fill={m.fill}
                fillOpacity={m.o}
                style={
                  reduced
                    ? undefined
                    : {
                        animation: `kio-mote-${i % 3} ${m.dur}s ease-in-out ${m.delay}s infinite`,
                        transformOrigin: `${m.cx}px ${m.cy}px`,
                      }
                }
              />
            ))}
          </g>
        )}
      </svg>
    </span>
  );
}
