/**
 * Kio mood scale — single source of truth for mood display.
 *
 * API identifiers (amazing/good/okay/low/very_difficult) are stable backend
 * values; these maps define how they are presented to users.
 */

import type { DailyMood } from './types';

export const MOOD_META: Record<DailyMood, { emoji: string; label: string }> = {
  amazing: { emoji: '😄', label: 'Very Happy' },
  good: { emoji: '🙂', label: 'Happy' },
  okay: { emoji: '😐', label: 'Neutral' },
  low: { emoji: '🙁', label: 'Sad' },
  very_difficult: { emoji: '😞', label: 'Very Low' },
};

export const MOOD_ORDER: DailyMood[] = ['amazing', 'good', 'okay', 'low', 'very_difficult'];

export function moodEmojiForScore(score: number | null): string | null {
  if (score === null) return null;
  if (score >= 9) return MOOD_META.amazing.emoji;
  if (score >= 7) return MOOD_META.good.emoji;
  if (score >= 5) return MOOD_META.okay.emoji;
  if (score >= 3) return MOOD_META.low.emoji;
  return MOOD_META.very_difficult.emoji;
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}
