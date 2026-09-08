/**
 * AI Control — which model serves which feature, and which prompt is live.
 *
 * Both are DB-driven, so changing them takes effect without a deploy. That
 * cuts both ways: activating a prompt version here changes what Comrade says
 * to every student immediately, which is why activation confirms first and
 * why the page points at the Playground for testing beforehand.
 */

import { useCallback, useEffect, useState } from 'react';
import { Cpu, FlaskConical, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import {
  activatePrompt,
  apiErrorDetail,
  listAIProviders,
  listAIRoutes,
  listPrompts,
  updateAIRoute,
} from '../../../../lib/admin-api';
import type {
  AIProviderConfig,
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
  providers,
  onSave,
  saving,
}: {
  route: AIRoute;
  providers: AIProviderConfig[];
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
          {!route.is_active && <StatusBadge status="inactive" />}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Select value={provider} onValueChange={setProvider}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Provider" />
            </SelectTrigger>
            <SelectContent>
              {providers.map((p) => (
                <SelectItem key={p.provider_name} value={p.provider_name}>
                  {p.display_name}
                  {!p.is_enabled && ' (disabled)'}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-64"
            aria-label={`Model for ${route.feature_name}`}
          />

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

export function AIControlPage() {
  const [routes, setRoutes] = useState<AIRoute[]>([]);
  const [providers, setProviders] = useState<AIProviderConfig[]>([]);
  const [prompts, setPrompts] = useState<PromptVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activateTarget, setActivateTarget] = useState<PromptVersion | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r, p, pr] = await Promise.all([
        listAIRoutes(),
        listAIProviders(),
        listPrompts(),
      ]);
      setRoutes(r.routes);
      setProviders(p.providers);
      setPrompts(pr.prompts);
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

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Feature routing</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-6 text-sm text-muted-foreground">Loading…</div>
          ) : routes.length === 0 ? (
            <EmptyState
              icon={Cpu}
              title="No routes configured"
              description="Feature routes are seeded by migration 009."
            />
          ) : (
            routes.map((route) => (
              <RouteRow
                key={route.feature_name}
                route={route}
                providers={providers}
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
