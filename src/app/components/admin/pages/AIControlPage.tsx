/**
 * AI Control — which model serves which feature, and which prompt is live.
 *
 * Both are DB-driven, so changing them takes effect without a deploy. That
 * cuts both ways: activating a prompt version here changes what Comrade says
 * to every student immediately, which is why activation confirms first and
 * why the page points at the Playground for testing beforehand.
 */

import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Check, Cpu, FlaskConical, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import {
  activatePrompt,
  apiErrorDetail,
  getAIConfig,
  listAIRoutes,
  listPrompts,
  updateAIConfig,
  updateAIRoute,
} from '../../../../lib/admin-api';
import type {
  AIConfig,
  AIProviderHealth,
  AIProviderOption,
  AIRoute,
  PromptVersion,
} from '../../../../lib/admin-types';
import { Button } from '../../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import { Input } from '../../ui/input';
import { Switch } from '../../ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../ui/select';
import { ConfirmActionDialog } from '../widgets/ConfirmActionDialog';
import { EmptyState } from '../widgets/EmptyState';
import { PageHeader } from '../widgets/PageHeader';
import { StatusBadge } from '../widgets/StatusBadge';

/** Plain-language names for the internal feature keys. */
const FEATURE_LABELS: Record<string, string> = {
  comrade_chat: 'Comrade chat',
  memory_extraction: 'Memory extraction',
  title_generation: 'Conversation titles',
  risk_detection: 'Risk detection',
  parent_insight: 'Parent insights',
  weekly_report: 'Weekly reports',
  activities: 'Activity suggestions',
};

/** Features where a model change carries safety weight, not just cost. */
const SAFETY_CRITICAL = new Set(['comrade_chat', 'risk_detection']);

function RouteRow({
  route,
  registry,
  onSave,
  saving,
}: {
  route: AIRoute;
  /** Supported provider/model pairs from the backend. */
  registry: AIProviderOption[];
  onSave: (feature: string, model: string, provider: string, active: boolean) => void;
  saving: boolean;
}) {
  const [provider, setProvider] = useState(route.primary_provider);
  const [model, setModel] = useState(route.primary_model);

  // Re-sync when the parent reloads after a save elsewhere on the page.
  useEffect(() => {
    setProvider(route.primary_provider);
    setModel(route.primary_model);
  }, [route.primary_provider, route.primary_model]);

  const dirty = provider !== route.primary_provider || model !== route.primary_model;

  return (
    <div className="grid gap-3 border-b p-4 last:border-0 sm:grid-cols-[1fr_auto]">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">
            {FEATURE_LABELS[route.feature_name] ?? route.feature_name}
          </span>
          <code className="text-xs text-muted-foreground">{route.feature_name}</code>
          {SAFETY_CRITICAL.has(route.feature_name) && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-300">
              safety-critical
            </span>
          )}
          {route.is_active ? (
            <span className="rounded-full bg-sky-100 px-2 py-0.5 text-xs text-sky-900 dark:bg-sky-950 dark:text-sky-200">
              Override
            </span>
          ) : (
            <span className="text-xs text-muted-foreground">
              Uses platform default
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={provider}
            onValueChange={(v) => {
              // Changing provider invalidates the model, so move to that
              // provider's first supported one rather than leaving a pair
              // the server would reject.
              setProvider(v);
              const first = registry.find((p) => p.provider_id === v)?.models[0];
              setModel(first ? first.model_id : '');
            }}
          >
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Provider" />
            </SelectTrigger>
            <SelectContent>
              {registry.map((p) => (
                <SelectItem
                  key={p.provider_id}
                  value={p.provider_id}
                  disabled={!p.credential_configured}
                >
                  {p.display_name}
                  {!p.credential_configured && ' — no credentials'}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* A dropdown, not a text field: an override may only name a model
              this build supports, and a typo here would point a possibly
              safety-critical feature at a model that does not exist. */}
          <Select value={model} onValueChange={setModel}>
            <SelectTrigger className="w-64" aria-label={`Model for ${route.feature_name}`}>
              <SelectValue placeholder="Model" />
            </SelectTrigger>
            <SelectContent>
              {(registry.find((p) => p.provider_id === provider)?.models ?? []).map((m) => (
                <SelectItem key={m.model_id} value={m.model_id}>
                  {m.display_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {route.fallback_model && (
            <span className="text-xs text-muted-foreground">
              fallback: {route.fallback_model}
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 sm:justify-end">
        <Switch
          checked={route.is_active}
          disabled={saving}
          onCheckedChange={(checked) =>
            onSave(route.feature_name, route.primary_model, route.primary_provider, checked)
          }
          aria-label={`${route.feature_name} active`}
        />
        <Button
          size="sm"
          disabled={!dirty || saving}
          onClick={() => onSave(route.feature_name, model, provider, route.is_active)}
        >
          Save
        </Button>
      </div>
    </div>
  );
}

/** Human-readable provider status, from telemetry rather than a probe call. */
const STATUS_LABEL: Record<string, string> = {
  configured: 'Configured',
  credentials_missing: 'Credentials unavailable',
  recently_successful: 'Healthy',
  recently_failing: 'Recent failures',
  cooling_down: 'Cooling down',
  unused: 'Unused',
};

function HealthLine({ health, provider }: { health?: AIProviderHealth; provider: AIProviderOption }) {
  if (!health) return null;
  const missing = !health.credential_configured;
  const bad = health.status === 'recently_failing' || health.status === 'cooling_down';

  return (
    <div className="flex items-center gap-2 text-xs">
      {missing || bad ? (
        <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
      ) : (
        <Check className="h-3.5 w-3.5 text-emerald-600" />
      )}
      <span className={missing || bad ? 'text-amber-700 dark:text-amber-400' : 'text-muted-foreground'}>
        {provider.display_name}: {STATUS_LABEL[health.status] ?? health.status}
      </span>
      {missing && (
        // The variable NAME, so an operator knows what to set. Never a value.
        <code className="text-muted-foreground">{provider.credential_setting}</code>
      )}
      {health.status === 'recently_failing' && health.last_failure_category && (
        <span className="text-muted-foreground">({health.last_failure_category})</span>
      )}
      {health.circuit_open && (
        <span className="text-muted-foreground">
          retrying in {health.cooldown_remaining_seconds}s
        </span>
      )}
    </div>
  );
}

/**
 * Platform AI configuration — which supported provider/model serves everything.
 *
 * Both dropdowns are fed from the backend registry, so a model name can only
 * ever be one this build actually supports. There is deliberately no free-text
 * model field: `risk_detection` asks a model whether a teenager is in danger,
 * and "whatever string someone pasted into a box" is not an acceptable answer
 * to which model made that call.
 *
 * A provider whose API key is absent from the server cannot be selected. The
 * server enforces that too — this only avoids offering a choice that would be
 * rejected.
 */
function PlatformConfigCard({
  config,
  onSave,
  saving,
}: {
  config: AIConfig;
  onSave: (payload: {
    primary_provider: string;
    primary_model: string;
    fallback_provider: string | null;
    fallback_model: string | null;
    fallback_enabled: boolean;
  }) => void;
  saving: boolean;
}) {
  const [primaryProvider, setPrimaryProvider] = useState(config.primary_provider);
  const [primaryModel, setPrimaryModel] = useState(config.primary_model);
  const [fallbackEnabled, setFallbackEnabled] = useState(config.fallback_enabled);
  const [fallbackProvider, setFallbackProvider] = useState(
    config.fallback_provider ?? '',
  );
  const [fallbackModel, setFallbackModel] = useState(config.fallback_model ?? '');

  useEffect(() => {
    setPrimaryProvider(config.primary_provider);
    setPrimaryModel(config.primary_model);
    setFallbackEnabled(config.fallback_enabled);
    setFallbackProvider(config.fallback_provider ?? '');
    setFallbackModel(config.fallback_model ?? '');
  }, [config]);

  const byId = (id: string) => config.providers.find((p) => p.provider_id === id);
  const healthFor = (id: string) => config.health.find((h) => h.provider_id === id);

  // Changing provider invalidates the model, so pick that provider's first.
  const pickProvider = (
    id: string,
    setProvider: (v: string) => void,
    setModel: (v: string) => void,
  ) => {
    setProvider(id);
    const first = byId(id)?.models[0];
    setModel(first ? first.model_id : '');
  };

  const dirty =
    primaryProvider !== config.primary_provider ||
    primaryModel !== config.primary_model ||
    fallbackEnabled !== config.fallback_enabled ||
    (fallbackProvider || null) !== config.fallback_provider ||
    (fallbackModel || null) !== config.fallback_model;

  const primaryUsable = byId(primaryProvider)?.credential_configured ?? false;
  const fallbackUsable =
    !fallbackEnabled || (byId(fallbackProvider)?.credential_configured ?? false);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Platform AI configuration</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <p className="text-sm text-muted-foreground">
          The provider and model every AI feature uses, unless a feature below
          has its own override. Saving takes effect for new requests
          immediately — no deploy, no restart, and nobody is signed out.
        </p>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm font-medium">Primary provider</label>
            <Select
              value={primaryProvider}
              onValueChange={(v) => pickProvider(v, setPrimaryProvider, setPrimaryModel)}
            >
              <SelectTrigger aria-label="Primary provider">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {config.providers.map((p) => (
                  <SelectItem
                    key={p.provider_id}
                    value={p.provider_id}
                    disabled={!p.credential_configured}
                  >
                    {p.display_name}
                    {!p.credential_configured && ' — no credentials'}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Primary model</label>
            <Select value={primaryModel} onValueChange={setPrimaryModel}>
              <SelectTrigger aria-label="Primary model">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(byId(primaryProvider)?.models ?? []).map((m) => (
                  <SelectItem key={m.model_id} value={m.model_id}>
                    {m.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="space-y-3 rounded-lg border p-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="text-sm font-medium">Fallback provider</div>
              <p className="text-xs text-muted-foreground">
                Used only when the primary fails with a transient error — a
                timeout or an outage. A rate limit or a bad credential does not
                fail over, so a throttle cannot quietly become a second bill.
              </p>
            </div>
            <Switch
              checked={fallbackEnabled}
              onCheckedChange={setFallbackEnabled}
              aria-label="Fallback enabled"
            />
          </div>

          {fallbackEnabled && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Select
                value={fallbackProvider}
                onValueChange={(v) =>
                  pickProvider(v, setFallbackProvider, setFallbackModel)
                }
              >
                <SelectTrigger aria-label="Fallback provider">
                  <SelectValue placeholder="Provider" />
                </SelectTrigger>
                <SelectContent>
                  {config.providers.map((p) => (
                    <SelectItem
                      key={p.provider_id}
                      value={p.provider_id}
                      disabled={!p.credential_configured}
                    >
                      {p.display_name}
                      {!p.credential_configured && ' — no credentials'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={fallbackModel} onValueChange={setFallbackModel}>
                <SelectTrigger aria-label="Fallback model">
                  <SelectValue placeholder="Model" />
                </SelectTrigger>
                <SelectContent>
                  {(byId(fallbackProvider)?.models ?? []).map((m) => (
                    <SelectItem key={m.model_id} value={m.model_id}>
                      {m.display_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>

        <div className="space-y-1">
          {config.providers.map((p) => (
            <HealthLine key={p.provider_id} provider={p} health={healthFor(p.provider_id)} />
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">
            {config.source === 'environment'
              ? 'Using server defaults — no override saved yet.'
              : `Last changed ${
                  config.updated_at ? new Date(config.updated_at).toLocaleString() : '—'
                }${config.updated_by_name ? ` by ${config.updated_by_name}` : ''}`}
          </p>
          <Button
            disabled={!dirty || saving || !primaryUsable || !fallbackUsable}
            onClick={() =>
              onSave({
                primary_provider: primaryProvider,
                primary_model: primaryModel,
                fallback_provider: fallbackEnabled ? fallbackProvider : null,
                fallback_model: fallbackEnabled ? fallbackModel : null,
                fallback_enabled: fallbackEnabled,
              })
            }
          >
            {saving ? 'Saving…' : 'Save configuration'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}


export function AIControlPage() {
  const [routes, setRoutes] = useState<AIRoute[]>([]);
  const [aiConfig, setAIConfig] = useState<AIConfig | null>(null);
  const [prompts, setPrompts] = useState<PromptVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activateTarget, setActivateTarget] = useState<PromptVersion | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r, pr, cfg] = await Promise.all([
        listAIRoutes(),
        listPrompts(),
        getAIConfig(),
      ]);
      setRoutes(r.routes);
      setPrompts(pr.prompts);
      setAIConfig(cfg);
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Could not load AI configuration.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleSaveRoute = async (
    feature: string,
    model: string,
    provider: string,
    active: boolean,
  ) => {
    setSaving(true);
    try {
      await updateAIRoute(feature, {
        primary_model: model,
        primary_provider: provider,
        is_active: active,
      });
      toast.success(`${FEATURE_LABELS[feature] ?? feature} updated.`);
      load();
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Could not update routing.'));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveConfig = async (payload: {
    primary_provider: string;
    primary_model: string;
    fallback_provider: string | null;
    fallback_model: string | null;
    fallback_enabled: boolean;
  }) => {
    setSaving(true);
    try {
      const updated = await updateAIConfig(payload);
      setAIConfig(updated);
      toast.success('AI configuration saved. New requests use it immediately.');
      load();
    } catch (err) {
      // A rejected change leaves the current configuration untouched and
      // serving traffic, so there is nothing to roll back in the UI.
      toast.error(apiErrorDetail(err, 'Could not save AI configuration.'));
    } finally {
      setSaving(false);
    }
  };

  const handleActivate = async (prompt: PromptVersion) => {
    try {
      await activatePrompt(prompt.prompt_id);
      toast.success(`${prompt.prompt_name} ${prompt.prompt_version} is now live.`);
      load();
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Could not activate prompt.'));
      throw err; // keep the confirm dialog open
    } finally {
      setActivateTarget(null);
    }
  };

  // Group versions under their prompt so "which one is live" is obvious.
  const promptGroups = prompts.reduce<Record<string, PromptVersion[]>>((acc, p) => {
    (acc[p.prompt_name] ??= []).push(p);
    return acc;
  }, {});

  return (
    <>
      <PageHeader
        title="AI Control"
        description="Model routing and prompt versions. Changes are live immediately — no deploy."
        actions={
          <div className="flex gap-2">
            <Button asChild variant="outline">
              <Link to="/admin/playground">
                <FlaskConical className="h-4 w-4" />
                Playground
              </Link>
            </Button>
            <Button variant="outline" onClick={load} disabled={loading}>
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        }
      />

      {aiConfig && (
        <PlatformConfigCard
          config={aiConfig}
          onSave={handleSaveConfig}
          saving={saving}
        />
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Feature overrides</CardTitle>
          <p className="text-sm text-muted-foreground">
            Features without an override follow the platform configuration
            above. Turn one on only to pin a feature to a different model —
            an active override means a platform change will not apply to it.
          </p>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-6 text-sm text-muted-foreground">Loading…</div>
          ) : routes.length === 0 ? (
            <EmptyState
              icon={Cpu}
              title="No routes configured"
              description="All features follow the platform configuration above."
            />
          ) : (
            routes.map((route) => (
              <RouteRow
                key={route.feature_name}
                route={route}
                registry={aiConfig?.providers ?? []}
                onSave={handleSaveRoute}
                saving={saving}
              />
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Prompt versions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : Object.keys(promptGroups).length === 0 ? (
            <EmptyState
              icon={Cpu}
              title="No prompt versions stored"
              description="Kio is running on the prompt checked into app/ai/prompts.py."
            />
          ) : (
            Object.entries(promptGroups).map(([name, versions]) => (
              <div key={name} className="space-y-2">
                <h3 className="text-sm font-medium">{name}</h3>
                <div className="divide-y rounded-lg border">
                  {versions.map((v) => (
                    <div
                      key={v.prompt_id}
                      className="flex flex-wrap items-center gap-3 p-3"
                    >
                      <code className="text-sm">{v.prompt_version}</code>
                      {v.is_active ? (
                        <StatusBadge status="active" label="Live" />
                      ) : (
                        <span className="text-xs text-muted-foreground">Inactive</span>
                      )}
                      <span className="text-xs text-muted-foreground">
                        {new Date(v.created_at).toLocaleDateString()}
                      </span>
                      {!v.is_active && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="ml-auto"
                          onClick={() => setActivateTarget(v)}
                        >
                          Make live
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <ConfirmActionDialog
        open={activateTarget !== null}
        onOpenChange={(open) => !open && setActivateTarget(null)}
        title="Make this prompt live?"
        description={
          <>
            <strong>
              {activateTarget?.prompt_name} {activateTarget?.prompt_version}
            </strong>{' '}
            will immediately govern what Comrade says to every student on the
            platform, and the currently live version will be deactivated. Test it in
            the Playground first if you have not already.
          </>
        }
        confirmLabel="Make live"
        onConfirm={async () => {
          if (activateTarget) await handleActivate(activateTarget);
        }}
      />
    </>
  );
}
