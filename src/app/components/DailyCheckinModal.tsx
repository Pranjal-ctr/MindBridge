/**
 * Mood check-in modal.
 *
 * `mode="initial"` — mandatory, full-screen, non-dismissible: shown after
 * login whenever no check-in exists in the current 12-hour window.
 * `mode="update"` — the one allowed mood update in the same window; this
 * variant can be closed without submitting.
 */

import { useState } from 'react';
import { Loader2, Sparkles, X } from 'lucide-react';
import { KioLogo } from './KioLogo';
import api from '../../lib/api';
import { MOOD_META, MOOD_ORDER } from '../../lib/mood';
import type {
  CheckinReason,
  DailyCheckinResponse,
  DailyMood,
} from '../../lib/types';

const REASONS: { value: CheckinReason; label: string }[] = [
  { value: 'academics', label: 'Academics' },
  { value: 'family', label: 'Family' },
  { value: 'friends', label: 'Friends' },
  { value: 'relationship', label: 'Relationship' },
  { value: 'health', label: 'Health' },
  { value: 'career', label: 'Career' },
  { value: 'sports', label: 'Sports' },
  { value: 'financial', label: 'Financial' },
  { value: 'social_media', label: 'Social Media' },
  { value: 'other', label: 'Other' },
];

interface DailyCheckinModalProps {
  onComplete: () => void;
  mode?: 'initial' | 'update';
  onClose?: () => void;
}

export function DailyCheckinModal({ onComplete, mode = 'initial', onClose }: DailyCheckinModalProps) {
  const [mood, setMood] = useState<DailyMood | null>(null);
  const [reason, setReason] = useState<CheckinReason | null>(null);
  const [reflection, setReflection] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isUpdate = mode === 'update';
  const canSubmit = mood !== null && reason !== null && !isSubmitting;

  const handleSubmit = async () => {
    if (!canSubmit || !mood || !reason) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await api.post<DailyCheckinResponse>('/wellness/checkin', {
        mood,
        reason,
        reflection: reflection.trim() || null,
      });
      setIsDone(true);
      setTimeout(onComplete, 1200);
    } catch (err: any) {
      if (err?.response?.status === 409) {
        // Window exhausted (e.g. another tab) — just proceed
        onComplete();
        return;
      }
      setError('Could not save your check-in. Please try again.');
      setIsSubmitting(false);
    }
  };

  const today = new Date().toLocaleDateString(undefined, {
    weekday: 'long', month: 'long', day: 'numeric',
  });

  return (
    <div className="fixed inset-0 z-50 bg-gradient-to-br from-indigo-50 via-white to-teal-50 flex items-center justify-center p-4 overflow-y-auto">
      <div className="w-full max-w-lg">
        <div className="bg-white rounded-2xl shadow-xl border border-border overflow-hidden">
          {/* Header */}
          <div className="bg-gradient-to-r from-primary to-secondary p-6 text-white">
            <div className="flex items-center justify-between mb-3">
              <KioLogo className="h-7 w-auto" reverse />
              <div className="flex items-center gap-3">
                <span className="text-xs text-blue-100">{today}</span>
                {isUpdate && onClose && (
                  <button
                    onClick={onClose}
                    className="p-1 rounded-lg hover:bg-white/15 transition"
                    aria-label="Close"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
            <h1 className="text-xl font-semibold">
              {isUpdate ? 'Update your mood' : 'Mood check-in'}
            </h1>
            <p className="text-blue-100 text-sm mt-1">
              {isUpdate
                ? 'Feelings change — tell us how it is now. This is your one update for this session.'
                : 'A quick moment for yourself before you start. This stays private.'}
            </p>
          </div>

          {isDone ? (
            <div className="p-10 text-center">
              <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-accent/15 flex items-center justify-center">
                <Sparkles className="w-7 h-7 text-accent" />
              </div>
              <h2 className="text-lg font-semibold mb-1">
                {isUpdate ? 'Mood updated' : 'Thanks for checking in'}
              </h2>
              <p className="text-sm text-muted-foreground">See you on your dashboard…</p>
            </div>
          ) : (
            <div className="p-6 space-y-6">
              {/* Mood */}
              <div>
                <div className="text-sm font-medium mb-3">
                  How are you feeling right now? <span className="text-red-500">*</span>
                </div>
                <div className="grid grid-cols-5 gap-2">
                  {MOOD_ORDER.map((value) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setMood(value)}
                      className={`flex flex-col items-center gap-1.5 py-3 px-1 rounded-xl border-2 transition ${
                        mood === value
                          ? 'border-primary bg-primary/5 shadow-sm'
                          : 'border-border hover:border-primary/40 bg-white'
                      }`}
                    >
                      <span className="text-2xl leading-none">{MOOD_META[value].emoji}</span>
                      <span className="text-[11px] text-center leading-tight text-muted-foreground">
                        {MOOD_META[value].label}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Reason */}
              <div>
                <div className="text-sm font-medium mb-3">
                  What's the main thing on your mind? <span className="text-red-500">*</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {REASONS.map((r) => (
                    <button
                      key={r.value}
                      type="button"
                      onClick={() => setReason(r.value)}
                      className={`px-3.5 py-1.5 rounded-full text-sm border transition ${
                        reason === r.value
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'border-border text-foreground hover:border-primary/40 bg-white'
                      }`}
                    >
                      {r.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Reflection */}
              <div>
                <div className="text-sm font-medium mb-2">
                  What's making you feel this way? <span className="text-muted-foreground font-normal">(optional)</span>
                </div>
                <textarea
                  value={reflection}
                  onChange={(e) => setReflection(e.target.value)}
                  rows={3}
                  maxLength={2000}
                  placeholder="A sentence or two, just for you…"
                  className="w-full px-4 py-3 bg-input-background rounded-xl border border-border focus:outline-none focus:ring-2 focus:ring-ring text-sm resize-none"
                />
              </div>

              {error && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
                  {error}
                </div>
              )}

              <button
                onClick={handleSubmit}
                disabled={!canSubmit}
                className="w-full py-3 bg-primary text-primary-foreground rounded-xl font-medium hover:bg-primary/90 transition disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
                {isUpdate ? 'Update mood' : 'Complete check-in'}
              </button>
              <p className="text-xs text-muted-foreground text-center -mt-2">
                {isUpdate
                  ? 'This will replace your current mood for this session.'
                  : 'You can update your mood once more before the next check-in window.'}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
