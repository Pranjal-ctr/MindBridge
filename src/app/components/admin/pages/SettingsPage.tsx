/**
 * Settings — the intelligence layer's tunable thresholds.
 *
 * These are the numbers that decide when a student is flagged: crisis trigger
 * score, the safety floors that force an acute category to override an
 * under-scored aggregate, risk band boundaries, wellness weights. All are
 * DB-first with a code fallback, so they are pilot-tunable with no deploy —
 * which is exactly why editing them needs to be deliberate.
 *
 * The editor is raw JSON on purpose. Every key has a different shape, and a
 * bespoke form per key would drift from the backend defaults the moment a new
 * key is added. What the page does provide is validation before submit, a
 * visible diff against what is currently stored, and a clear marker of whether
 * a value is a real override or still the code default.
 */

import { useCallback, useEffect, useState } from 'react';
import { RefreshCw, RotateCcw, Settings2, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import {
  apiErrorDetail,
  listPlatformConfig,
  updatePlatformConfig,
} from '../../../../lib/admin-api';
import type { PlatformConfigEntry } from '../../../../lib/admin-types';
import { Button } from '../../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import { Textarea } from '../../ui/textarea';
import { ConfirmActionDialog } from '../widgets/ConfirmActionDialog';
import { EmptyState } from '../widgets/EmptyState';
import { PageHeader } from '../widgets/PageHeader';

/** Keys where a bad value changes who gets flagged, not just cosmetics. */
const SAFETY_KEYS = new Set(['crisis', 'safety_floors', 'risk_bands']);

const KEY_HELP: Record<string, string> = {
  crisis:
    'Score at which the crisis workflow fires, and who gets notified. Raising trigger_score means fewer alerts reach counselors.',
  safety_floors:
    'A credible self-harm / suicidal-ideation / abuse score forces overall risk to at least enforced_overall, so an under-scored aggregate cannot mask acute risk.',
  risk_bands: 'Score boundaries between green, yellow, red and critical.',
  wellness_weights: 'Relative weight of each component in the wellness score.',
  parent_insight: 'How often parent insights regenerate.',
  analysis: 'Context window and smoothing for the per-message analysis.',
};

function ConfigCard({
  entry,
  onSaved,
}: {
  entry: PlatformConfigEntry;
  onSaved: () => void;
}) {
  const stored = JSON.stringify(entry.config_value, null, 2);
  const [draft, setDraft] = useState(stored);
  const [confirmOpen, setConfirmOpen] = useState(false);

  useEffect(() => setDraft(stored), [stored]);

  let parseError: string | null = null;
  let parsed: Record<string, unknown> | null = null;
  try {
    const value = JSON.parse(draft);
    if (typeof value !== 'object' || value === null || Array.isArray(value)) {
      parseError = 'Value must be a JSON object.';
    } else {
      parsed = value as Record<string, unknown>;
    }
  } catch (err) {
    parseError = err instanceof Error ? err.message : 'Invalid JSON.';
  }

  const dirty = draft !== stored;
  const isSafety = SAFETY_KEYS.has(entry.config_key);

  const save = async () => {
    if (!parsed) return;
    try {
      await updatePlatformConfig(entry.config_key, parsed);
      toast.success(`${entry.config_key} saved.`);
      onSaved();
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Could not save configuration.'));
      throw err;
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-base">
            <code>{entry.config_key}</code>
          </CardTitle>
          {isSafety && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-300">
              <ShieldAlert className="h-3 w-3" />
              safety
            </span>
          )}
          <span
            className={`rounded-full px-2 py-0.5 text-xs ${
              entry.source === 'database'
                ? 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300'
                : 'bg-muted text-muted-foreground'
            }`}
            title={
              entry.source === 'database'
                ? 'Overridden here; the code default is not in use.'
                : 'Still using the value checked into the codebase.'
            }
          >
            {entry.source === 'database' ? 'overridden' : 'code default'}
          </span>
        </div>
        <p className="text-sm text-muted-foreground">
          {KEY_HELP[entry.config_key] ?? entry.description ?? 'Platform configuration.'}
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={Math.min(16, stored.split('\n').length + 2)}
          spellCheck={false}
          className="font-mono text-xs"
          aria-label={`${entry.config_key} value`}
        />

        {parseError && (
          <p className="text-sm text-destructive">{parseError}</p>
        )}

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            disabled={!dirty || Boolean(parseError)}
            onClick={() => (isSafety ? setConfirmOpen(true) : save())}
          >
            Save
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={!dirty}
            onClick={() => setDraft(stored)}
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Revert
          </Button>
        </div>
      </CardContent>

      <ConfirmActionDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={`Change ${entry.config_key}?`}
        description={
          <>
            This changes which students get flagged, platform-wide and
            immediately. Misconfiguring it can stop acute cases reaching a
            counselor. The change is recorded in the audit log.
          </>
        }
        confirmLabel="Save"
        destructive
        onConfirm={save}
      />
    </Card>
  );
}

export function SettingsPage() {
  const [configs, setConfigs] = useState<PlatformConfigEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listPlatformConfig();
      // Safety keys first — they are the ones worth seeing.
      setConfigs(
        [...data.configs].sort(
          (a, b) =>
            Number(SAFETY_KEYS.has(b.config_key)) -
            Number(SAFETY_KEYS.has(a.config_key)),
        ),
      );
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Could not load configuration.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <PageHeader
        title="Settings"
        description="Intelligence-layer thresholds. Stored in the database, applied without a deploy."
        actions={
          <Button variant="outline" onClick={load} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        }
      />

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading configuration…</p>
      ) : configs.length === 0 ? (
        <EmptyState
          icon={Settings2}
          title="No configuration keys"
          description="Kio is running entirely on the defaults in app/intelligence/config.py."
        />
      ) : (
        <div className="space-y-4">
          {configs.map((entry) => (
            <ConfigCard key={entry.config_key} entry={entry} onSaved={load} />
          ))}
        </div>
      )}
    </>
  );
}
