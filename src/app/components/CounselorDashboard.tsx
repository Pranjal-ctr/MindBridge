import { Calendar, Users, FileText, AlertTriangle, TrendingUp, Menu, X, Loader2, Sparkles } from 'lucide-react';
import { KioLogo } from './KioLogo';
import { useCallback, useEffect, useRef, useState } from 'react';
import { CounselorAvailability } from './CounselorAvailability';
import { CounselorSessions } from './CounselorSessions';
import { ScheduleSessionDialog } from './ScheduleSessionDialog';
import { RiskQueue } from './RiskQueue';
import { NotificationBell } from './NotificationBell';
import { Disclaimer } from './Disclaimer';
import api from '../../lib/api';
import { listSessions, splitSessions } from '../../lib/counselor-api';
import { useAuth } from '../../lib/auth-context';
import type {
  CounselorSession,
  CounselorStudentListResponse,
  CounselorStudentProfile,
  WeeklyReportResponse,
} from '../../lib/types';

export function CounselorDashboard() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [riskQueueCount, setRiskQueueCount] = useState(0);
  const { user, logout } = useAuth();

  const counselorName = user
    ? `${user.first_name} ${user.last_name}`.trim() || user.email
    : 'Counselor';

  // In-page sections — the sidebar scrolls to these rather than routing away.
  const studentsRef = useRef<HTMLDivElement>(null);
  const sessionsRef = useRef<HTMLDivElement>(null);
  const availabilityRef = useRef<HTMLDivElement>(null);
  const riskRef = useRef<HTMLDivElement>(null);

  const scrollTo = useCallback((ref: React.RefObject<HTMLDivElement | null>) => {
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setSidebarOpen(false);
  }, []);

  // Live sessions — owned here so the stat cards and the list share one fetch.
  const [sessions, setSessions] = useState<CounselorSession[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const loadSessions = useCallback(async () => {
    try {
      const data = await listSessions();
      setSessions(data.sessions);
    } catch {
      setSessions([]);
    } finally {
      setIsLoadingSessions(false);
    }
  }, []);
  useEffect(() => { loadSessions(); }, [loadSessions]);

  const [scheduleFor, setScheduleFor] = useState<CounselorStudentProfile | null>(null);

  // Live student roster
  const [students, setStudents] = useState<CounselorStudentProfile[]>([]);
  const [isLoadingStudents, setIsLoadingStudents] = useState(true);
  useEffect(() => {
    let cancelled = false;
    api
      .get<CounselorStudentListResponse>('/counselors/students')
      .then((res) => { if (!cancelled) setStudents(res.data.students); })
      .catch(() => { if (!cancelled) setStudents([]); })
      .finally(() => { if (!cancelled) setIsLoadingStudents(false); });
    return () => { cancelled = true; };
  }, []);

  // Weekly AI report per student (fetched on demand, cached server-side)
  const [openReportFor, setOpenReportFor] = useState<string | null>(null);
  const [reports, setReports] = useState<Record<string, WeeklyReportResponse | 'loading' | 'error'>>({});
  const toggleReport = async (studentId: string) => {
    if (openReportFor === studentId) {
      setOpenReportFor(null);
      return;
    }
    setOpenReportFor(studentId);
    if (reports[studentId] && reports[studentId] !== 'error') return;
    setReports((prev) => ({ ...prev, [studentId]: 'loading' }));
    try {
      const { data } = await api.get<WeeklyReportResponse>(
        `/counselors/students/${studentId}/weekly-report`
      );
      setReports((prev) => ({ ...prev, [studentId]: data }));
    } catch {
      setReports((prev) => ({ ...prev, [studentId]: 'error' }));
    }
  };

  // Stats derived from live data. There is no duration column on
  // counselor_sessions, so "average session length" is deliberately not shown
  // rather than estimated.
  const { upcoming } = splitSessions(sessions);
  const weekAhead = Date.now() + 7 * 24 * 60 * 60 * 1000;
  const upcomingThisWeek = upcoming.filter(
    (s) => new Date(s.scheduled_at).getTime() <= weekAhead
  ).length;
  const completedSessions = sessions.filter((s) => s.status === 'completed').length;

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
              <div className="text-sm font-medium">{counselorName}</div>
              <div className="text-xs text-muted-foreground">Counselor</div>
            </div>
          </div>

          <nav className="flex-1 p-4 space-y-2">
            <button
              onClick={() => scrollTo(studentsRef)}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition"
            >
              <Users className="w-5 h-5" />
              <span>Students</span>
            </button>
            <button
              onClick={() => scrollTo(availabilityRef)}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition"
            >
              <Calendar className="w-5 h-5" />
              <span>Availability</span>
            </button>
            <button
              onClick={() => scrollTo(sessionsRef)}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition"
            >
              <FileText className="w-5 h-5" />
              <span>Sessions &amp; Notes</span>
            </button>
            <button
              onClick={() => scrollTo(riskRef)}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition"
            >
              <AlertTriangle className="w-5 h-5" />
              <span>Risk Alerts</span>
              {riskQueueCount > 0 && (
                <span className="ml-auto px-2 py-0.5 bg-destructive text-destructive-foreground rounded-full text-xs">
                  {riskQueueCount}
                </span>
              )}
            </button>
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

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        {/* Header */}
        <header className="sticky top-0 z-10 h-16 border-b border-border bg-card flex items-center justify-between px-4 md:px-6">
          <div className="flex items-center gap-4">
            <button className="md:hidden" onClick={() => setSidebarOpen(true)}>
              <Menu className="w-6 h-6" />
            </button>
            <h1 className="text-lg font-semibold">Counselor Dashboard</h1>
          </div>
          <div className="flex items-center gap-3">
            {riskQueueCount > 0 && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-100 text-amber-700 rounded-full text-sm">
                <AlertTriangle className="w-4 h-4" />
                <span className="hidden sm:inline">
                  {riskQueueCount} Risk Alert{riskQueueCount === 1 ? '' : 's'}
                </span>
              </div>
            )}
            <NotificationBell />
          </div>
        </header>

        <div className="p-4 md:p-6 space-y-6">
          {/* Quick Stats */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-sm text-muted-foreground mb-1">Active Students</div>
              <div className="text-2xl font-bold text-foreground">
                {isLoadingStudents ? '—' : students.length}
              </div>
            </div>
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-sm text-muted-foreground mb-1">Next 7 Days</div>
              <div className="text-2xl font-bold text-foreground">
                {isLoadingSessions ? '—' : upcomingThisWeek}
              </div>
            </div>
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-sm text-muted-foreground mb-1">Sessions Completed</div>
              <div className="text-2xl font-bold text-foreground">
                {isLoadingSessions ? '—' : completedSessions}
              </div>
            </div>
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-sm text-muted-foreground mb-1">Risk Alerts</div>
              <div className="text-2xl font-bold text-destructive">{riskQueueCount}</div>
            </div>
          </div>

          {/* Risk review queue (live) */}
          <div ref={riskRef}>
            <RiskQueue onCountChange={setRiskQueueCount} />
          </div>

          {/* Availability (live) */}
          <div ref={availabilityRef}>
            <CounselorAvailability />
          </div>

          {/* Sessions & notes (live) */}
          <div ref={sessionsRef}>
            <CounselorSessions
              sessions={sessions}
              isLoading={isLoadingSessions}
              onChanged={loadSessions}
            />
          </div>

          {/* Student Profiles (live) */}
          <div className="space-y-4" ref={studentsRef}>
            <h2 className="text-lg font-semibold">Student Profiles</h2>
            {isLoadingStudents ? (
              <div className="bg-card border border-border rounded-xl p-12 flex items-center justify-center">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : students.length === 0 ? (
              <div className="bg-card border border-dashed border-border rounded-xl p-12 text-center text-sm text-muted-foreground">
                No students in your roster yet.
              </div>
            ) : students.map((student) => {
              const risk = student.risk_level === 'critical' ? 'red' : student.risk_level;
              const name = `${student.first_name} ${student.last_name}`;
              const report = reports[student.student_id];
              return (
              <div key={student.student_id} className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
                {/* Header */}
                <div className={`p-4 flex items-center justify-between ${
                  risk === 'red' ? 'bg-red-50 border-b-2 border-red-300' :
                  risk === 'yellow' ? 'bg-amber-50 border-b-2 border-amber-300' :
                  'bg-emerald-50 border-b-2 border-emerald-300'
                }`}>
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-gradient-to-br from-primary to-secondary rounded-full flex items-center justify-center text-white font-semibold">
                      {student.first_name[0]}{student.last_name[0]}
                    </div>
                    <div>
                      <div className="font-semibold text-foreground">{name}</div>
                      <div className="text-sm text-muted-foreground">
                        {student.age ? `${student.age} years` : 'Age not set'}
                        {student.wellness_score !== null && ` • Wellness ${Math.round(student.wellness_score)}/100`}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className={`px-3 py-1.5 rounded-full text-sm font-medium ${
                      risk === 'red' ? 'bg-red-200 text-red-800' :
                      risk === 'yellow' ? 'bg-amber-200 text-amber-800' :
                      'bg-emerald-200 text-emerald-800'
                    }`}>
                      {risk === 'red' ? 'High Risk' : risk === 'yellow' ? 'Moderate' : 'Low Risk'}
                    </div>
                  </div>
                </div>

                {/* Content */}
                <div className="p-6 space-y-4">
                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <div className="text-sm font-medium text-muted-foreground mb-2">Main Concerns</div>
                      {student.main_concerns.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {student.main_concerns.map((concern, cIdx) => (
                            <span key={cIdx} className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm">
                              {concern}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-sm text-muted-foreground">None recorded</span>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <div className="text-sm font-medium text-muted-foreground mb-1">Last Session</div>
                        <div className="text-sm text-foreground">{student.last_session || 'No sessions yet'}</div>
                      </div>
                      <div>
                        <div className="text-sm font-medium text-muted-foreground mb-1">Emotional Trend</div>
                        <div className="flex items-center gap-2">
                          <TrendingUp className={`w-4 h-4 ${
                            student.emotional_trend === 'Improving' ? 'text-emerald-600' :
                            student.emotional_trend === 'Concerning' ? 'text-red-600' : 'text-gray-600'
                          }`} />
                          <span className="text-sm text-foreground">{student.emotional_trend}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {student.ai_summary && (
                    <div>
                      <div className="text-sm font-medium text-muted-foreground mb-2">AI-Generated Summary</div>
                      <div className={`p-4 rounded-lg text-sm leading-relaxed ${
                        risk === 'red' ? 'bg-red-50 text-red-900 border border-red-200' :
                        risk === 'yellow' ? 'bg-amber-50 text-amber-900 border border-amber-200' :
                        'bg-blue-50 text-blue-900 border border-blue-200'
                      }`}>
                        {student.ai_summary}
                      </div>
                    </div>
                  )}

                  {/* Weekly AI report (on demand) */}
                  <div>
                    <button
                      onClick={() => toggleReport(student.student_id)}
                      className="flex items-center gap-2 text-sm text-primary hover:underline"
                    >
                      <Sparkles className="w-4 h-4" />
                      {openReportFor === student.student_id ? 'Hide weekly report' : "This week's AI report"}
                    </button>
                    {openReportFor === student.student_id && (
                      <div className="mt-3 p-4 bg-muted/60 border border-border rounded-lg">
                        {report === 'loading' || !report ? (
                          <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
                            <Loader2 className="w-4 h-4 animate-spin" /> Generating report…
                          </div>
                        ) : report === 'error' ? (
                          <p className="text-sm text-red-600">Could not load the weekly report.</p>
                        ) : (
                          <div className="space-y-3 text-sm">
                            <div className="font-medium">{report.headline}</div>
                            <p className="text-muted-foreground">{report.summary}</p>
                            {report.highlights.length > 0 && (
                              <div>
                                <span className="font-medium">Highlights: </span>
                                {report.highlights.join(' · ')}
                              </div>
                            )}
                            {report.focus_areas.length > 0 && (
                              <div>
                                <span className="font-medium">Suggested focus: </span>
                                {report.focus_areas.join(' · ')}
                              </div>
                            )}
                            <div className="text-xs text-muted-foreground">
                              Week of {new Date(report.week_start).toLocaleDateString()}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Notes attach to a session, so there is no student-level
                      "Add Note" — scheduling comes first, then notes on it. */}
                  <div className="flex gap-3 pt-2">
                    <button
                      onClick={() => setScheduleFor(student)}
                      className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition"
                    >
                      Schedule Session
                    </button>
                    <button
                      onClick={() => scrollTo(sessionsRef)}
                      className="px-4 py-2 bg-muted text-foreground rounded-lg hover:bg-muted/80 transition"
                    >
                      Sessions &amp; Notes
                    </button>
                  </div>
                </div>
              </div>
              );
            })}
          </div>

          {/* Non-diagnostic disclaimer */}
          <Disclaimer variant="full" className="pt-2" />

          {scheduleFor && (
            <ScheduleSessionDialog
              studentId={scheduleFor.student_id}
              studentName={`${scheduleFor.first_name} ${scheduleFor.last_name}`}
              onClose={() => setScheduleFor(null)}
              onScheduled={loadSessions}
            />
          )}
        </div>
      </div>
    </div>
  );
}
