/**
 * Risk Incident detail — one assessment, in full, read-only.
 *
 * Shows the AI's assessment and the counselor's recorded verdict side by side.
 * That pairing is the point: migration 014 captures the human judgment next to
 * the model's so agreement can be measured, and this is the only place the two
 * are visible together.
 *
 * What it deliberately does NOT show is the student's conversation. Reading
 * message content is break-glass access with its own audit-logged endpoint,
 * and routing it through a risk page would quietly turn oversight into
 * surveillance.
 */

import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, Loader2, ShieldAlert } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { apiErrorDetail, getAdminRiskDetail } from '../../../../lib/admin-api';
import type { AdminRiskDetail } from '../../../../lib/admin-types';
import { slaFor } from '../../../../lib/risk-sla';
import { Button } from '../../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import { EmptyState } from '../widgets/EmptyState';
import { PageHeader } from '../widgets/PageHeader';
import { StatusBadge } from '../widgets/StatusBadge';

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-sm">{children}</dd>
    </div>
  );
}

/** Category scores, strongest first — this is what drove the level. */
function Categories({ categories }: { categories: Record<string, number> | null }) {
  const entries = Object.entries(categories ?? {})
    .filter(([, v]) => typeof v === 'number' && v > 0)
    .sort((a, b) => b[1] - a[1]);

  if (entries.length === 0) {
    return <p className="text-sm text-muted-foreground">No category scores recorded.</p>;
  }

  return (
    <div className="space-y-2">
      {entries.map(([name, score]) => (
        <div key={name} className="flex items-center gap-3">
          <span className="w-40 shrink-0 text-sm capitalize">
            {name.replace(/_/g, ' ')}
          </span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${Math.min(100, score)}%` }}
            />
          </div>
          <span className="w-10 shrink-0 text-right text-sm tabular-nums">{score}</span>
        </div>
      ))}
    </div>
  );
}

export function RiskDetailPage() {
  const { riskId } = useParams<{ riskId: string }>();
  const [record, setRecord] = useState<AdminRiskDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!riskId) return;
    setLoading(true);
    try {
      setRecord(await getAdminRiskDetail(riskId));
      setError(null);
    } catch (err) {
      setError(apiErrorDetail(err, 'Could not load this assessment.'));
    } finally {
      setLoading(false);
    }
  }, [riskId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        <Loader2 className="mr-3 h-5 w-5 animate-spin" />
        Loading assessment…
      </div>
    );
  }

  if (error || !record) {
    return (
      <>
        <PageHeader title="Risk Incident" />
        <EmptyState
          icon={ShieldAlert}
          title="Assessment unavailable"
          description={error ?? 'This assessment could not be found.'}
          action={
            <Button asChild variant="outline">
              <Link to="/admin/risk">Back to Risk Center</Link>
            </Button>
          }
        />
      </>
    );
  }

  const sla = slaFor(record.risk_level);
  const reviewed = Boolean(record.reviewed_at);
  const disagreed = record.verdict === 'disagree';

  return (
    <>
      <PageHeader
        title="Risk Incident"
        description={`${record.student_name} · ${record.school_name}`}
        actions={
          <Button asChild variant="outline">
            <Link to="/admin/risk">
              <ArrowLeft className="h-4 w-4" />
              Risk Center
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-2">
        {/* AI assessment */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">AI assessment</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <dl className="grid grid-cols-2 gap-4">
              <Field label="Level">
                <StatusBadge status={record.risk_level} />
              </Field>
              <Field label="Score">
                {record.risk_score === null ? '—' : record.risk_score}
              </Field>
              <Field label="Confidence">
                {record.confidence === null
                  ? '—'
                  : `${Math.round(record.confidence * 100)}%`}
              </Field>
              <Field label="Source">{record.generated_by ?? '—'}</Field>
            </dl>

            {record.summary && (
              <div>
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                  Summary
                </dt>
                <p className="mt-1 text-sm">{record.summary}</p>
              </div>
            )}

            {record.trigger_reason && (
              <div>
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                  Trigger
                </dt>
                <p className="mt-1 text-sm">{record.trigger_reason}</p>
              </div>
            )}

            <div>
              <dt className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
                Contributing categories
              </dt>
              <Categories categories={record.categories} />
            </div>
          </CardContent>
        </Card>

        {/* Human review */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Counselor review</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <dl className="grid grid-cols-2 gap-4">
              <Field label="Status">
                <StatusBadge status={record.review_status ?? 'pending'} />
              </Field>
              <Field label="Age">
                {record.age_hours < 1
                  ? 'Just now'
                  : record.age_hours < 48
                    ? `${Math.round(record.age_hours)} hours`
                    : `${Math.round(record.age_hours / 24)} days`}
              </Field>
              <Field label="Assigned">
                {record.assigned_counselor_name ?? (
                  <span className="text-muted-foreground">Unassigned</span>
                )}
              </Field>
              <Field label="Reviewed by">
                {record.reviewed_by_name ?? (
                  <span className="text-muted-foreground">Not yet reviewed</span>
                )}
              </Field>
            </dl>

            {!reviewed && (
              <div
                className={`rounded-lg border p-3 text-sm ${
                  sla.emergency
                    ? 'border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300'
                    : 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300'
                }`}
              >
                <div>
                  Response target: <strong>{sla.window}</strong>
                </div>
                <div className="mt-1">{sla.action}</div>
              </div>
            )}

            {reviewed ? (
              <dl className="space-y-4">
                <Field label="Counselor's level">
                  {record.counselor_risk_level ? (
                    <StatusBadge status={record.counselor_risk_level} />
                  ) : (
                    '—'
                  )}
                </Field>
                <Field label="Verdict">
                  {record.verdict ? (
                    <span
                      className={
                        disagreed
                          ? 'font-medium text-amber-700 dark:text-amber-400'
                          : 'font-medium text-emerald-700 dark:text-emerald-400'
                      }
                    >
                      {disagreed ? 'Disagreed with AI' : 'Agreed with AI'}
                    </span>
                  ) : (
                    '—'
                  )}
                </Field>
                <Field label="Outcome">{record.outcome ?? '—'}</Field>
                <Field label="Note">
                  {record.resolution_note ?? (
                    <span className="text-muted-foreground">No note recorded.</span>
                  )}
                </Field>
              </dl>
            ) : (
              <p className="text-sm text-muted-foreground">
                No counselor has recorded a verdict yet. Reviewing is done from the
                counselor dashboard — platform admins have oversight here, not
                clinical sign-off.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <p className="text-xs text-muted-foreground">
        Conversation content is not shown here. Reading a student&apos;s messages is
        break-glass access with its own audit-logged flow.
      </p>
    </>
  );
}
