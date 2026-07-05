/**
 * Counselor availability manager — add/remove bookable slots.
 * Self-contained: talks to /counselors/availability directly.
 */

import { useState, useEffect, useCallback } from 'react';
import { CalendarPlus, Loader2, Trash2, Clock } from 'lucide-react';
import api from '../../lib/api';
import type { AvailabilitySlot, SlotListResponse } from '../../lib/types';

export function CounselorAvailability() {
  const [slots, setSlots] = useState<AvailabilitySlot[]>([]);
  const [loading, setLoading] = useState(true);
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');
  const [duration, setDuration] = useState(45);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await api.get<SlotListResponse>('/counselors/availability');
      setSlots(data.slots);
    } catch {
      setSlots([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const addSlot = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!date || !time) return;
    setBusy(true);
    setError(null);
    try {
      const start = new Date(`${date}T${time}`);
      const end = new Date(start.getTime() + duration * 60000);
      await api.post('/counselors/availability', {
        start_at: start.toISOString(),
        end_at: end.toISOString(),
      });
      setDate(''); setTime('');
      await load();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Could not add slot.');
    } finally {
      setBusy(false);
    }
  };

  const removeSlot = async (slotId: string) => {
    setBusy(true);
    setError(null);
    try {
      await api.delete(`/counselors/availability/${slotId}`);
      await load();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Could not remove slot.');
    } finally {
      setBusy(false);
    }
  };

  const fmt = (s: AvailabilitySlot) =>
    new Date(s.start_at).toLocaleString('en-US', {
      weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
    });

  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
      <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <CalendarPlus className="w-5 h-5 text-primary" /> My Availability
      </h2>

      {error && <div className="mb-3 p-2 bg-red-50 text-red-700 text-sm rounded-lg">{error}</div>}

      <form onSubmit={addSlot} className="flex flex-wrap items-end gap-3 mb-5">
        <div>
          <label className="text-xs font-medium text-muted-foreground block mb-1">Date</label>
          <input type="date" required value={date} min={new Date().toISOString().split('T')[0]}
            onChange={(e) => setDate(e.target.value)}
            className="px-3 py-2 border border-border rounded-lg text-sm bg-input-background" />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground block mb-1">Start time</label>
          <input type="time" required value={time} onChange={(e) => setTime(e.target.value)}
            className="px-3 py-2 border border-border rounded-lg text-sm bg-input-background" />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground block mb-1">Duration</label>
          <select value={duration} onChange={(e) => setDuration(parseInt(e.target.value))}
            className="px-3 py-2 border border-border rounded-lg text-sm bg-input-background">
            <option value={30}>30 min</option>
            <option value={45}>45 min</option>
            <option value={60}>60 min</option>
          </select>
        </div>
        <button type="submit" disabled={busy}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-primary/90 transition">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <CalendarPlus className="w-4 h-4" />}
          Add Slot
        </button>
      </form>

      {loading ? (
        <div className="flex justify-center py-6"><Loader2 className="w-5 h-5 animate-spin text-muted-foreground" /></div>
      ) : slots.length === 0 ? (
        <p className="text-sm text-muted-foreground">No upcoming slots. Add some so students can book you.</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {slots.map((s) => (
            <div key={s.slot_id}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm ${
                s.is_booked ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-muted border-border'
              }`}>
              <Clock className="w-3.5 h-3.5" />
              {fmt(s)}
              {s.is_booked ? (
                <span className="text-xs font-medium">Booked</span>
              ) : (
                <button onClick={() => removeSlot(s.slot_id)} disabled={busy}
                  className="text-muted-foreground hover:text-red-600" title="Remove">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
