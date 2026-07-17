/**
 * Student Activities — AI-personalized wellbeing activities plus pattern-mined
 * personal insights (shown only once enough check-in history exists).
 */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowLeft,
  BookOpen,
  Check,
  Clock,
  Flower2,
  Footprints,
  Lightbulb,
  Loader2,
  Moon,
  Palette,
  RefreshCw,
  Sparkles,
  Users,
} from 'lucide-react';
import { KioLogo } from './KioLogo';
import api from '../../lib/api';
import type {
  ActivitiesResponse,
  ActivityItem,
  PersonalInsightsResponse,
  WeeklyReportResponse,
} from '../../lib/types';

const CATEGORY_STYLE: Record<
  ActivityItem['category'],
  { Icon: typeof Flower2; bg: string; text: string; label: string }
> = {
  mindfulness: { Icon: Flower2, bg: 'bg-teal-50 border-teal-200', text: 'text-teal-700', label: 'Mindfulness' },
  physical: { Icon: Footprints, bg: 'bg-emerald-50 border-emerald-200', text: 'text-emerald-700', label: 'Physical' },
  social: { Icon: Users, bg: 'bg-blue-50 border-blue-200', text: 'text-blue-700', label: 'Social' },
  reflection: { Icon: BookOpen, bg: 'bg-indigo-50 border-indigo-200', text: 'text-indigo-700', label: 'Reflection' },
  rest: { Icon: Moon, bg: 'bg-purple-50 border-purple-200', text: 'text-purple-700', label: 'Rest' },
  creative: { Icon: Palette, bg: 'bg-pink-50 border-pink-200', text: 'text-pink-700', label: 'Creative' },
};

export function StudentActivities() {
  const [activities, setActivities] = useState<ActivitiesResponse | null>(null);
  const [insights, setInsights] = useState<PersonalInsightsResponse | null>(null);
  const [weeklyReport, setWeeklyReport] = useState<WeeklyReportResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  // Optimistic completions layered over the persisted `completed` flags
  const [justCompleted, setJustCompleted] = useState<Set<string>>(new Set());

  const fetchAll = useCallback(async (refresh = false) => {
    refresh ? setIsRefreshing(true) : setIsLoading(true);
    try {
      const [activitiesRes, insightsRes, reportRes] = await Promise.all([
        api.get<ActivitiesResponse>('/wellness/activities'),
        api.get<PersonalInsightsResponse>('/wellness/insights'),
        api.get<WeeklyReportResponse>('/wellness/weekly-report').catch(() => null),
      ]);
      setActivities(activitiesRes.data);
      setInsights(insightsRes.data);
      if (reportRes) setWeeklyReport(reportRes.data);
    } catch {
      // keep whatever we had
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const isDone = (activity: ActivityItem) =>
    activity.completed || justCompleted.has(activity.activity_id);

  const markDone = async (activity: ActivityItem) => {
    if (isDone(activity)) return;
    setJustCompleted((prev) => new Set(prev).add(activity.activity_id));
    try {
      await api.post('/wellness/activities/complete', {
        activity_id: activity.activity_id,
        title: activity.title,
      });
    } catch {
      // 409 = already completed elsewhere; either way the tick stands
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-teal-50">
      {/* Header */}
      <header className="bg-white border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              to="/student"
              className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition text-sm"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="hidden sm:inline">Back to Dashboard</span>
            </Link>
            <div className="hidden sm:block w-px h-6 bg-border"></div>
            <KioLogo className="h-7 w-auto" />
          </div>
          <button
            onClick={() => fetchAll(true)}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm border border-border hover:bg-muted transition disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-8">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-24 gap-3">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Picking activities for you…</p>
          </div>
        ) : (
          <>
            {/* Weekly report */}
            {weeklyReport && (
              <section className="bg-gradient-to-r from-primary to-secondary rounded-2xl p-6 text-white">
                <div className="flex items-center justify-between mb-2">
                  <h1 className="text-lg font-semibold flex items-center gap-2">
                    <Sparkles className="w-5 h-5" /> Your week at a glance
                  </h1>
                  <span className="text-xs text-blue-100">
                    Week of {new Date(weeklyReport.week_start).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                  </span>
                </div>
                <p className="font-medium mb-1">{weeklyReport.headline}</p>
                <p className="text-sm text-blue-100 mb-3">{weeklyReport.summary}</p>
                {weeklyReport.highlights.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {weeklyReport.highlights.map((h, idx) => (
                      <span key={idx} className="text-xs px-3 py-1.5 bg-white/15 rounded-full">
                        {h}
                      </span>
                    ))}
                  </div>
                )}
              </section>
            )}

            {/* Personal insights */}
            <section>
              <div className="flex items-center gap-2 mb-4">
                <Lightbulb className="w-5 h-5 text-primary" />
                <h1 className="text-lg font-semibold">Personal insights</h1>
              </div>
              {insights?.sufficient_data && insights.insights.length > 0 ? (
                <div className="grid gap-3 md:grid-cols-2">
                  {insights.insights.map((insight, idx) => (
                    <div key={idx} className="bg-white border border-border rounded-xl p-4 shadow-sm">
                      <div className="font-medium mb-1">{insight.title}</div>
                      <p className="text-sm text-muted-foreground">{insight.body}</p>
                      <p className="text-xs text-muted-foreground/70 mt-2">{insight.evidence}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="bg-white border border-dashed border-border rounded-xl p-6 text-center">
                  <p className="text-sm text-muted-foreground">
                    {insights && !insights.sufficient_data
                      ? `Keep checking in daily and Kio will start noticing your patterns — ${insights.checkin_days} of 7 days so far.`
                      : 'No clear patterns yet — they appear as your history grows.'}
                  </p>
                </div>
              )}
            </section>

            {/* Activities */}
            <section>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-primary" />
                  <h2 className="text-lg font-semibold">For you today</h2>
                </div>
                {activities && (
                  <span className="text-xs px-2.5 py-1 rounded-full bg-accent/15 text-primary font-medium">
                    {activities.personalized ? 'Personalized by Kio' : 'Based on your recent signals'}
                  </span>
                )}
              </div>

              {activities && activities.activities.length > 0 ? (
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  {activities.activities.map((activity) => {
                    const style = CATEGORY_STYLE[activity.category] ?? CATEGORY_STYLE.mindfulness;
                    const done = isDone(activity);
                    return (
                      <div
                        key={activity.activity_id}
                        className={`bg-white border rounded-xl p-5 shadow-sm transition flex flex-col ${
                          done
                            ? 'border-accent/60 bg-accent/5'
                            : activity.is_daily
                            ? 'border-secondary/50 ring-1 ring-secondary/20'
                            : 'border-border hover:shadow-md'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3 mb-3">
                          <div className="flex items-center gap-2 flex-wrap">
                            <div className={`flex items-center gap-2 px-2.5 py-1 rounded-full border text-xs font-medium ${style.bg} ${style.text}`}>
                              <style.Icon className="w-3.5 h-3.5" />
                              {style.label}
                            </div>
                            {activity.is_daily && (
                              <span className="px-2.5 py-1 rounded-full bg-secondary/10 text-secondary text-xs font-medium">
                                Today's pick
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-1 text-xs text-muted-foreground shrink-0">
                            <Clock className="w-3.5 h-3.5" />
                            {activity.duration_minutes} min
                          </div>
                        </div>
                        <h3 className="font-semibold mb-1">{activity.title}</h3>
                        <p className="text-sm text-muted-foreground mb-3">{activity.description}</p>
                        <p className="text-xs text-muted-foreground/80 italic mb-4 flex-1">{activity.reason}</p>
                        <button
                          onClick={() => markDone(activity)}
                          disabled={done}
                          className={`w-full py-2 rounded-lg text-sm font-medium transition flex items-center justify-center gap-2 ${
                            done
                              ? 'bg-accent/20 text-primary cursor-default'
                              : 'bg-primary text-primary-foreground hover:bg-primary/90'
                          }`}
                        >
                          {done ? (
                            <>
                              <Check className="w-4 h-4" /> Completed ✓
                            </>
                          ) : (
                            'Mark as done'
                          )}
                        </button>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="bg-white border border-dashed border-border rounded-xl p-8 text-center">
                  <p className="text-sm text-muted-foreground">
                    No suggestions right now — complete today's check-in and try again.
                  </p>
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
