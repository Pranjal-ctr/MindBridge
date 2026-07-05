/**
 * MindBridge AI Playground (internal, platform admin only)
 * Test model + prompt-version combinations side by side before
 * activating a prompt globally.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowLeft,
  Brain,
  CheckCircle2,
  Clock,
  Coins,
  FlaskConical,
  Loader2,
  Play,
  Plus,
  X,
} from 'lucide-react';
import api from '../../lib/api';

interface PromptVersion {
  prompt_id: string;
  prompt_name: string;
  prompt_version: string;
  prompt_content: string;
  is_active: boolean;
}

interface ProviderConfig {
  provider_name: string;
  display_name: string;
  is_enabled: boolean;
  default_model: string;
}

interface Variant {
  provider: string;
  model: string;
  prompt_version_id: string | null;
  temperature: number;
}

interface VariantResult {
  provider: string;
  model: string;
  prompt_version: string | null;
  text: string | null;
  latency_ms: number;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: number | null;
  error: string | null;
}

const KNOWN_MODELS = ['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.5-pro'];

export function AdminPlayground() {
  const [prompts, setPrompts] = useState<PromptVersion[]>([]);
  const [providers, setProviders] = useState<ProviderConfig[]>([]);
  const [message, setMessage] = useState('');
  const [variants, setVariants] = useState<Variant[]>([
    { provider: 'gemini', model: 'gemini-2.5-flash', prompt_version_id: null, temperature: 0.7 },
  ]);
  const [results, setResults] = useState<VariantResult[] | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [activating, setActivating] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    const [promptsRes, providersRes] = await Promise.all([
      api.get<{ prompts: PromptVersion[] }>('/admin/prompts'),
      api.get<{ providers: ProviderConfig[] }>('/admin/ai/providers'),
    ]);
    setPrompts(promptsRes.data.prompts);
    setProviders(providersRes.data.providers);
  }, []);

  useEffect(() => {
    loadData().catch(() => setError('Failed to load prompts/providers'));
  }, [loadData]);

  const updateVariant = (index: number, patch: Partial<Variant>) => {
    setVariants((prev) => prev.map((v, i) => (i === index ? { ...v, ...patch } : v)));
  };

  const addVariant = () => {
    if (variants.length < 3) {
      setVariants((prev) => [
        ...prev,
        { provider: 'gemini', model: 'gemini-2.5-flash', prompt_version_id: null, temperature: 0.7 },
      ]);
    }
  };

  const removeVariant = (index: number) => {
    setVariants((prev) => prev.filter((_, i) => i !== index));
  };

  const run = async () => {
    setError(null);
    setNotice(null);
    setResults(null);
    setIsRunning(true);
    try {
      const { data } = await api.post<{ results: VariantResult[] }>('/admin/ai/playground', {
        message,
        variants,
      });
      setResults(data.results);
    } catch {
      setError('Playground run failed. Check the backend logs.');
    } finally {
      setIsRunning(false);
    }
  };

  const activate = async (promptId: string) => {
    setActivating(promptId);
    setNotice(null);
    try {
      const { data } = await api.patch<PromptVersion>(`/admin/prompts/${promptId}/activate`);
      setNotice(`Activated "${data.prompt_name}" ${data.prompt_version} globally.`);
      await loadData();
    } catch {
      setError('Failed to activate prompt version');
    } finally {
      setActivating(null);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-emerald-50 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <Link to="/admin" className="text-muted-foreground hover:text-foreground transition">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <FlaskConical className="w-7 h-7 text-primary" />
            <div>
              <h1 className="text-xl font-semibold">AI Playground</h1>
              <p className="text-sm text-muted-foreground">
                Test prompts and models safely before changing them globally
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Brain className="w-4 h-4" />
            Internal — Platform Admin only
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">{error}</div>
        )}
        {notice && (
          <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-700 text-sm flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" /> {notice}
          </div>
        )}

        {/* Variant configuration */}
        <div className="grid gap-4 mb-6" style={{ gridTemplateColumns: `repeat(${variants.length}, 1fr)` }}>
          {variants.map((variant, i) => (
            <div key={i} className="bg-white rounded-2xl border border-border p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold">Variant {String.fromCharCode(65 + i)}</span>
                {variants.length > 1 && (
                  <button onClick={() => removeVariant(i)} className="text-muted-foreground hover:text-red-500">
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">Provider</label>
                <select
                  value={variant.provider}
                  onChange={(e) => updateVariant(i, { provider: e.target.value })}
                  className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-input-background"
                >
                  {(providers.length ? providers : [{ provider_name: 'gemini', display_name: 'Google Gemini', is_enabled: true, default_model: 'gemini-2.5-flash' }]).map((p) => (
                    <option key={p.provider_name} value={p.provider_name} disabled={!p.is_enabled}>
                      {p.display_name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">Model</label>
                <select
                  value={variant.model}
                  onChange={(e) => updateVariant(i, { model: e.target.value })}
                  className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-input-background"
                >
                  {KNOWN_MODELS.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">Prompt version</label>
                <select
                  value={variant.prompt_version_id ?? ''}
                  onChange={(e) => updateVariant(i, { prompt_version_id: e.target.value || null })}
                  className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-input-background"
                >
                  <option value="">Built-in fallback (v1)</option>
                  {prompts.map((p) => (
                    <option key={p.prompt_id} value={p.prompt_id}>
                      {p.prompt_name} {p.prompt_version} {p.is_active ? '● active' : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">
                  Temperature: {variant.temperature.toFixed(1)}
                </label>
                <input
                  type="range"
                  min={0}
                  max={2}
                  step={0.1}
                  value={variant.temperature}
                  onChange={(e) => updateVariant(i, { temperature: parseFloat(e.target.value) })}
                  className="w-full"
                />
              </div>
            </div>
          ))}
        </div>

        {variants.length < 3 && (
          <button
            onClick={addVariant}
            className="mb-6 flex items-center gap-2 text-sm text-primary hover:underline"
          >
            <Plus className="w-4 h-4" /> Add variant to compare ({variants.length}/3)
          </button>
        )}

        {/* Test message */}
        <div className="bg-white rounded-2xl border border-border p-4 mb-6">
          <label className="text-sm font-medium block mb-2">Test message (as a student would send it)</label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={3}
            maxLength={4000}
            placeholder="e.g. I have three exams next week and I can't focus. What should I do?"
            className="w-full px-4 py-3 border border-border rounded-xl text-sm bg-input-background focus:outline-none focus:ring-2 focus:ring-ring resize-none"
          />
          <div className="flex justify-end mt-3">
            <button
              onClick={run}
              disabled={!message.trim() || isRunning}
              className="flex items-center gap-2 px-5 py-2.5 bg-primary text-white rounded-xl text-sm font-medium disabled:opacity-50 hover:bg-primary/90 transition"
            >
              {isRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              {isRunning ? 'Running…' : `Run ${variants.length > 1 ? `${variants.length} variants` : 'test'}`}
            </button>
          </div>
        </div>

        {/* Results */}
        {results && (
          <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${results.length}, 1fr)` }}>
            {results.map((r, i) => (
              <div key={i} className="bg-white rounded-2xl border border-border p-4 flex flex-col">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-semibold">Variant {String.fromCharCode(65 + i)}</span>
                  <span className="text-xs text-muted-foreground">{r.model}</span>
                </div>

                <div className="flex items-center gap-4 text-xs text-muted-foreground mb-3">
                  <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{r.latency_ms} ms</span>
                  {r.input_tokens != null && <span>{r.input_tokens}→{r.output_tokens} tok</span>}
                  {r.estimated_cost_usd != null && (
                    <span className="flex items-center gap-1">
                      <Coins className="w-3 h-3" />${r.estimated_cost_usd.toFixed(6)}
                    </span>
                  )}
                </div>

                {r.error ? (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">{r.error}</div>
                ) : (
                  <div className="p-3 bg-slate-50 rounded-xl text-sm whitespace-pre-wrap flex-1">{r.text}</div>
                )}

                {(() => {
                  const variantPromptId = variants[i]?.prompt_version_id;
                  const prompt = prompts.find((p) => p.prompt_id === variantPromptId);
                  if (!prompt || prompt.is_active || r.error) return null;
                  return (
                    <button
                      onClick={() => activate(prompt.prompt_id)}
                      disabled={activating !== null}
                      className="mt-3 flex items-center justify-center gap-2 px-4 py-2 border-2 border-primary text-primary rounded-xl text-sm font-medium hover:bg-blue-50 transition disabled:opacity-50"
                    >
                      {activating === prompt.prompt_id
                        ? <Loader2 className="w-4 h-4 animate-spin" />
                        : <CheckCircle2 className="w-4 h-4" />}
                      Activate {prompt.prompt_version} globally
                    </button>
                  );
                })()}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
