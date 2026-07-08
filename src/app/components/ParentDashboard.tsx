import { Link } from 'react-router-dom';
import { Brain, TrendingUp, TrendingDown, Minus, Heart, AlertCircle, CheckCircle, Info, Calendar, Menu, X, Loader2, RefreshCw, Users, KeyRound } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../lib/auth-context';
import { useChildInsights } from '../../hooks/useChildInsights';
import api from '../../lib/api';
import type { LinkedChildResponse } from '../../lib/types';

export function ParentDashboard() {
  const { user, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Children state
  const [children, setChildren] = useState<LinkedChildResponse[]>([]);
  const [isLoadingChildren, setIsLoadingChildren] = useState(true);
  const [selectedChildId, setSelectedChildId] = useState<string | null>(null);

  // Insights state (live: 5-min poll + refetch-on-focus + manual refresh button)
  const { insights, isLoading: isLoadingInsights, isRefreshing, refetch: refetchInsights } =
    useChildInsights(selectedChildId);

  // Redeem code state
  const [showRedeemForm, setShowRedeemForm] = useState(false);
  const [redeemCode, setRedeemCode] = useState('');
  const [redeemRelationship, setRedeemRelationship] = useState('parent');
  const [isRedeeming, setIsRedeeming] = useState(false);
  const [redeemError, setRedeemError] = useState<string | null>(null);
  const [redeemSuccess, setRedeemSuccess] = useState<string | null>(null);

  // Fetch linked children
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

  // Redeem invite code
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

  const wellnessTrend = insights?.wellness_trend ?? [];
  const stressFactors = insights?.stress_factors ?? [];

  const wellnessScore = insights?.wellness_score ?? selectedChild?.wellness_score ?? null;
  const riskLevel = selectedChild?.risk_level ?? insights?.risk_level ?? 'green';
  const emotionalState = insights?.emotional_state ?? 'Stable';
  const trend = insights?.wellness_breakdown?.trend ?? null;

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
  };
  const riskColor = riskColors[riskLevel] || riskColors.green;

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Sidebar */}
      <div className={`${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0 fixed md:static inset-y-0 left-0 z-50 w-64 bg-sidebar border-r border-sidebar-border transition-transform duration-300 ease-in-out`}>
        <div className="flex flex-col h-full">
          <div className="p-4 border-b border-sidebar-border">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Brain className="w-6 h-6 text-primary" />
                <span className="font-semibold">MindBridge</span>
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

            {/* Link another child */}
            <button
              onClick={() => setShowRedeemForm(!showRedeemForm)}
              className="w-full flex items-center gap-2 px-3 py-2 mt-1 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition text-sm"
            >
              <KeyRound className="w-4 h-4" />
              <span>Link Another Child</span>
            </button>
          </div>

          <nav className="flex-1 p-4 space-y-2">
            <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
              <TrendingUp className="w-5 h-5" />
              <span>Overview</span>
            </a>
            <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition">
              <Heart className="w-5 h-5" />
              <span>Wellness Trends</span>
            </a>
            <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition">
              <AlertCircle className="w-5 h-5" />
              <span>Recommendations</span>
            </a>
            <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition">
              <Calendar className="w-5 h-5" />
              <span>Activities</span>
            </a>
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

        <div className="p-4 md:p-6 space-y-6">
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
                Ask your child to generate an invite code from their MindBridge dashboard, then enter it here to link your accounts.
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

          {/* Content only shows when there's a selected child */}
          {selectedChild && (
            <>
              {/* Privacy Banner */}
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <div className="font-medium text-blue-900">Privacy Reminder</div>
                    <div className="text-sm text-blue-700 mt-1">
                      You're viewing aggregated insights and trends. Raw conversations remain private to ensure your child feels safe to share openly.
                    </div>
                  </div>
                </div>
              </div>

              {/* Overview Cards */}
              {isLoadingInsights ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                      <div className="flex items-center justify-between mb-4">
                        <div className="text-sm text-muted-foreground">Wellness Score</div>
                        {trendDisplay && (
                          <div className={`flex items-center gap-1 text-sm ${trendDisplay.color}`}>
                            <trendDisplay.Icon className="w-4 h-4" />
                            <span>{trendDisplay.label}</span>
                          </div>
                        )}
                      </div>
                      <div className="text-3xl font-bold text-foreground mb-2">
                        {wellnessScore !== null ? `${Math.round(wellnessScore)}/100` : '—'}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {insights?.wellness_breakdown?.explanation
                          || (wellnessScore === null ? 'Not enough data yet' : 'Awaiting first computed score')}
                      </div>
                    </div>

                    <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                      <div className="flex items-center justify-between mb-4">
                        <div className="text-sm text-muted-foreground">Emotional State</div>
                      </div>
                      <div className="text-3xl font-bold text-foreground mb-2">{emotionalState}</div>
                      <div className="text-sm text-muted-foreground">
                        {insights?.summary || 'No AI summary yet -- check back after your child chats with Comrade.'}
                      </div>
                    </div>

                    <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                      <div className="flex items-center justify-between mb-4">
                        <div className="text-sm text-muted-foreground">Risk Level</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className={`w-3 h-3 ${riskColor.dot} rounded-full`}></div>
                        <div className={`text-3xl font-bold ${riskColor.text} capitalize`}>{riskLevel}</div>
                      </div>
                      <div className="text-sm text-muted-foreground mt-2">
                        {riskLevel === 'green' ? 'No immediate concerns' : 'Monitoring recommended'}
                      </div>
                    </div>
                  </div>

                  {/* Wellness Trend Chart */}
                  <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                    <h2 className="text-lg font-semibold mb-4">7-Day Wellness Trend</h2>
                    {wellnessTrend.length > 0 ? (
                      <ResponsiveContainer width="100%" height={250}>
                        <LineChart id="parent-wellness-trend" data={wellnessTrend}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                          <XAxis dataKey="date" stroke="#6b7280" />
                          <YAxis stroke="#6b7280" domain={[0, 100]} />
                          <Tooltip />
                          <Line type="monotone" dataKey="score" stroke="#2563EB" strokeWidth={3} dot={{ r: 4 }} />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="py-12 text-center text-sm text-muted-foreground">
                        Not enough data yet -- the trend appears once your child has a few days of activity.
                      </div>
                    )}
                    {insights?.wellness_breakdown && (
                      <details className="mt-4 group">
                        <summary className="text-sm text-primary cursor-pointer select-none">
                          Why this score?
                        </summary>
                        <div className="mt-3 space-y-2">
                          {Object.entries(insights.wellness_breakdown.components).map(([name, c]) => (
                            <div key={name} className="flex items-center justify-between text-sm">
                              <span className="capitalize text-muted-foreground">{name.replace(/_/g, ' ')}</span>
                              <span className="text-foreground">{c.detail}</span>
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                  </div>

                  {/* Insights & Recommendations */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Current Insights */}
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

                    {/* Recommendations */}
                    <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                      <h2 className="text-lg font-semibold mb-4">Parenting Recommendations</h2>
                      {insights?.recommendations?.length ? (
                        <div className="space-y-4">
                          {insights.recommendations.map((rec, idx) => (
                            <div
                              key={idx}
                              className="p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg"
                            >
                              <p className="text-sm text-blue-800">{rec}</p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="py-8 text-center text-sm text-muted-foreground">
                          No recommendations yet -- check back after your child has a few conversations.
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Stress Factors */}
                  <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                    <h2 className="text-lg font-semibold mb-4">Stress Distribution</h2>
                    {stressFactors.length > 0 ? (
                      <ResponsiveContainer width="100%" height={250}>
                        <BarChart id="parent-stress-factors" data={stressFactors}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                          <XAxis dataKey="name" stroke="#6b7280" />
                          <YAxis stroke="#6b7280" />
                          <Tooltip />
                          <Bar dataKey="value" fill="#2563EB" radius={[8, 8, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="py-12 text-center text-sm text-muted-foreground">
                        No stress signals detected yet.
                      </div>
                    )}
                  </div>

                  {/* Family Communication Tips */}
                  <div className="bg-gradient-to-br from-primary to-secondary rounded-xl p-6 text-white">
                    <h2 className="text-xl font-semibold mb-4">Family Communication Tips</h2>
                    <div className="grid md:grid-cols-2 gap-4">
                      {[
                        "Ask open-ended questions instead of yes/no questions",
                        "Listen without immediately offering solutions",
                        "Validate their feelings before giving advice",
                        "Share your own challenges to build connection"
                      ].map((tip, idx) => (
                        <div key={idx} className="flex items-start gap-3 p-3 bg-white/10 rounded-lg">
                          <CheckCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                          <span className="text-sm">{tip}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
