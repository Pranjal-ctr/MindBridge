/**
 * Counselor risk review queue -- pending AI/tripwire assessments awaiting
 * acknowledgement or resolution. Self-contained: talks to /risk/queue directly.
 */

import { useState, useEffect, useCallback } from 'react';
import { AlertTriangle, CheckCircle2, Eye, Loader2, ShieldAlert } from 'lucide-react';
import api from '../../lib/api';
import type { RiskQueueItem, RiskQueueListResponse } from '../../lib/types';

const LEVEL_STYLES: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  critical: { bg: 'bg-red-50', border: 'border-red-300', text: 'text-red-900', badge: 'bg-red-600 text-white' },
  red: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-900', badge: 'bg-red-500 text-white' },
  yellow: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-900', badge: 'bg-amber-500 text-white' },
  green: { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-900', badge: 'bg-emerald-500 text-white' },
};

export function RiskQueue({ onCountChange }: { onCountChange?: (count: number) => void }) {
  const [items, setItems] = useState<RiskQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await api.get<RiskQueueListResponse>('/risk/queue');
      setItems(data.items);
      onCountChange?.(data.total);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [onCountChange]);

  useEffect(() => { load(); }, [load]);

  const review = async (riskId: string, status: 'acknowledged' | 'resolved') => {
    setBusyId(riskId);
    setError(null);
    try {
      await api.patch(`/risk/queue/${riskId}`, { review_status: status });
      setItems((prev) => {
        const next = prev.filter((i) => i.risk_id !== riskId);
        onCountChange?.(next.length);
        return next;
      });
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Could not update this assessment.');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-destructive" />
          Risk Review Queue
        </h2>
        {items.length > 0 && (
          <span className="px-2 py-0.5 bg-destructive text-destructive-foreground rounded-full text-xs">
            {items.length}
          </span>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        </div>
      ) : items.length === 0 ? (
        <div className="py-8 text-center text-sm text-muted-foreground">
          Nothing awaiting review right now.
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => {
            const style = LEVEL_STYLES[item.risk_level] ?? LEVEL_STYLES.yellow;
            return (
              <div key={item.risk_id} className={`p-4 rounded-lg border ${style.bg} ${style.border}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${style.badge}`}>
                        {item.risk_level}
                      </span>
                      <span className={`font-medium ${style.text}`}>{item.student_name}</span>
                      {item.risk_score !== null && (
                        <span className="text-xs text-muted-foreground">score {Math.round(item.risk_score)}</span>
                      )}
                    </div>
                    {item.summary && (
                      <p className={`text-sm ${style.text} opacity-90`}>{item.summary}</p>
                    )}
                    {!item.summary && item.trigger_reason && (
                      <p className={`text-sm ${style.text} opacity-90 flex items-center gap-1`}>
                        <AlertTriangle className="w-3.5 h-3.5" /> {item.trigger_reason}
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => review(item.risk_id, 'acknowledged')}
                      disabled={busyId === item.risk_id}
                      className="p-2 rounded-lg bg-white hover:bg-muted transition disabled:opacity-50"
                      title="Acknowledge"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => review(item.risk_id, 'resolved')}
                      disabled={busyId === item.risk_id}
                      className="p-2 rounded-lg bg-white hover:bg-muted transition disabled:opacity-50"
                      title="Resolve"
                    >
                      <CheckCircle2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
