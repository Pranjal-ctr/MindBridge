/**
 * Parent Dashboard — "How is my child doing?" at a glance.
 *
 * Three tabs: Overview (wellness analytics), Recommendations (personalized
 * guidance + why), Family Activities (things to do together). All content is
 * derived from real backend calculations; per-day mood icons stay private to
 * the student — parents see the weekly aggregate instead.
 */

import { TrendingUp, TrendingDown, Minus, Heart, AlertCircle, CheckCircle, Info, Calendar, Menu, X, Loader2, RefreshCw, Users, KeyRound, Sparkles, MessageCircle, Shield, HelpCircle, Lightbulb } from 'lucide-react';
import { KioLogo } from './KioLogo';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from 'recharts';
import { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '../../lib/auth-context';
import { useChildInsights } from '../../hooks/useChildInsights';
import api from '../../lib/api';
import { MOOD_META } from '../../lib/mood';
import type {
  LinkedChildResponse,
  WeeklyReportResponse,
  WellnessTrendPoint,
} from '../../lib/types';

// Spec progression green -> yellow -> orange -> red (backend levels map onto it)
const RISK_TIMELINE_COLORS: Record<string, string> = {
  green: '#10b981', yellow: '#f59e0b', red: '#f97316', critical: '#ef4444',
};
const RISK_TIMELINE_LABELS: Record<string, string> = {
  green: 'Green', yellow: 'Yellow', red: 'Orange', critical: 'Red',
};

type ParentTab = 'overview' | 'recommendations' | 'activities';

/** Light 3-point moving average over real points — smooths jitter, keeps shape. */
function smoothTrend(points: WellnessTrendPoint[]): WellnessTrendPoint[] {
  if (points.length < 4) return points;
  return points.map((p, i) => {
    const window = points.slice(Math.max(0, i - 1), Math.min(points.length, i + 2));
    const avg = window.reduce((sum, q) => sum + q.score, 0) / window.length;
    return { date: p.date, score: Math.round(avg * 10) / 10 };
  });
}

function formatTrendDate(value: string): string {
  return value.includes('-')
    ? new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    : value;
}

function TrendTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-border rounded-lg shadow-md px-3 py-2 text-sm">
      <div className="text-muted-foreground text-xs">{formatTrendDate(String(label))}</div>
      <div className="font-semibold">{payload[0].value}/100</div>
    </div>
  );
}

export function ParentDashboard() {
  const { user, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [tab, setTab] = useState<ParentTab>('overview');

  // Children state
  const [children, setChildren] = useState<LinkedChildResponse[]>([]);
  const [isLoadingChildren, setIsLoadingChildren] = useState(true);
  const [selectedChildId, setSelectedChildId] = useState<string | null>(null);

  // Insights state (live: 5-min poll + refetch-on-focus + manual refresh button)
  const { insights, isLoading: isLoadingInsights, isRefreshing, refetch: refetchInsights } =
    useChildInsights(selectedChildId);

  // Wellness trend range selector (7 / 30 / 90 days)
  const [trendDays, setTrendDays] = useState<7 | 30 | 90>(7);
  const [trendData, setTrendData] = useState<WellnessTrendPoint[]>([]);
  useEffect(() => {
    if (!selectedChildId) return;
    let cancelled = false;
    api
      .get<WellnessTrendPoint[]>(`/parents/children/${selectedChildId}/wellness-trend`, {
        params: { days: trendDays },
      })
      .then((res) => { if (!cancelled) setTrendData(res.data); })
      .catch(() => { if (!cancelled) setTrendData([]); });
    return () => { cancelled = true; };
  }, [selectedChildId, trendDays]);

  // Weekly AI report (cached server-side per ISO week)
  const [weeklyReport, setWeeklyReport] = useState<WeeklyReportResponse | null>(null);
  useEffect(() => {
    if (!selectedChildId) return;
    let cancelled = false;
    setWeeklyReport(null);
    api
      .get<WeeklyReportResponse>(`/parents/children/${selectedChildId}/weekly-report`)
      .then((res) => { if (!cancelled) setWeeklyReport(res.data); })
      .catch(() => { if (!cancelled) setWeeklyReport(null); });
    return () => { cancelled = true; };
  }, [selectedChildId]);

  // Redeem code state
  const [showRedeemForm, setShowRedeemForm] = useState(false);
  const [redeemCode, setRedeemCode] = useState('');
  const [redeemRelationship, setRedeemRelationship] = useState('parent');
  const [isRedeeming, setIsRedeeming] = useState(false);
  const [redeemError, setRedeemError] = useState<string | null>(null);
  const [redeemSuccess, setRedeemSuccess] = useState<string | null>(null);

  const fetchChildren = useCallback(async () => {
    try {
      setIsLoadingChildren(true);
      const { data } = await api.get<{ children: LinkedChildResponse[] }>('/linking/children');
      setChildren(data.children);
      if (data.children.length > 0 && !selectedChildId) {
        setSelectedChildId(data.children[0].student_id);
      }
    } catch {
      setChildren([]);
    } finally {
      setIsLoadingChildren(false);
    }
  }, [selectedChildId]);

  useEffect(() => {
    fetchChildren();
  }, [fetchChildren]);

  const handleRedeem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!redeemCode.trim()) return;
    setIsRedeeming(true);
    setRedeemError(null);
    setRedeemSuccess(null);
    try {
      const { data } = await api.post('/linking/redeem', {
        invite_code: redeemCode.toUpperCase(),
        relationship: redeemRelationship,
      });
      setRedeemSuccess(`Successfully linked to ${data.student_name}!`);
      setRedeemCode('');
      setShowRedeemForm(false);
      await fetchChildren();
    } catch (err: any) {
      setRedeemError(err.response?.data?.detail || 'Failed to redeem invite code');
    } finally {
      setIsRedeeming(false);
    }
  };

  const selectedChild = children.find((c) => c.student_id === selectedChildId);

  const displayTrend = useMemo(() => smoothTrend(trendData), [trendData]);
  const weekDelta = useMemo(() => {
    if (trendData.length < 2) return null;
    return Math.round(trendData[trendData.length - 1].score - trendData[0].score);
  }, [trendData]);

  const stressFactors = insights?.stress_factors ?? [];
  const dimensions = insights?.wellbeing_dimensions ?? [];
  const wellnessScore = insights?.wellness_score ?? selectedChild?.wellness_score ?? null;
  const riskLevel = selectedChild?.risk_level ?? insights?.risk_level ?? 'green';
  const emotionalState = insights?.emotional_state ?? 'Stable';
  const trend = insights?.wellness_breakdown?.trend ?? null;
  const moodSummary = insights?.weekly_mood_summary ?? null;

  const trendDisplay = trend === 'improving'
    ? { Icon: TrendingUp, label: 'Improving', color: 'text-emerald-600' }
    : trend === 'declining'
    ? { Icon: TrendingDown, label: 'Declining', color: 'text-red-600' }
    : trend === 'stable'
    ? { Icon: Minus, label: 'Stable', color: 'text-muted-foreground' }
    : null;

  const insightCardStyles: Record<string, { bg: string; border: string; text: string; icon: string; Icon: typeof AlertCircle }> = {
    positive: { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-900', icon: 'text-emerald-600', Icon: CheckCircle },
    caution: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-900', icon: 'text-amber-600', Icon: AlertCircle },
    info: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-900', icon: 'text-blue-600', Icon: Info },
  };

  const riskColors: Record<string, { bg: string; text: string; dot: string }> = {
    green: { bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500' },
    yellow: { bg: 'bg-amber-100', text: 'text-amber-700', dot: 'bg-amber-500' },
    orange: { bg: 'bg-orange-100', text: 'text-orange-700', dot: 'bg-orange-500' },
    red: { bg: 'bg-red-100', text: 'text-red-700', dot: 'bg-red-500' },
    critical: { bg: 'bg-red-100', text: 'text-red-700', dot: 'bg-red-500' },
  };
  const riskColor = riskColors[riskLevel] || riskColors.green;

  const navItems: { id: ParentTab; label: string; Icon: typeof TrendingUp }[] = [
    { id: 'overview', label: 'Overview', Icon: TrendingUp },
    { id: 'recommendations', label: 'Recommendations', Icon: Lightbulb },
    { id: 'activities', label: 'Family Activities', Icon: Heart },
  ];

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Sidebar */}
      <div className={`${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0 fixed md:static inset-y-0 left-0 z-50 w-64 bg-sidebar border-r border-sidebar-border transition-transform duration-300 ease-in-out`}>
        <div className="flex flex-col h-full">
          <div className="p-4 border-b border-sidebar-border">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <KioLogo className="h-7 w-auto" />
              </div>
              <button className="md:hidden" onClick={() => setSidebarOpen(false)}>
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="mt-3 px-3 py-2 bg-sidebar-accent rounded-lg">
              <div className="text-sm font-medium">
                {user ? `${user.first_name} ${user.last_name}` : 'Parent Portal'}
              </div>
              <div className="text-xs text-muted-foreground">Parent</div>
            </div>
          </div>

          {/* Children List */}
          <div className="p-3 border-b border-sidebar-border">
            <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 px-3">
              My Children
            </div>
            {isLoadingChildren ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
              </div>
            ) : children.length === 0 ? (
              <div className="px-3 py-2 text-sm text-muted-foreground">
                No linked children yet
              </div>
            ) : (
              <div className="space-y-1">
                {children.map((child) => (
                  <button
                    key={child.student_id}
                    onClick={() => setSelectedChildId(child.student_id)}
                    className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition ${
                      selectedChildId === child.student_id
                        ? 'bg-sidebar-primary text-sidebar-primary-foreground'
                        : 'text-sidebar-foreground hover:bg-sidebar-accent'
                    }`}
                  >
                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                      <span className="text-xs font-semibold text-primary">
                        {child.first_name[0]}{child.last_name[0]}
                      </span>
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-medium truncate">{child.first_name} {child.last_name}</div>
                      <div className="text-xs opacity-70">{child.relationship || 'Child'}</div>
                    </div>
                  </button>
                ))}
              </div>
            )}

            <button
              onClick={() => setShowRedeemForm(!showRedeemForm)}
              className="w-full flex items-center gap-2 px-3 py-2 mt-1 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition text-sm"
            >
              <KeyRound className="w-4 h-4" />
              <span>Link Another Child</span>
            </button>
          </div>

          <nav className="flex-1 p-4 space-y-2">
            {navItems.map(({ id, label, Icon }) => (
              <button
                key={id}
                onClick={() => { setTab(id); setSidebarOpen(false); }}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition text-left ${
                  tab === id
                    ? 'bg-sidebar-primary text-sidebar-primary-foreground'
                    : 'text-sidebar-foreground hover:bg-sidebar-accent'
                }`}
              >
                <Icon className="w-5 h-5" />
                <span>{label}</span>
              </button>
            ))}
          </nav>

          <div className="p-4 border-t border-sidebar-border">
            <button
              onClick={logout}
              className="w-full flex items-center justify-center px-3 py-2 rounded-lg text-muted-foreground hover:bg-sidebar-accent transition text-sm"
            >
              Sign Out
            </button>
          </div>
        </div>
      </div>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/50 z-40 md:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        {/* Header */}
        <header className="sticky top-0 z-10 h-16 border-b border-border bg-card flex items-center justify-between px-4 md:px-6">
          <div className="flex items-center gap-4">
            <button className="md:hidden" onClick={() => setSidebarOpen(true)}>
              <Menu className="w-6 h-6" />
            </button>
            <h1 className="text-lg font-semibold">
              {selectedChild ? `${selectedChild.first_name}'s Wellness` : 'Parent Dashboard'}
            </h1>
          </div>
          <div className="flex items-center gap-3">
            {selectedChild && (
              <button
                onClick={refetchInsights}
                disabled={isRefreshing}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm border border-border hover:bg-muted transition disabled:opacity-50"
                title="Refresh insights"
              >
                <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                <span className="hidden sm:inline">Refresh</span>
              </button>
            )}
            <div className={`flex items-center gap-2 px-3 py-1.5 ${riskColor.bg} ${riskColor.text} rounded-full text-sm`}>
              <CheckCircle className="w-4 h-4" />
              <span className="hidden sm:inline">Status: </span>
              {riskLevel === 'green' ? 'Good' : riskLevel === 'yellow' ? 'Caution' : 'Alert'}
            </div>
          </div>
        </header>

        <div className="p-4 md:p-6 space-y-6 max-w-6xl mx-auto">
          {/* Redeem Form */}
          {showRedeemForm && (
            <div className="bg-white border border-border rounded-xl p-6 shadow-sm">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <KeyRound className="w-5 h-5 text-primary" />
                Link a Child with Invite Code
              </h2>
              <form onSubmit={handleRedeem} className="space-y-4">
                {redeemError && (
                  <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
                    <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                    <span>{redeemError}</span>
                  </div>
                )}
                {redeemSuccess && (
                  <div className="flex items-start gap-2 p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-700 text-sm">
                    <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />
                    <span>{redeemSuccess}</span>
                  </div>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-foreground mb-2 block">Invite Code</label>
                    <input
                      type="text"
                      value={redeemCode}
                      onChange={(e) => setRedeemCode(e.target.value.toUpperCase())}
                      placeholder="e.g. MB-X7K9"
                      className="w-full px-4 py-3 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-ring bg-input-background uppercase tracking-wider font-mono"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-foreground mb-2 block">Relationship</label>
                    <select
                      value={redeemRelationship}
                      onChange={(e) => setRedeemRelationship(e.target.value)}
                      className="w-full px-4 py-3 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-ring bg-input-background"
                    >
                      <option value="parent">Parent</option>
                      <option value="mother">Mother</option>
                      <option value="father">Father</option>
                      <option value="guardian">Guardian</option>
                      <option value="other">Other</option>
                    </select>
                  </div>
                </div>
                <div className="flex gap-3">
                  <button
                    type="submit"
                    disabled={isRedeeming}
                    className="px-6 py-2.5 bg-primary text-primary-foreground rounded-xl hover:bg-primary/90 transition font-medium disabled:opacity-50 flex items-center gap-2"
                  >
                    {isRedeeming && <Loader2 className="w-4 h-4 animate-spin" />}
                    Link Child
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowRedeemForm(false)}
                    className="px-6 py-2.5 border border-border rounded-xl hover:bg-muted transition"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* No children state */}
          {!isLoadingChildren && children.length === 0 && !showRedeemForm && (
            <div className="text-center py-16">
              <Users className="w-16 h-16 mx-auto text-muted-foreground/30 mb-4" />
              <h2 className="text-xl font-semibold mb-2">No Linked Children</h2>
              <p className="text-muted-foreground mb-6 max-w-md mx-auto">
                Ask your child to generate an invite code from their Kio dashboard, then enter it here to link your accounts.
              </p>
              <button
                onClick={() => setShowRedeemForm(true)}
                className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-xl hover:bg-primary/90 transition font-medium"
              >
                <KeyRound className="w-4 h-4" />
                Enter Invite Code
              </button>
            </div>
          )}

          {selectedChild && isLoadingInsights && (
            <div className="space-y-6 animate-pulse">
              <div className="h-40 bg-muted rounded-2xl" />
              <div className="grid md:grid-cols-2 gap-6">
                <div className="h-64 bg-muted rounded-xl" />
                <div className="h-64 bg-muted rounded-xl" />
              </div>
            </div>
          )}

          {selectedChild && !isLoadingInsights && tab === 'overview' && (
            <>
              {/* Privacy Banner */}
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <Shield className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-blue-700">
                    <span className="font-medium text-blue-900">Privacy reminder: </span>
                    You're viewing aggregated insights and trends. Raw conversations remain private so your child feels safe to share openly.
                  </div>
                </div>
              </div>

              {/* Premium wellness summary hero */}
              <div className="bg-gradient-to-br from-primary via-primary to-secondary rounded-2xl p-6 md:p-8 text-white">
                <div className="grid grid-cols-2 lg:grid-cols-5 gap-6 items-start">
                  <div className="col-span-2 lg:col-span-1">
                    <div className="text-sm text-blue-100 mb-1">Overall Wellness</div>
                    <div className="text-4xl font-bold">
                      {wellnessScore !== null ? Math.round(wellnessScore) : '—'}
                      <span className="text-lg font-normal text-blue-200">/100</span>
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-blue-100 mb-1">Trend</div>
                    <div className="flex items-center gap-1.5 font-semibold">
                      {trendDisplay ? (
                        <>
                          <trendDisplay.Icon className="w-4 h-4" />
                          {trendDisplay.label}
                        </>
                      ) : '—'}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-blue-100 mb-1">Risk</div>
                    <div className="flex items-center gap-2 font-semibold capitalize">
                      <span className={`w-2.5 h-2.5 rounded-full ${riskColor.dot}`} />
                      {riskLevel}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-blue-100 mb-1">Emotional State</div>
                    <div className="font-semibold">{emotionalState}</div>
                  </div>
                  <div>
                    <div className="text-sm text-blue-100 mb-1">Change This Period</div>
                    <div className="font-semibold">
                      {weekDelta === null ? '—' : weekDelta > 0 ? `+${weekDelta} pts` : weekDelta < 0 ? `${weekDelta} pts` : 'No change'}
                    </div>
                  </div>
                </div>
                {insights?.wellness_breakdown?.explanation && (
                  <p className="mt-5 pt-4 border-t border-white/20 text-sm text-blue-100">
                    {insights.wellness_breakdown.explanation}
                  </p>
                )}
              </div>

              {/* AI Weekly Summary */}
              <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-lg font-semibold flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-primary" />
                    This Week's Summary
                  </h2>
                  {weeklyReport && (
                    <span className="text-xs text-muted-foreground">
                      Week of {new Date(weeklyReport.week_start).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                    </span>
                  )}
                </div>
                {weeklyReport ? (
                  <>
                    <p className="font-medium mb-2">{weeklyReport.headline}</p>
                    <p className="text-sm text-muted-foreground mb-4">{weeklyReport.summary}</p>
                    <div className="grid md:grid-cols-2 gap-4">
                      {weeklyReport.highlights.length > 0 && (
                        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
                          <div className="text-sm font-medium text-emerald-800 mb-2">Highlights</div>
                          <ul className="space-y-1.5">
                            {weeklyReport.highlights.map((h, idx) => (
                              <li key={idx} className="text-sm text-emerald-700 flex items-start gap-2">
                                <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />{h}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {weeklyReport.focus_areas.length > 0 && (
                        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                          <div className="text-sm font-medium text-blue-800 mb-2">Focus for next week</div>
                          <ul className="space-y-1.5">
                            {weeklyReport.focus_areas.map((f, idx) => (
                              <li key={idx} className="text-sm text-blue-700 flex items-start gap-2">
                                <Info className="w-4 h-4 mt-0.5 shrink-0" />{f}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="py-6 text-center text-sm text-muted-foreground">
                    The weekly summary appears once there's activity to report.
                  </div>
                )}
              </div>

              {/* Wellness Trend + Weekly Mood Summary */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 bg-card border border-border rounded-xl p-6 shadow-sm">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold">Wellness Trend</h2>
                    <div className="flex gap-1 p-0.5 bg-muted rounded-lg">
                      {([7, 30, 90] as const).map((days) => (
                        <button
                          key={days}
                          onClick={() => setTrendDays(days)}
                          className={`px-3 py-1 rounded-md text-sm transition ${
                            trendDays === days
                              ? 'bg-white shadow-sm text-foreground font-medium'
                              : 'text-muted-foreground hover:text-foreground'
                          }`}
                        >
                          {days}d
                        </button>
                      ))}
                    </div>
                  </div>
                  {displayTrend.length > 1 ? (
                    <ResponsiveContainer width="100%" height={260}>
                      <LineChart id="parent-wellness-trend" data={displayTrend}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                        <XAxis
                          dataKey="date"
                          stroke="#6B7280"
                          tick={{ fontSize: 12 }}
                          tickFormatter={formatTrendDate}
                        />
                        <YAxis stroke="#6B7280" domain={[0, 100]} tick={{ fontSize: 12 }} />
                        <Tooltip content={<TrendTooltip />} />
                        <Line
                          type="monotone"
                          dataKey="score"
                          stroke="#5A6BFF"
                          strokeWidth={2.5}
                          dot={{ r: 3, fill: '#5A6BFF' }}
                          activeDot={{ r: 5 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="py-12 text-center text-sm text-muted-foreground">
                      Not enough data in this range yet -- the trend fills in as your child stays active.
                    </div>
                  )}
                  {insights?.wellness_breakdown && (
                    <details className="mt-4 group">
                      <summary className="text-sm text-primary cursor-pointer select-none">
                        Why this score?
                      </summary>
                      <div className="mt-3 space-y-3">
                        {Object.entries(insights.wellness_breakdown.components)
                          .sort(([, a], [, b]) => b.contribution - a.contribution)
                          .map(([name, c]) => (
                            <div key={name}>
                              <div className="flex items-center justify-between text-sm mb-1">
                                <span className="capitalize text-foreground font-medium">
                                  {name.replace(/_/g, ' ')}
                                </span>
                                <span className="text-muted-foreground">
                                  contributes {Math.round(c.contribution)} pts
                                </span>
                              </div>
                              <div className="h-1.5 bg-muted rounded-full overflow-hidden mb-1">
                                <div
                                  className="h-full bg-secondary rounded-full transition-all"
                                  style={{ width: `${Math.min(c.normalized, 100)}%` }}
                                />
                              </div>
                              <div className="text-xs text-muted-foreground">{c.detail}</div>
                            </div>
                          ))}
                        {insights.wellness_breakdown.calculated_at && (
                          <div className="text-xs text-muted-foreground pt-2 border-t border-border">
                            Last updated {new Date(insights.wellness_breakdown.calculated_at).toLocaleString()}
                            {insights.wellness_breakdown.confidence !== null &&
                              ` · confidence ${Math.round((insights.wellness_breakdown.confidence ?? 0) * 100)}%`}
                          </div>
                        )}
                      </div>
                    </details>
                  )}
                </div>

                {/* Weekly Mood Summary (aggregate -- daily icons stay with the student) */}
                <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                  <h2 className="text-lg font-semibold mb-1">This Week's Mood</h2>
                  <p className="text-xs text-muted-foreground mb-5">
                    A weekly summary -- daily details stay private to your child.
                  </p>
                  {moodSummary ? (
                    <div className="space-y-4">
                      <div className="text-center py-4 bg-muted/50 rounded-xl">
                        {moodSummary.dominant_mood && (
                          <div className="text-4xl mb-2">
                            {MOOD_META[moodSummary.dominant_mood as keyof typeof MOOD_META]?.emoji}
                          </div>
                        )}
                        <div className="text-lg font-semibold">{moodSummary.headline}</div>
                      </div>
                      <div className="space-y-2 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">Days recorded</span>
                          <span className="font-medium">{moodSummary.days_recorded} of 7</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">Low mood days</span>
                          <span className={`font-medium ${moodSummary.low_days > 1 ? 'text-amber-600' : ''}`}>
                            {moodSummary.low_days}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">Direction</span>
                          <span className={`font-medium capitalize ${
                            moodSummary.trend === 'improving' ? 'text-emerald-600'
                            : moodSummary.trend === 'declining' ? 'text-amber-600' : ''
                          }`}>
                            {moodSummary.trend}
                          </span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="py-10 text-center text-sm text-muted-foreground">
                      No mood check-ins recorded this week yet.
                    </div>
                  )}
                </div>
              </div>

              {/* Wellbeing Dimensions (radar) + Stress Factors */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                  <h2 className="text-lg font-semibold mb-1">Wellbeing Dimensions</h2>
                  <p className="text-xs text-muted-foreground mb-3">
                    Each dimension is derived from real signals -- higher is better.
                  </p>
                  {dimensions.length >= 3 ? (
                    <ResponsiveContainer width="100%" height={340}>
                      <RadarChart data={dimensions} outerRadius="72%">
                        <PolarGrid stroke="#E2E8F0" />
                        <PolarAngleAxis dataKey="dimension" tick={{ fill: '#374151', fontSize: 13 }} />
                        <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                        <Radar
                          dataKey="value"
                          stroke="#5A6BFF"
                          strokeWidth={2}
                          fill="#5A6BFF"
                          fillOpacity={0.3}
                        />
                        <Tooltip />
                      </RadarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="py-16 text-center text-sm text-muted-foreground">
                      Dimensions appear once the wellness engine has a few signals to work with.
                    </div>
                  )}
                </div>

                <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                  <h2 className="text-lg font-semibold mb-1">Stress Factors</h2>
                  <p className="text-xs text-muted-foreground mb-3">
                    AI-estimated contribution of each area to current stress (0-100), from conversations, check-ins, and risk analysis.
                  </p>
                  {stressFactors.length > 0 ? (
                    <ResponsiveContainer width="100%" height={Math.max(220, stressFactors.length * 40)}>
                      <BarChart
                        id="parent-stress-factors"
                        data={stressFactors}
                        layout="vertical"
                        margin={{ left: 8, right: 24 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" horizontal={false} />
                        <XAxis type="number" stroke="#6B7280" domain={[0, 100]} tick={{ fontSize: 12 }} />
                        <YAxis type="category" dataKey="name" stroke="#6B7280" width={104} tick={{ fontSize: 13 }} />
                        <Tooltip />
                        <Bar dataKey="value" fill="#5A6BFF" radius={[0, 8, 8, 0]} barSize={16} />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="py-16 text-center text-sm text-muted-foreground">
                      No stress signals detected yet.
                    </div>
                  )}
                </div>
              </div>

              {/* Risk Timeline */}
              <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                <h2 className="text-lg font-semibold mb-1">Risk Timeline</h2>
                <p className="text-sm text-muted-foreground mb-5">
                  Daily AI risk reading over the last week -- levels only, never conversation content.
                </p>
                {(insights?.risk_trend?.length ?? 0) > 0 ? (
                  <div className="relative">
                    <div className="absolute left-0 right-0 top-5 h-0.5 bg-border" />
                    <div className="relative flex justify-between">
                      {insights!.risk_trend.map((point, idx) => {
                        const prev = idx > 0 ? insights!.risk_trend[idx - 1] : null;
                        const rank: Record<string, number> = { green: 0, yellow: 1, red: 2, critical: 3 };
                        const movement = prev
                          ? rank[point.level] > rank[prev.level] ? '↑' : rank[point.level] < rank[prev.level] ? '↓' : ''
                          : '';
                        return (
                          <div key={point.date} className="flex flex-col items-center gap-2">
                            <div
                              className="w-10 h-10 rounded-full border-4 border-white shadow-md flex items-center justify-center text-white text-xs font-bold"
                              style={{ backgroundColor: RISK_TIMELINE_COLORS[point.level] ?? '#10b981' }}
                              title={`${point.date}: ${RISK_TIMELINE_LABELS[point.level] ?? point.level}`}
                            >
                              {movement}
                            </div>
                            <div className="text-xs text-muted-foreground text-center">
                              {new Date(point.date).toLocaleDateString(undefined, { weekday: 'short' })}
                              <br />
                              <span className="text-[10px]">
                                {new Date(point.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  <div className="py-8 text-center text-sm text-muted-foreground">
                    No risk readings this week -- that's a good sign.
                  </div>
                )}
                <div className="flex items-center gap-4 mt-5 text-xs text-muted-foreground">
                  {Object.entries(RISK_TIMELINE_COLORS).map(([level, color]) => (
                    <span key={level} className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                      {RISK_TIMELINE_LABELS[level]}
                    </span>
                  ))}
                </div>
              </div>

              {/* Today's Insights + Protective & Risk Factors */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                  <h2 className="text-lg font-semibold mb-4">Today's Insights</h2>
                  {insights?.today_insights?.length ? (
                    <div className="space-y-4">
                      {insights.today_insights.map((card, idx) => {
                        const style = insightCardStyles[card.type] ?? insightCardStyles.info;
                        const CardIcon = style.Icon;
                        return (
                          <div key={idx} className={`p-4 ${style.bg} border ${style.border} rounded-lg`}>
                            <div className="flex items-start gap-3">
                              <CardIcon className={`w-5 h-5 ${style.icon} flex-shrink-0 mt-0.5`} />
                              <div>
                                <div className={`font-medium ${style.text}`}>{card.title}</div>
                                <div className={`text-sm ${style.text} opacity-90 mt-1`}>{card.body}</div>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="py-8 text-center text-sm text-muted-foreground">
                      No insights yet -- these appear once your child starts chatting with Comrade.
                    </div>
                  )}
                </div>

                <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                  <h2 className="text-lg font-semibold mb-4">Protective & Risk Factors</h2>
                  {(insights?.protective_factors?.length || insights?.risk_factors?.length) ? (
                    <div className="space-y-5">
                      {insights!.protective_factors.length > 0 && (
                        <div>
                          <div className="text-sm font-medium text-emerald-700 mb-2 flex items-center gap-2">
                            <Shield className="w-4 h-4" /> What's protecting their wellbeing
                          </div>
                          <ul className="space-y-2">
                            {insights!.protective_factors.map((f, idx) => (
                              <li key={idx} className="flex items-start gap-2 text-sm">
                                <CheckCircle className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
                                {f}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {insights!.risk_factors.length > 0 && (
                        <div>
                          <div className="text-sm font-medium text-amber-700 mb-2 flex items-center gap-2">
                            <AlertCircle className="w-4 h-4" /> What to keep an eye on
                          </div>
                          <ul className="space-y-2">
                            {insights!.risk_factors.map((f, idx) => (
                              <li key={idx} className="flex items-start gap-2 text-sm">
                                <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
                                {f}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="py-8 text-center text-sm text-muted-foreground">
                      Factors appear as the AI builds a picture of your child's week.
                    </div>
                  )}
                </div>
              </div>

              {/* Positive changes & areas needing attention */}
              {((insights?.improvements?.length ?? 0) > 0 || (insights?.concerns?.length ?? 0) > 0) && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                    <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                      <TrendingUp className="w-5 h-5 text-emerald-600" />
                      Positive Changes
                    </h2>
                    {insights?.improvements?.length ? (
                      <ul className="space-y-3">
                        {insights.improvements.map((item, idx) => (
                          <li key={idx} className="flex items-start gap-3 text-sm">
                            <CheckCircle className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-muted-foreground py-4 text-center">
                        Nothing highlighted this week.
                      </p>
                    )}
                  </div>
                  <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                    <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                      <AlertCircle className="w-5 h-5 text-amber-600" />
                      Areas Needing Attention
                    </h2>
                    {insights?.concerns?.length ? (
                      <ul className="space-y-3">
                        {insights.concerns.map((item, idx) => (
                          <li key={idx} className="flex items-start gap-3 text-sm">
                            <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-muted-foreground py-4 text-center">
                        No areas of concern right now.
                      </p>
                    )}
                  </div>
                </div>
              )}
            </>
          )}

          {/* ── Recommendations tab ── */}
          {selectedChild && !isLoadingInsights && tab === 'recommendations' && (
            <>
              {/* Today's recommendation */}
              <div className="bg-gradient-to-r from-primary to-secondary rounded-2xl p-6 md:p-8 text-white">
                <div className="text-sm text-blue-100 mb-2 flex items-center gap-2">
                  <Sparkles className="w-4 h-4" /> Today's recommendation
                </div>
                <p className="text-lg md:text-xl font-medium leading-relaxed">
                  {insights?.recommendations?.[0]
                    ?? 'Check back after your child has a few conversations -- personalized guidance appears here.'}
                </p>
              </div>

              {/* This week's focus */}
              {weeklyReport && weeklyReport.focus_areas.length > 0 && (
                <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                  <h2 className="text-lg font-semibold mb-4">This Week's Focus</h2>
                  <div className="grid md:grid-cols-2 gap-3">
                    {weeklyReport.focus_areas.map((f, idx) => (
                      <div key={idx} className="p-4 bg-blue-50 border border-blue-200 rounded-lg text-blue-900">
                        {f}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* All recommendations, readable cards */}
              <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                <h2 className="text-lg font-semibold mb-4">Parenting Recommendations</h2>
                {insights?.recommendations?.length ? (
                  <div className="grid md:grid-cols-2 gap-4">
                    {insights.recommendations.map((rec, idx) => (
                      <div key={idx} className="p-5 bg-muted/50 border border-border rounded-xl">
                        <div className="flex items-start gap-3">
                          <div className="w-7 h-7 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-semibold shrink-0">
                            {idx + 1}
                          </div>
                          <p className="text-[15px] leading-relaxed">{rec}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-8 text-center text-sm text-muted-foreground">
                    No recommendations yet -- check back after your child has a few conversations.
                  </div>
                )}
              </div>

              {/* Going well / strengths + small wins */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                  <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                    <CheckCircle className="w-5 h-5 text-emerald-600" /> Things Going Well
                  </h2>
                  {(insights?.improvements?.length || weeklyReport?.highlights?.length) ? (
                    <ul className="space-y-3">
                      {[...(insights?.improvements ?? []), ...(weeklyReport?.highlights ?? [])]
                        .slice(0, 6)
                        .map((item, idx) => (
                          <li key={idx} className="flex items-start gap-3 text-sm">
                            <CheckCircle className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
                            {item}
                          </li>
                        ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-muted-foreground py-4 text-center">
                      Small wins show up here as they happen.
                    </p>
                  )}
                </div>
                <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                  <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                    <Shield className="w-5 h-5 text-primary" /> Strengths
                  </h2>
                  {insights?.protective_factors?.length ? (
                    <ul className="space-y-3">
                      {insights.protective_factors.map((f, idx) => (
                        <li key={idx} className="flex items-start gap-3 text-sm">
                          <Shield className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                          {f}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-muted-foreground py-4 text-center">
                      Strengths appear as the AI learns what supports your child.
                    </p>
                  )}
                </div>
              </div>

              {/* Habits to support */}
              {(insights?.concerns?.length ?? 0) > 0 && (
                <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                  <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                    <AlertCircle className="w-5 h-5 text-amber-600" /> Habits to Support
                  </h2>
                  <ul className="space-y-3">
                    {insights!.concerns.map((item, idx) => (
                      <li key={idx} className="flex items-start gap-3 text-sm">
                        <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Why am I seeing this? */}
              <div className="bg-muted/50 border border-border rounded-xl p-6">
                <h2 className="text-base font-semibold mb-2 flex items-center gap-2">
                  <HelpCircle className="w-4 h-4 text-primary" /> Why am I seeing this?
                </h2>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  These recommendations are generated by Kio's AI from aggregated signals only:
                  your child's wellness score components, mood check-in patterns, AI-analyzed
                  stress topics, and risk trajectory. The AI never reads you their conversations --
                  it summarizes patterns so you can support them without breaking their trust.
                  {insights?.last_updated && (
                    <> Last generated {new Date(insights.last_updated).toLocaleString()}.</>
                  )}
                </p>
              </div>
            </>
          )}

          {/* ── Family Activities tab ── */}
          {selectedChild && !isLoadingInsights && tab === 'activities' && (
            <>
              <div className="bg-gradient-to-r from-primary to-secondary rounded-2xl p-6 md:p-8 text-white">
                <h2 className="text-xl font-semibold mb-1 flex items-center gap-2">
                  <Heart className="w-5 h-5" /> Family Activities
                </h2>
                <p className="text-sm text-blue-100">
                  Small shared moments, chosen for {selectedChild.first_name}'s current state.
                  Doing things together is one of the strongest protective factors there is.
                </p>
              </div>

              <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                <h2 className="text-lg font-semibold mb-4">This Week Together</h2>
                {insights?.family_activities?.length ? (
                  <div className="grid md:grid-cols-2 gap-4">
                    {insights.family_activities.map((activity, idx) => (
                      <div key={idx} className="p-5 bg-accent/10 border border-accent/30 rounded-xl flex items-start gap-3">
                        <Sparkles className="w-5 h-5 text-primary mt-0.5 shrink-0" />
                        <p className="text-[15px] leading-relaxed">{activity}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-8 text-center text-sm text-muted-foreground">
                    Personalized family activities appear after your child's first few conversations.
                  </div>
                )}
              </div>

              <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                <h2 className="text-lg font-semibold mb-1 flex items-center gap-2">
                  <MessageCircle className="w-5 h-5 text-primary" /> Conversation Starters
                </h2>
                <p className="text-xs text-muted-foreground mb-4">
                  {insights?.family_communication?.length
                    ? "Tailored to your child's week."
                    : 'General approaches that build connection.'}
                </p>
                <div className="grid md:grid-cols-2 gap-4">
                  {(insights?.family_communication?.length
                    ? insights.family_communication
                    : [
                        'Ask open-ended questions instead of yes/no questions',
                        'Listen without immediately offering solutions',
                        'Validate their feelings before giving advice',
                        'Share your own challenges to build connection',
                      ]
                  ).map((tip, idx) => (
                    <div key={idx} className="p-5 bg-muted/50 border border-border rounded-xl flex items-start gap-3">
                      <MessageCircle className="w-5 h-5 text-secondary mt-0.5 shrink-0" />
                      <p className="text-[15px] leading-relaxed">{tip}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-muted/50 border border-border rounded-xl p-6">
                <h2 className="text-base font-semibold mb-2 flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-primary" /> A gentle rhythm
                </h2>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Aim for one shared activity and one real conversation this week. These refresh
                  automatically as {selectedChild.first_name}'s week evolves.
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
