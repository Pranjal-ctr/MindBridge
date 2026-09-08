/**
 * School Admin Dashboard — school-wide anonymised analytics.
 *
 * Every number here comes from GET /analytics/overview. Nothing is synthesised
 * client-side: if the API has no data for a panel, the panel says so. This page
 * previously rendered hardcoded arrays ("970 students", "87% counselor
 * utilization", "97% parent satisfaction"), which showed schools invented
 * figures about their own students.
 *
 * Two states matter beyond loading/error:
 *   - `cohort_suppressed` — school below the k-anonymity floor. Breakdowns are
 *     withheld server-side; we explain why rather than drawing empty charts.
 *   - a null `score` on a trend point — no data that month. Recharts renders it
 *     as a gap; it must never be coerced to 0.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  BarChart3,
  CalendarCheck,
  HeartHandshake,
  Loader2,
  Menu,
  RefreshCw,
  ShieldCheck,
  TrendingUp,
  Users,
  X,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { KioLogo } from './KioLogo';
import { Disclaimer } from './Disclaimer';
import { NotificationBell } from './NotificationBell';
import { getAnalyticsOverview } from '../../lib/analytics-api';
import { useAuth } from '../../lib/auth-context';
import type { AnalyticsOverview } from '../../lib/types';

// ── Small presentational helpers ──────────────────────────────────────

function StatCard({
  icon: Icon,
  value,
  label,
  hint,
  tone,
}: {
  icon: typeof Users;
  value: string;
  label: string;
  hint?: string;
  tone: 'primary' | 'emerald' | 'purple' | 'amber';
}) {
  const tones = {
    primary: 'from-blue-500 to-blue-600 text-blue-100',
    emerald: 'from-emerald-500 to-emerald-600 text-emerald-100',
    purple: 'from-purple-500 to-purple-600 text-purple-100',
    amber: 'from-amber-500 to-amber-600 text-amber-100',
  } as const;

  return (
    <div className={`bg-gradient-to-br ${tones[tone]} text-white rounded-xl p-6 shadow-lg`}>
      <div className="flex items-center justify-between mb-2">
        <Icon className="w-8 h-8 opacity-80" />
      </div>
      <div className="text-3xl font-bold mb-1">{value}</div>
      <div className="text-sm opacity-90">{label}</div>
      {hint && <div className="text-xs opacity-75 mt-1">{hint}</div>}
    </div>
  );
}

function Panel({
  title,
  subtitle,
  children,
  innerRef,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  innerRef?: React.Ref<HTMLDivElement>;
}) {
  return (
    <div ref={innerRef} className="bg-card border border-border rounded-xl p-6 shadow-sm scroll-mt-20">
      <h2 className="text-lg font-semibold">{title}</h2>
      {subtitle && <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </div>
  );
}

/** Shown when a panel has no data yet — never a zeroed-out chart. */
function NoData({ message }: { message: string }) {
  return (
    <div className="h-[250px] flex items-center justify-center text-center text-sm text-muted-foreground px-6">
      {message}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────

export function SchoolAdminDashboard() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { user, logout } = useAuth();

  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const overviewRef = useRef<HTMLDivElement>(null);
  const wellbeingRef = useRef<HTMLDivElement>(null);
  const riskRef = useRef<HTMLDivElement>(null);
  const counselingRef = useRef<HTMLDivElement>(null);

  const scrollTo = useCallback((ref: React.RefObject<HTMLDivElement | null>) => {
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setSidebarOpen(false);
  }, []);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await getAnalyticsOverview());
    } catch {
      // Deliberately generic: an analytics failure must not leak roster detail.
      setError('Could not load analytics. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const schoolName = data?.school_name || 'Your School';
  const suppressed = data?.cohort_suppressed ?? false;

  // Zero-value tiers would render as invisible pie slices with legend noise.
  const pieData = (data?.risk_distribution ?? []).filter((b) => b.value > 0);
  const trend = data?.wellness_trend ?? [];
  const hasTrendData = trend.some((p) => p.score !== null);
  const stress = data?.stress_by_category ?? [];

  const navItems = [
    { label: 'Overview', icon: BarChart3, ref: overviewRef },
    { label: 'Wellbeing', icon: TrendingUp, ref: wellbeingRef },
    { label: 'Risk', icon: AlertTriangle, ref: riskRef },
    { label: 'Counseling', icon: HeartHandshake, ref: counselingRef },
  ];

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Sidebar */}
      <div
        className={`${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        } md:translate-x-0 fixed md:static inset-y-0 left-0 z-50 w-64 bg-sidebar border-r border-sidebar-border transition-transform duration-300 ease-in-out`}
      >
        <div className="flex flex-col h-full">
          <div className="p-4 border-b border-sidebar-border">
            <div className="flex items-center justify-between">
              <KioLogo className="h-7 w-auto" />
              <button className="md:hidden" onClick={() => setSidebarOpen(false)} aria-label="Close menu">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="mt-3 px-3 py-2 bg-sidebar-accent rounded-lg">
              <div className="text-sm font-medium truncate" title={schoolName}>
                {schoolName}
              </div>
              <div className="text-xs text-muted-foreground">Admin Portal</div>
            </div>
          </div>

          {/* In-page sections. These were href="#" and went nowhere. */}
          <nav className="flex-1 p-4 space-y-2">
            {navItems.map(({ label, icon: Icon, ref }) => (
              <button
                key={label}
                onClick={() => scrollTo(ref)}
                className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition text-left"
              >
                <Icon className="w-5 h-5" />
                <span>{label}</span>
              </button>
            ))}
          </nav>

          <div className="p-4 border-t border-sidebar-border">
            {/* Was a <Link to="/">, which left a valid JWT in localStorage. */}
            <button
              onClick={logout}
              className="w-full flex items-center justify-center px-3 py-2 rounded-lg text-muted-foreground hover:bg-sidebar-accent transition text-sm"
            >
              Sign Out
            </button>
          </div>
        </div>
      </div>

      {/* Main */}
      <div className="flex-1 overflow-y-auto">
        <header className="sticky top-0 z-10 h-16 border-b border-border bg-card flex items-center justify-between px-4 md:px-6">
          <div className="flex items-center gap-4">
            <button className="md:hidden" onClick={() => setSidebarOpen(true)} aria-label="Open menu">
              <Menu className="w-6 h-6" />
            </button>
            <h1 className="text-lg font-semibold">School Analytics</h1>
          </div>
          <div className="flex items-center gap-3">
            {data && (
              <span className="text-sm text-muted-foreground hidden sm:inline">
                Updated {new Date(data.generated_at).toLocaleString()}
              </span>
            )}
            <button
              onClick={load}
              disabled={isLoading}
              className="p-2 rounded-lg hover:bg-accent transition disabled:opacity-50"
              aria-label="Refresh analytics"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
            <NotificationBell />
          </div>
        </header>

        <div className="p-4 md:p-6 space-y-6">
          {/* Privacy notice */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
            <div className="flex items-start gap-3">
              <ShieldCheck className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div>
                <div className="font-medium text-blue-900">Aggregate data only</div>
                <div className="text-sm text-blue-700 mt-1">
                  Everything on this page is school-wide. Individual students are never
                  identified and their conversations are never accessible at school level.
                  {data && data.min_cohort_size > 0 && (
                    <> Breakdowns are withheld entirely for schools with fewer than{' '}
                    {data.min_cohort_size} students.</>
                  )}
                </div>
              </div>
            </div>
          </div>

          {isLoading && !data && (
            <div className="flex items-center justify-center py-24 text-muted-foreground">
              <Loader2 className="w-6 h-6 animate-spin mr-3" />
              Loading analytics…
            </div>
          )}

          {error && (
            <div className="bg-destructive/10 border border-destructive/30 rounded-xl p-4 flex items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" />
                <div className="text-sm text-destructive">{error}</div>
              </div>
              <button
                onClick={load}
                className="px-3 py-1.5 rounded-lg bg-destructive text-destructive-foreground text-sm whitespace-nowrap"
              >
                Retry
              </button>
            </div>
          )}

          {data && (
            <>
              {/* Key metrics */}
              <div ref={overviewRef} className="grid grid-cols-1 md:grid-cols-4 gap-4 scroll-mt-20">
                <StatCard
                  icon={Users}
                  tone="primary"
                  value={String(data.total_students)}
                  label="Active Students"
                />
                <StatCard
                  icon={BarChart3}
                  tone="emerald"
                  // null means nothing recorded — showing "0/100" would read as
                  // a school in total crisis.
                  value={
                    data.avg_wellness_score === null ? '—' : `${data.avg_wellness_score}/100`
                  }
                  label="Avg Wellness Score"
                  hint={
                    data.avg_wellness_score === null
                      ? 'No scores recorded yet'
                      : `From ${data.students_with_wellness_data} student${
                          data.students_with_wellness_data === 1 ? '' : 's'
                        }`
                  }
                />
                <StatCard
                  icon={CalendarCheck}
                  tone="purple"
                  value={suppressed ? '—' : `${data.checkin_participation}%`}
                  label="Checked In (7 days)"
                  hint={
                    suppressed
                      ? 'Withheld — small school'
                      : `${data.checked_in_last_7d} of ${data.total_students} students`
                  }
                />
                <StatCard
                  icon={HeartHandshake}
                  tone="amber"
                  value={String(data.counselors.active_counselors)}
                  label="Assigned Counselors"
                  hint={`${data.counselors.upcoming_sessions} session${
                    data.counselors.upcoming_sessions === 1 ? '' : 's'
                  } upcoming`}
                />
              </div>

              {suppressed && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                  <div className="flex items-start gap-3">
                    <ShieldCheck className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <div className="font-medium text-amber-900">
                        Detailed breakdowns are hidden
                      </div>
                      <div className="text-sm text-amber-700 mt-1">
                        {data.total_students === 0
                          ? 'No students have enrolled yet. Charts will appear once your school reaches '
                          : `Your school has ${data.total_students} student${
                              data.total_students === 1 ? '' : 's'
                            }. Wellbeing, risk and stress breakdowns unlock at `}
                        {data.min_cohort_size} students — below that, a single-student
                        category would identify that student to you.
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {!suppressed && (
                <>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Wellness trend */}
                    <Panel
                      innerRef={wellbeingRef}
                      title="6-Month Wellness Trend"
                      subtitle="School-wide monthly average"
                    >
                      {hasTrendData ? (
                        <ResponsiveContainer width="100%" height={250}>
                          <LineChart data={trend}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                            <XAxis dataKey="month" stroke="#6b7280" />
                            <YAxis stroke="#6b7280" domain={[0, 100]} />
                            <Tooltip
                              formatter={(value) =>
                                value === null || value === undefined
                                  ? 'No data'
                                  : `${value}/100`
                              }
                            />
                            {/* connectNulls stays false: a month with no data is a
                                gap in the record, not a straight line through it. */}
                            <Line
                              type="monotone"
                              dataKey="score"
                              stroke="#5A6BFF"
                              strokeWidth={3}
                              dot={{ r: 5 }}
                              connectNulls={false}
                            />
                          </LineChart>
                        </ResponsiveContainer>
                      ) : (
                        <NoData message="No wellness scores recorded yet. This chart fills in as students use Kio." />
                      )}
                    </Panel>

                    {/* Risk distribution */}
                    <Panel
                      innerRef={riskRef}
                      title="Student Risk Distribution"
                      subtitle="Current risk tier across the school"
                    >
                      {pieData.length > 0 ? (
                        <div className="flex items-center justify-between">
                          <ResponsiveContainer width="50%" height={250}>
                            <PieChart>
                              <Pie
                                data={pieData}
                                cx="50%"
                                cy="50%"
                                innerRadius={60}
                                outerRadius={90}
                                paddingAngle={2}
                                dataKey="value"
                              >
                                {pieData.map((entry) => (
                                  <Cell key={entry.level} fill={entry.color} />
                                ))}
                              </Pie>
                              <Tooltip
                                formatter={(value: number, name: string) => [
                                  `${value} student${value === 1 ? '' : 's'}`,
                                  name,
                                ]}
                              />
                            </PieChart>
                          </ResponsiveContainer>
                          <div className="space-y-3">
                            {data.risk_distribution.map((item) => (
                              <div key={item.level} className="flex items-center gap-3">
                                <div
                                  className="w-4 h-4 rounded"
                                  style={{ backgroundColor: item.color }}
                                />
                                <div>
                                  <div className="font-medium text-sm">{item.name}</div>
                                  <div className="text-xs text-muted-foreground">
                                    {item.value} student{item.value === 1 ? '' : 's'}
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <NoData message="No risk assessments recorded yet." />
                      )}
                    </Panel>
                  </div>

                  {/* Stress factors */}
                  <Panel
                    title="Primary Stress Factors"
                    subtitle="Students counted once, by their most recent dominant topic"
                  >
                    {stress.length > 0 ? (
                      <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={stress}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                          <XAxis dataKey="category" stroke="#6b7280" />
                          <YAxis stroke="#6b7280" allowDecimals={false} />
                          <Tooltip
                            formatter={(value: number) => [
                              `${value} student${value === 1 ? '' : 's'}`,
                              'Students',
                            ]}
                          />
                          <Bar dataKey="students" fill="#5A6BFF" radius={[8, 8, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <NoData message="No stress signals detected yet. These emerge from student conversations over time." />
                    )}
                  </Panel>
                </>
              )}

              {/* Counseling coverage — staff data, so it survives suppression */}
              <Panel
                innerRef={counselingRef}
                title="Counseling Coverage"
                subtitle="Trailing 30 days"
              >
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="p-4 rounded-lg bg-accent/50">
                    <div className="text-2xl font-bold">{data.counselors.sessions_last_30d}</div>
                    <div className="text-sm text-muted-foreground">Sessions completed</div>
                  </div>
                  <div className="p-4 rounded-lg bg-accent/50">
                    <div className="text-2xl font-bold">
                      {data.counselors.students_seen_last_30d}
                    </div>
                    <div className="text-sm text-muted-foreground">Students seen</div>
                  </div>
                  <div className="p-4 rounded-lg bg-accent/50">
                    <div className="text-2xl font-bold">{data.counselors.upcoming_sessions}</div>
                    <div className="text-sm text-muted-foreground">Upcoming sessions</div>
                  </div>
                </div>
              </Panel>
            </>
          )}

          <Disclaimer variant="short" className="pt-2" />
        </div>
      </div>
    </div>
  );
}
