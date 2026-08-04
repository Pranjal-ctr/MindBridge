/**
 * Counselor risk review queue -- pending AI/tripwire assessments awaiting
 * review. Surfaces the AI's contributors + confidence for transparency, the
 * response SLA per level, and captures the counselor's verdict (their level +
 * outcome + note) so an AI-vs-human labeled dataset accumulates. Talks to
 * /risk/queue directly.
 */

import { useState, useEffect, useCallback } from 'react';
import { AlertTriangle, CheckCircle2, ChevronDown, Eye, Loader2, ShieldAlert, Siren } from 'lucide-react';
import api from '../../lib/api';
import type { RiskOutcome, RiskQueueItem, RiskQueueListResponse, RiskReviewUpdate } from '../../lib/types';
import { slaFor, ESCALATION_STEPS } from '../../lib/risk-sla';

const LEVEL_STYLES: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  critical: { bg: 'bg-red-50', border: 'border-red-300', text: 'text-red-900', badge: 'bg-red-600 text-white' },
  red: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-900', badge: 'bg-red-500 text-white' },
  yellow: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-900', badge: 'bg-amber-500 text-white' },
  green: { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-900', badge: 'bg-emerald-500 text-white' },
};

const CATEGORY_LABELS: Record<string, string> = {
  hopelessness: 'Hopelessness', anxiety: 'Anxiety', burnout: 'Burnout', loneliness: 'Loneliness',
  bullying: 'Bullying', abuse: 'Abuse', family_conflict: 'Family conflict', self_harm: 'Self-harm',
  suicidal_ideation: 'Suicidal ideation', sleep_issues: 'Sleep issues', eating_issues: 'Eating issues',
  substance_use: 'Substance use', academic_pressure: 'Academic pressure',
};

const OUTCOMES: { value: RiskOutcome; label: string }[] = [
  { value: 'no_action_needed', label: 'No action needed' },
  { value: 'monitoring', label: 'Monitoring' },
  { value: 'counseling_scheduled', label: 'Counseling scheduled' },
  { value: 'parent_contacted', label: 'Parent contacted' },
  { value: 'escalated', label: 'Escalated' },
  { value: 'referred_external', label: 'Referred (external)' },
  { value: 'false_positive', label: 'False positive' },
];

const LEVELS: RiskReviewUpdate['counselor_risk_level'][] = ['green', 'yellow', 'red', 'critical'];

const CONTRIBUTOR_THRESHOLD = 40; // categories below this aren't meaningful contributors

/** Top contributing risk categories, most severe first. */
function contributors(categories: Record<string, number> | null): [string, number][] {
  if (!categories) return [];
  return Object.entries(categories)
    .filter(([, v]) => v >= CONTRIBUTOR_THRESHOLD)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4);
}

interface ReviewForm {
  verdict: 'agree' | 'disagree' | null;
  counselor_risk_level: RiskReviewUpdate['counselor_risk_level'];
  outcome: RiskOutcome | null;
  note: string;
}

export function RiskQueue({ onCountChange }: { onCountChange?: (count: number) => void }) {
  const [items, setItems] = useState<RiskQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [form, setForm] = useState<ReviewForm>({ verdict: null, counselor_risk_level: null, outcome: null, note: '' });
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

  const removeItem = (riskId: string) =>
    setItems((prev) => {
      const next = prev.filter((i) => i.risk_id !== riskId);
      onCountChange?.(next.length);
      return next;
    });

  // Quick acknowledge -- no verdict captured.
  const acknowledge = async (riskId: string) => {
    setBusyId(riskId);
    setError(null);
    try {
      await api.patch(`/risk/queue/${riskId}`, { review_status: 'acknowledged' } as RiskReviewUpdate);
      removeItem(riskId);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Could not update this assessment.');
    } finally {
      setBusyId(null);
    }
  };

  const openReview = (item: RiskQueueItem) => {
    if (openId === item.risk_id) { setOpenId(null); return; }
    setOpenId(item.risk_id);
    // Default the counselor's level to the AI's level so "agree" is one click.
    setForm({ verdict: null, counselor_risk_level: item.risk_level as ReviewForm['counselor_risk_level'], outcome: null, note: '' });
  };

  const resolve = async (item: RiskQueueItem) => {
    setBusyId(item.risk_id);
    setError(null);
    // Infer verdict from whether the counselor kept the AI level, if not set explicitly.
    const verdict = form.verdict ?? (form.counselor_risk_level === item.risk_level ? 'agree' : 'disagree');
    const payload: RiskReviewUpdate = {
      review_status: 'resolved',
      verdict,
      counselor_risk_level: form.counselor_risk_level,
      outcome: form.outcome,
      note: form.note.trim() || null,
    };
    try {
      await api.patch(`/risk/queue/${item.risk_id}`, payload);
      setOpenId(null);
      removeItem(item.risk_id);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Could not resolve this assessment.');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
      <div className="flex items-center justify-between mb-1">
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
      <p className="text-xs text-muted-foreground mb-4">
        AI-assisted, human-reviewed. Response targets: Critical — immediately · Red — same working day ·
        Yellow — within 48h.
      </p>

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
            const sla = slaFor(item.risk_level);
            const tops = contributors(item.categories);
            const isOpen = openId === item.risk_id;
            const busy = busyId === item.risk_id;
            return (
              <div key={item.risk_id} className={`p-4 rounded-lg border ${style.bg} ${style.border}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${style.badge}`}>
                        {item.risk_level}
                      </span>
                      <span className={`font-medium ${style.text}`}>{item.student_name}</span>
                      {item.risk_score !== null && (
                        <span className="text-xs text-muted-foreground">score {Math.round(item.risk_score)}</span>
                      )}
                      {item.inconclusive ? (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-slate-200 text-slate-700" title="Model confidence below threshold — treat as insufficient signal, not low risk.">
                          Inconclusive
                        </span>
                      ) : item.confidence !== null && (
                        <span className="text-xs text-muted-foreground">confidence {Math.round(item.confidence * 100)}%</span>
                      )}
                      <span className="text-xs text-muted-foreground">· respond: {sla.window}</span>
                    </div>

                    {item.summary && <p className={`text-sm ${style.text} opacity-90`}>{item.summary}</p>}
                    {!item.summary && item.trigger_reason && (
                      <p className={`text-sm ${style.text} opacity-90 flex items-center gap-1`}>
                        <AlertTriangle className="w-3.5 h-3.5" /> {item.trigger_reason}
                      </p>
                    )}

                    {tops.length > 0 && (
                      <div className="mt-2 flex items-center gap-1.5 flex-wrap">
                        <span className="text-xs text-muted-foreground">Contributors:</span>
                        {tops.map(([key, val]) => (
                          <span key={key} className="text-xs px-1.5 py-0.5 rounded bg-white/70 border border-current/10">
                            {CATEGORY_LABELS[key] ?? key} {Math.round(val)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => acknowledge(item.risk_id)}
                      disabled={busy}
                      className="p-2 rounded-lg bg-white hover:bg-muted transition disabled:opacity-50"
                      title="Acknowledge (mark seen)"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => openReview(item)}
                      disabled={busy}
                      className="px-3 py-2 rounded-lg bg-white hover:bg-muted transition disabled:opacity-50 text-sm font-medium flex items-center gap-1"
                      title="Review & resolve"
                    >
                      Review <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                    </button>
                  </div>
                </div>

                {sla.emergency && (
                  <div className="mt-3 flex items-start gap-2 p-2.5 rounded-lg bg-red-600/10 border border-red-300 text-red-800 text-xs">
                    <Siren className="w-4 h-4 mt-0.5 shrink-0" />
                    <div>
                      <span className="font-semibold">Emergency escalation — {sla.action}</span>
                      <ol className="mt-1 list-decimal pl-4 space-y-0.5">
                        {ESCALATION_STEPS.map((s, i) => <li key={i}>{s}</li>)}
                      </ol>
                    </div>
                  </div>
                )}

                {isOpen && (
                  <div className="mt-3 pt-3 border-t border-current/10 space-y-3">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-muted-foreground mb-1">Your assessed level</label>
                        <select
                          value={form.counselor_risk_level ?? ''}
                          onChange={(e) => setForm((f) => ({ ...f, counselor_risk_level: e.target.value as ReviewForm['counselor_risk_level'] }))}
                          className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-white capitalize"
                        >
                          {LEVELS.map((lvl) => <option key={lvl} value={lvl!}>{lvl}</option>)}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-muted-foreground mb-1">Outcome</label>
                        <select
                          value={form.outcome ?? ''}
                          onChange={(e) => setForm((f) => ({ ...f, outcome: (e.target.value || null) as RiskOutcome | null }))}
                          className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-white"
                        >
                          <option value="">Select outcome…</option>
                          {OUTCOMES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                        </select>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-muted-foreground">Agree with AI level?</span>
                      {(['agree', 'disagree'] as const).map((v) => (
                        <button
                          key={v}
                          type="button"
                          onClick={() => setForm((f) => ({ ...f, verdict: v }))}
                          className={`px-2.5 py-1 rounded-lg text-xs font-medium border capitalize transition ${
                            form.verdict === v ? 'bg-primary text-primary-foreground border-primary' : 'bg-white border-border hover:bg-muted'
                          }`}
                        >
                          {v}
                        </button>
                      ))}
                      <span className="text-[11px] text-muted-foreground">Inferred from your level if left blank.</span>
                    </div>

                    <textarea
                      value={form.note}
                      onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))}
                      placeholder="Optional notes (context, action taken)…"
                      rows={2}
                      className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-white resize-y"
                    />

                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setOpenId(null)}
                        disabled={busy}
                        className="px-3 py-2 text-sm rounded-lg hover:bg-muted transition disabled:opacity-50"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => resolve(item)}
                        disabled={busy}
                        className="px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition disabled:opacity-50 flex items-center gap-1.5"
                      >
                        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                        Resolve
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
