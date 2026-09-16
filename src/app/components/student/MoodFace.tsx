/**
 * MoodFace — the five Kio mood faces, drawn rather than typed.
 *
 * Replaces the emoji characters (😄 🙂 😐 🙁 😞) the student surfaces used to
 * render. Emoji are a font, and which font depends on the device: the same
 * check-in read as Apple's glossy faces on one phone, Segoe's flat outlines on
 * a school Windows machine, and a tofu box where the family shares an older
 * Android. For the one control this product asks a teenager to use every day,
 * that is not a detail — the scale has to look like the same scale everywhere,
 * and it has to look like Kio.
 *
 * So each face is an SVG: one pastel disc, two eyes, one mouth, sized off the
 * radius so a 28px face in a calendar cell and a 56px face in the check-in
 * modal are the same drawing rather than two hand-tuned ones.
 *
 * The mood keys are the backend's (`amazing` … `very_difficult`); nothing here
 * introduces a second vocabulary. Colours run green → lime → amber → orange →
 * pink, warm to cool rather than good to bad: `very_difficult` is a face with
 * tears, not a red alert, because a student picking it is telling us something
 * hard and should not be met with a warning colour.
 */

import type { DailyMood } from '../../../lib/types';

interface MoodFaceProps {
  mood: DailyMood;
  /** Rendered width and height in px. */
  size?: number;
  /** Ring treatment for the currently chosen mood in a picker. */
  selected?: boolean;
  className?: string;
}

/** Disc fill and selection ring per mood. */
const FACE: Record<DailyMood, { bg: string; ring: string }> = {
  amazing: { bg: '#D3F9D8', ring: '#40C057' },
  good: { bg: '#E2F8D4', ring: '#82C91E' },
  okay: { bg: '#FFF3BF', ring: '#F59F00' },
  low: { bg: '#FFE8CC', ring: '#F76707' },
  very_difficult: { bg: '#FFD6E7', ring: '#E64980' },
};

/** Ink for eyes and mouth — Kio navy, never pure black. */
const INK = '#232B6D';

export function MoodFace({ mood, size = 52, selected = false, className = '' }: MoodFaceProps) {
  const c = FACE[mood];
  const half = size / 2;
  const r = size * 0.42;

  const eyeLx = half - r * 0.3;
  const eyeRx = half + r * 0.3;
  const eyeY = half - r * 0.15;
  const eyeR = r * (mood === 'amazing' || mood === 'very_difficult' ? 0.14 : 0.13);

  // Every mouth is drawn from this baseline, so the five faces line up when
  // they sit in a row.
  const mouthY = half + r * 0.1;
  const stroke = size * 0.045;

  const mouth: Record<DailyMood, JSX.Element> = {
    amazing: (
      <path
        d={`M${half - r * 0.38} ${mouthY} Q${half} ${mouthY + r * 0.38} ${half + r * 0.38} ${mouthY}`}
        stroke={INK}
        strokeWidth={stroke}
        strokeLinecap="round"
        fill="none"
      />
    ),
    good: (
      <path
        d={`M${half - r * 0.32} ${mouthY} Q${half} ${mouthY + r * 0.28} ${half + r * 0.32} ${mouthY}`}
        stroke={INK}
        strokeWidth={stroke * 0.9}
        strokeLinecap="round"
        fill="none"
      />
    ),
    okay: (
      <line
        x1={half - r * 0.28}
        y1={mouthY + r * 0.04}
        x2={half + r * 0.28}
        y2={mouthY + r * 0.04}
        stroke={INK}
        strokeWidth={stroke * 0.9}
        strokeLinecap="round"
      />
    ),
    low: (
      <path
        d={`M${half - r * 0.32} ${mouthY + r * 0.2} Q${half} ${mouthY - r * 0.08} ${half + r * 0.32} ${mouthY + r * 0.2}`}
        stroke={INK}
        strokeWidth={stroke * 0.9}
        strokeLinecap="round"
        fill="none"
      />
    ),
    very_difficult: (
      <>
        <path
          d={`M${half - r * 0.36} ${mouthY + r * 0.24} Q${half} ${mouthY - r * 0.12} ${half + r * 0.36} ${mouthY + r * 0.24}`}
          stroke={INK}
          strokeWidth={stroke}
          strokeLinecap="round"
          fill="none"
        />
        {/* Tears. Dropped below ~28px, where they turn into two grey specks. */}
        {size >= 28 && (
          <>
            <ellipse
              cx={eyeLx + r * 0.05}
              cy={eyeY + r * 0.3}
              rx={r * 0.08}
              ry={r * 0.13}
              fill="#74B9FF"
              opacity="0.7"
            />
            <ellipse
              cx={eyeRx - r * 0.05}
              cy={eyeY + r * 0.3}
              rx={r * 0.08}
              ry={r * 0.13}
              fill="#74B9FF"
              opacity="0.7"
            />
          </>
        )}
      </>
    ),
  };

  return (
    // Decorative: every caller pairs it with the mood's label in text, so a
    // screen reader that also announced the drawing would read it twice.
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={className}
      aria-hidden="true"
      focusable="false"
      style={{ overflow: 'visible', display: 'block' }}
    >
      <circle
        cx={half}
        cy={half}
        r={r}
        fill={c.bg}
        stroke={selected ? c.ring : 'transparent'}
        strokeWidth={selected ? size * 0.055 : 0}
      />
      {selected && (
        <circle
          cx={half}
          cy={half}
          r={r + size * 0.1}
          fill="none"
          stroke={c.ring}
          strokeWidth={size * 0.035}
          opacity="0.3"
        />
      )}
      <circle cx={eyeLx} cy={eyeY} r={eyeR} fill={INK} />
      <circle cx={eyeRx} cy={eyeY} r={eyeR} fill={INK} />
      {mouth[mood]}
    </svg>
  );
}

/** The same face for a 1–10 mood score, for surfaces that only store a number. */
export function moodForScore(score: number | null): DailyMood | null {
  if (score === null) return null;
  if (score >= 9) return 'amazing';
  if (score >= 7) return 'good';
  if (score >= 5) return 'okay';
  if (score >= 3) return 'low';
  return 'very_difficult';
}
