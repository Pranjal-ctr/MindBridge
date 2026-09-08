/**
 * Platform Dashboard — the /admin index.
 *
 * Cross-tenant KPIs from GET /admin/analytics/platform, plus a live count of
 * what is waiting in risk queues across every school. The risk strip is first
 * on purpose: an admin opening this page should see unreviewed alerts before
 * revenue.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  Building2,
  Cpu,
  DollarSign,
  GraduationCap,
  HeartHandshake,
  MessagesSquare,
  RefreshCw,
  Users,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import {
  apiErrorDetail,
  getPlatformAnalytics,
  listAdminRisk,
} from '../../../../lib/admin-api';
import type { AdminRiskRow, PlatformAnalytics } from '../../../../lib/admin-types';
import { Button } from '../../ui/button';
import { Card, CardContent } from '../../ui/card';
import { PageHeader } from '../widgets/PageHeader';
import { StatCard } from '../widgets/StatCard';
import { StatusBadge } from '../widgets/StatusBadge';

/** Hours a pending assessment may sit before the dashboard calls it stale. */
const STALE_AFTER_HOURS = 24;

function currency(value: number): string {
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export function DashboardPage() {
  const [stats, setStats] = useState<PlatformAnalytics | null>(null);
  const [pending, setPending] = useState<AdminRiskRow[]>([]);
  const [pendingTotal, setPendingTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // Independent calls — fire together rather than serialising the page.
      const [analytics, risk] = await Promise.all([
        getPlatformAnalytics(),
        listAdminRisk(1, 5, { review_status: 'pending' }),
      ]);
      setStats(analytics);
      setPending(risk.items);
      setPendingTotal(risk.total);
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Could not load platform data.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const stale = pending.filter((r) => r.age_hours >= STALE_AFTER_HOURS);

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Platform-wide overview across every school."
        actions={
          <Button variant="outline" onClick={load} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        }
      />

      {/* Unreviewed risk first — this is the number that matters most. */}
      <Card
        className={
          pendingTotal > 0
            ? 'border-amber-300 bg-amber-50/60 dark:border-amber-900 dark:bg-amber-950/30'
            : undefined
        }
      >
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <AlertTriangle
                className={`h-5 w-5 ${pendingTotal > 0 ? 'text-amber-600' : 'text-muted-foreground'}`}
              />
              <span className="font-medium">
                {loading
                  ? 'Checking risk queues…'
                  : pendingTotal === 0
                    ? 'No assessments awaiting review'
                    : `${pendingTotal} assessment${pendingTotal === 1 ? '' : 's'} awaiting review`}
              </span>
              {stale.length > 0 && (
                <span className="text-sm text-amber-700 dark:text-amber-400">
                  · {stale.length} over {STALE_AFTER_HOURS}h
                </span>
              )}
            </div>
            <Button asChild size="sm" variant="outline">
              <Link to="/admin/risk">Open Risk Center</Link>
            </Button>
          </div>

          {pending.length > 0 && (
            <div className="divide-y rounded-lg border bg-card">
              {pending.map((row) => (
                <Link
                  key={row.risk_id}
                  to={`/admin/risk/${row.risk_id}`}
                  className="flex flex-wrap items-center gap-3 px-3 py-2 text-sm hover:bg-accent/50"
                >
                  <StatusBadge status={row.risk_level} />
                  <span className="font-medium">{row.student_name}</span>
                  <span className="text-muted-foreground">{row.school_name}</span>
                  <span className="ml-auto tabular-nums text-muted-foreground">
                    {row.age_hours < 1
                      ? 'just now'
                      : `${Math.round(row.age_hours)}h old`}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Schools"
          icon={Building2}
          loading={loading}
          value={stats?.total_schools ?? 0}
        />
        <StatCard
          label="Students"
          icon={GraduationCap}
          loading={loading}
          value={stats?.total_students ?? 0}
        />
        <StatCard
          label="Parents"
          icon={Users}
          loading={loading}
          value={stats?.total_parents ?? 0}
        />
        <StatCard
          label="Counselors"
          icon={HeartHandshake}
          loading={loading}
          value={stats?.total_counselors ?? 0}
        />
        <StatCard
          label="Active users"
          icon={Users}
          loading={loading}
          value={stats?.active_users ?? 0}
          hint="Signed in within 30 days"
        />
        <StatCard
          label="Conversations"
          icon={MessagesSquare}
          loading={loading}
          value={stats?.conversation_count ?? 0}
        />
        <StatCard
          label="AI requests"
          icon={Cpu}
          loading={loading}
          value={stats?.ai_requests ?? 0}
          hint={stats ? `${currency(stats.ai_cost_usd)} spent` : undefined}
        />
        <StatCard
          label="Revenue"
          icon={DollarSign}
          loading={loading}
          value={stats ? currency(stats.revenue_usd) : '—'}
          hint="Active subscriptions"
        />
      </div>
    </>
  );
}
