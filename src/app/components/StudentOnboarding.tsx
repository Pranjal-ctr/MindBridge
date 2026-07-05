/**
 * Student first-login onboarding wizard (max 5 questions).
 * Shown once, after the first successful login, when GET /onboarding is null.
 * Responses feed AI personalization (injected into the Comrade system prompt).
 */

import { useState } from 'react';
import { Brain, Check, Loader2, ArrowRight, ArrowLeft, Sparkles } from 'lucide-react';
import api from '../../lib/api';
import type { OnboardingSubmit } from '../../lib/types';

const CLASS_OPTIONS = ['Class 8', 'Class 9', 'Class 10', 'Class 11', 'Class 12', 'College'];

const HELP_OPTIONS = [
  'Improve Grades', 'Study Habits', 'Exam Stress', 'Career Guidance', 'Confidence',
  'Friendships', 'Mental Wellbeing', 'Communication Skills', 'Motivation', 'Time Management', 'Other',
];

const HOBBY_OPTIONS = [
  'Music', 'Sports', 'Gaming', 'Coding', 'Reading', 'Writing', 'Drawing',
  'Photography', 'Dance', 'Travel', 'Movies', 'Fitness', 'Other',
];

const STRENGTH_OPTIONS = [
  'Mathematics', 'Science', 'Programming', 'Leadership', 'Helping Others', 'Creativity',
  'Music', 'Writing', 'Sports', 'Public Speaking', 'Problem Solving', 'Other',
];

const STYLE_OPTIONS = [
  { value: 'Friendly Friend', desc: 'Warm, casual, like a close friend' },
  { value: 'Mentor', desc: 'Guiding and wise' },
  { value: 'Older Sibling', desc: 'Supportive and relatable' },
  { value: 'Professional Coach', desc: 'Structured and goal-focused' },
  { value: 'Calm Listener', desc: 'Gentle and patient' },
  { value: 'Motivational', desc: 'Energetic and encouraging' },
];

export function StudentOnboarding({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState(0);
  const [classLevel, setClassLevel] = useState<string | null>(null);
  const [helpGoals, setHelpGoals] = useState<string[]>([]);
  const [hobbies, setHobbies] = useState<string[]>([]);
  const [strengths, setStrengths] = useState<string[]>([]);
  const [style, setStyle] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggle = (list: string[], setList: (v: string[]) => void, value: string) => {
    setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  };

  const steps = [
    { title: 'Which class are you studying in?', canNext: !!classLevel },
    { title: 'What would you like Comrade to help you with?', canNext: helpGoals.length > 0 },
    { title: 'What are your hobbies?', canNext: hobbies.length > 0 },
    { title: 'What are your strengths?', canNext: strengths.length > 0 },
    { title: 'How should Comrade interact with you?', canNext: !!style },
  ];

  const isLast = step === steps.length - 1;

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: OnboardingSubmit = {
        class_level: classLevel || '',
        help_goals: helpGoals,
        hobbies,
        strengths,
        interaction_style: style || '',
      };
      await api.post('/onboarding/', payload);
      onComplete();
    } catch {
      setError('Could not save your answers. Please try again.');
      setSaving(false);
    }
  };

  const Chip = ({ value, selected, onClick }: { value: string; selected: boolean; onClick: () => void }) => (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-2.5 rounded-xl border-2 text-sm font-medium transition text-left ${
        selected
          ? 'border-primary bg-blue-50 text-primary'
          : 'border-border bg-card text-muted-foreground hover:border-primary/50'
      }`}
    >
      <span className="flex items-center gap-2">
        {selected && <Check className="w-4 h-4 shrink-0" />}
        {value}
      </span>
    </button>
  );

  return (
    <div className="fixed inset-0 z-50 bg-gradient-to-br from-blue-50 via-white to-emerald-50 flex items-center justify-center p-4 overflow-y-auto">
      <div className="w-full max-w-2xl my-8">
        <div className="bg-white rounded-3xl shadow-xl border border-border overflow-hidden">
          {/* Header + progress */}
          <div className="bg-gradient-to-r from-primary to-secondary p-6 text-white">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
                <Brain className="w-6 h-6" />
              </div>
              <div>
                <div className="flex items-center gap-2 font-semibold">
                  <Sparkles className="w-4 h-4" /> Let's set up Comrade for you
                </div>
                <p className="text-blue-100 text-sm">This helps me support you better — takes under a minute.</p>
              </div>
            </div>
            <div className="flex gap-1.5">
              {steps.map((_, i) => (
                <div key={i} className={`h-1.5 flex-1 rounded-full ${i <= step ? 'bg-white' : 'bg-white/30'}`} />
              ))}
            </div>
          </div>

          <div className="p-6 md:p-8">
            <div className="text-xs font-medium text-muted-foreground mb-1">
              Question {step + 1} of {steps.length}
            </div>
            <h2 className="text-xl font-semibold mb-5">{steps[step].title}</h2>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">{error}</div>
            )}

            {/* Step 0: class (single) */}
            {step === 0 && (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {CLASS_OPTIONS.map((c) => (
                  <Chip key={c} value={c} selected={classLevel === c} onClick={() => setClassLevel(c)} />
                ))}
              </div>
            )}

            {/* Step 1: help goals (multi) */}
            {step === 1 && (
              <div className="grid grid-cols-2 gap-3">
                {HELP_OPTIONS.map((o) => (
                  <Chip key={o} value={o} selected={helpGoals.includes(o)} onClick={() => toggle(helpGoals, setHelpGoals, o)} />
                ))}
              </div>
            )}

            {/* Step 2: hobbies (multi) */}
            {step === 2 && (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {HOBBY_OPTIONS.map((o) => (
                  <Chip key={o} value={o} selected={hobbies.includes(o)} onClick={() => toggle(hobbies, setHobbies, o)} />
                ))}
              </div>
            )}

            {/* Step 3: strengths (multi) */}
            {step === 3 && (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {STRENGTH_OPTIONS.map((o) => (
                  <Chip key={o} value={o} selected={strengths.includes(o)} onClick={() => toggle(strengths, setStrengths, o)} />
                ))}
              </div>
            )}

            {/* Step 4: interaction style (single) */}
            {step === 4 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {STYLE_OPTIONS.map((s) => (
                  <button
                    key={s.value}
                    type="button"
                    onClick={() => setStyle(s.value)}
                    className={`p-4 rounded-xl border-2 text-left transition ${
                      style === s.value ? 'border-primary bg-blue-50' : 'border-border hover:border-primary/50'
                    }`}
                  >
                    <div className="font-medium text-sm flex items-center gap-2">
                      {style === s.value && <Check className="w-4 h-4 text-primary" />}
                      {s.value}
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5">{s.desc}</div>
                  </button>
                ))}
              </div>
            )}

            {/* Nav */}
            <div className="flex items-center justify-between mt-8">
              <button
                type="button"
                onClick={() => setStep((s) => Math.max(0, s - 1))}
                disabled={step === 0}
                className="flex items-center gap-1 px-4 py-2 text-sm text-muted-foreground disabled:opacity-0"
              >
                <ArrowLeft className="w-4 h-4" /> Back
              </button>

              {isLast ? (
                <button
                  type="button"
                  onClick={submit}
                  disabled={!steps[step].canNext || saving}
                  className="flex items-center gap-2 px-6 py-2.5 bg-primary text-white rounded-xl text-sm font-medium disabled:opacity-50 hover:bg-primary/90 transition"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                  Finish
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => setStep((s) => s + 1)}
                  disabled={!steps[step].canNext}
                  className="flex items-center gap-2 px-6 py-2.5 bg-primary text-white rounded-xl text-sm font-medium disabled:opacity-50 hover:bg-primary/90 transition"
                >
                  Next <ArrowRight className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
