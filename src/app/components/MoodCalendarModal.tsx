/**
 * Student mood calendar — compact monthly view of mood check-ins with the
 * student's own notes. Private to the student (parents only see aggregates).
 */

import { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Loader2, X } from 'lucide-react';
import api from '../../lib/api';
import { MOOD_META, moodEmojiForScore } from '../../lib/mood';
import type { MoodCalendarDay, MoodCalendarResponse } from '../../lib/types';

interface MoodCalendarModalProps {
  onClose: () => void;
}

export function MoodCalendarModal({ onClose }: MoodCalendarModalProps) {
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [calendar, setCalendar] = useState<MoodCalendarResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selected, setSelected] = useState<MoodCalendarDay | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setSelected(null);
    api
      .get<MoodCalendarResponse>('/wellness/mood-calendar', { params: { month } })
      .then((res) => { if (!cancelled) setCalendar(res.data); })
      .catch(() => { if (!cancelled) setCalendar(null); })
      .finally(() => { if (!cancelled) setIsLoading(false); });
    return () => { cancelled = true; };
  }, [month]);

  const shiftMonth = (delta: number) => {
    const [year, m] = month.split('-').map(Number);
    const d = new Date(year, m - 1 + delta, 1);
    setMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`);
  };

  const cells = useMemo(() => {
    const [year, m] = month.split('-').map(Number);
    const firstWeekday = (new Date(year, m - 1, 1).getDay() + 6) % 7; // Monday-first
    const daysInMonth = new Date(year, m, 0).getDate();
    const byDate = new Map((calendar?.days ?? []).map((d) => [d.date, d]));
    const list: ({ day: number; entry: MoodCalendarDay | null } | null)[] = [];
    for (let i = 0; i < firstWeekday; i++) list.push(null);
    for (let day = 1; day <= daysInMonth; day++) {
      const iso = `${month}-${String(day).padStart(2, '0')}`;
      list.push({ day, entry: byDate.get(iso) ?? null });
    }
    return list;
  }, [month, calendar]);

  const emojiFor = (entry: MoodCalendarDay) =>
    entry.mood ? MOOD_META[entry.mood].emoji : moodEmojiForScore(entry.mood_score);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md bg-white rounded-2xl shadow-xl border border-border overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="font-semibold">Mood Calendar</h2>
          <div className="flex items-center gap-2">
            <button onClick={() => shiftMonth(-1)} className="p-1.5 rounded-lg hover:bg-muted transition" aria-label="Previous month">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-sm text-muted-foreground w-28 text-center">
              {new Date(`${month}-01`).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
            </span>
            <button onClick={() => shiftMonth(1)} className="p-1.5 rounded-lg hover:bg-muted transition" aria-label="Next month">
              <ChevronRight className="w-4 h-4" />
            </button>
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-muted transition ml-1" aria-label="Close">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="p-5">
          {isLoading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              <div className="grid grid-cols-7 gap-1 text-center">
                {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((d, idx) => (
                  <div key={idx} className="text-xs text-muted-foreground py-1">{d}</div>
                ))}
                {cells.map((cell, idx) =>
                  cell === null ? (
                    <div key={idx} />
                  ) : (
                    <button
                      key={idx}
                      onClick={() => cell.entry && setSelected(cell.entry)}
                      disabled={!cell.entry}
                      className={`aspect-square rounded-lg flex flex-col items-center justify-center transition ${
                        cell.entry
                          ? selected?.date === cell.entry.date
                            ? 'bg-primary/10 ring-2 ring-primary/40'
                            : 'bg-muted/60 hover:bg-muted'
                          : ''
                      }`}
                    >
                      <span className="text-muted-foreground/70 text-[10px]">{cell.day}</span>
                      {cell.entry && (
                        <span className="text-base leading-none">{emojiFor(cell.entry)}</span>
                      )}
                    </button>
                  )
                )}
              </div>

              {selected ? (
                <div className="mt-4 p-4 bg-muted/50 rounded-xl text-sm space-y-1">
                  <div className="font-medium">
                    {new Date(selected.date).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
                    {selected.mood && ` — ${MOOD_META[selected.mood].emoji} ${MOOD_META[selected.mood].label}`}
                  </div>
                  {selected.reason && (
                    <div className="text-muted-foreground capitalize">
                      On their mind: {selected.reason.replace('_', ' ')}
                    </div>
                  )}
                  {selected.note && (
                    <div className="text-muted-foreground italic">"{selected.note}"</div>
                  )}
                </div>
              ) : (calendar?.days.length ?? 0) > 0 ? (
                <p className="mt-4 text-xs text-muted-foreground text-center">
                  Tap a day to see your note.
                </p>
              ) : (
                <p className="mt-4 text-sm text-muted-foreground text-center">
                  No check-ins recorded this month yet.
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
