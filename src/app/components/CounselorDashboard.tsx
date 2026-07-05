import { Link } from 'react-router-dom';
import { Brain, Calendar, Users, FileText, AlertTriangle, TrendingUp, Clock, Menu, X } from 'lucide-react';
import { useState } from 'react';
import { CounselorAvailability } from './CounselorAvailability';

export function CounselorDashboard() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const upcomingSessions = [
    { student: 'Sarah J.', time: '2:00 PM Today', risk: 'yellow', topic: 'Academic stress' },
    { student: 'Mike T.', time: '3:30 PM Today', risk: 'green', topic: 'Follow-up session' },
    { student: 'Emily R.', time: '10:00 AM Tomorrow', risk: 'red', topic: 'Urgent - Family issues' }
  ];

  const studentProfiles = [
    {
      name: 'Sarah Johnson',
      age: 16,
      grade: '11th',
      risk: 'yellow',
      lastSession: '3 days ago',
      mainConcerns: ['Exam anxiety', 'Sleep issues', 'Academic pressure'],
      emotionalTrend: 'Improving',
      aiSummary: 'Student has been experiencing increased anxiety around upcoming final exams. Shows good engagement with coping strategies. Sleep patterns have improved from 5 to 6.5 hours. Recommend continuing with stress management techniques and monitoring academic workload.'
    },
    {
      name: 'Mike Thompson',
      age: 17,
      grade: '12th',
      risk: 'green',
      lastSession: '1 week ago',
      mainConcerns: ['College decisions', 'Future planning'],
      emotionalTrend: 'Stable',
      aiSummary: 'Student is navigating college application process well. Shows healthy coping mechanisms and strong support system. No immediate concerns. Continue regular check-ins.'
    },
    {
      name: 'Emily Rodriguez',
      age: 15,
      grade: '10th',
      risk: 'red',
      lastSession: 'Yesterday',
      mainConcerns: ['Family conflict', 'Social isolation', 'Depression symptoms'],
      emotionalTrend: 'Concerning',
      aiSummary: 'Student has expressed persistent feelings of sadness and withdrawal. Recent family conflict involving parental separation. AI detected keywords indicating possible depression. IMMEDIATE FOLLOW-UP RECOMMENDED. Consider family counseling referral.'
    }
  ];

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
              <div className="text-sm font-medium">Dr. Jennifer Martinez</div>
              <div className="text-xs text-muted-foreground">Licensed Counselor</div>
            </div>
          </div>

          <nav className="flex-1 p-4 space-y-2">
            <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
              <Users className="w-5 h-5" />
              <span>Students</span>
            </a>
            <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition">
              <Calendar className="w-5 h-5" />
              <span>Schedule</span>
            </a>
            <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition">
              <FileText className="w-5 h-5" />
              <span>Session Notes</span>
            </a>
            <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition">
              <AlertTriangle className="w-5 h-5" />
              <span>Risk Alerts</span>
              <span className="ml-auto px-2 py-0.5 bg-destructive text-destructive-foreground rounded-full text-xs">1</span>
            </a>
          </nav>

          <div className="p-4 border-t border-sidebar-border">
            <Link to="/" className="flex items-center justify-center px-3 py-2 rounded-lg text-muted-foreground hover:bg-sidebar-accent transition text-sm">
              Sign Out
            </Link>
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
          <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-100 text-amber-700 rounded-full text-sm">
            <AlertTriangle className="w-4 h-4" />
            <span className="hidden sm:inline">1 Risk Alert</span>
          </div>
        </header>

        <div className="p-4 md:p-6 space-y-6">
          {/* Quick Stats */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-sm text-muted-foreground mb-1">Active Students</div>
              <div className="text-2xl font-bold text-foreground">24</div>
            </div>
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-sm text-muted-foreground mb-1">This Week</div>
              <div className="text-2xl font-bold text-foreground">12</div>
            </div>
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-sm text-muted-foreground mb-1">Avg Session Time</div>
              <div className="text-2xl font-bold text-foreground">45m</div>
            </div>
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-sm text-muted-foreground mb-1">Risk Alerts</div>
              <div className="text-2xl font-bold text-destructive">1</div>
            </div>
          </div>

          {/* Availability (live) */}
          <CounselorAvailability />

          {/* Upcoming Sessions */}
          <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
            <h2 className="text-lg font-semibold mb-4">Upcoming Sessions</h2>
            <div className="space-y-3">
              {upcomingSessions.map((session, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-4 bg-muted rounded-lg hover:bg-muted/80 transition"
                >
                  <div className="flex items-center gap-4">
                    <div className={`w-3 h-3 rounded-full ${
                      session.risk === 'red' ? 'bg-destructive' :
                      session.risk === 'yellow' ? 'bg-warning' : 'bg-success'
                    }`}></div>
                    <div>
                      <div className="font-medium">{session.student}</div>
                      <div className="text-sm text-muted-foreground">{session.topic}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Clock className="w-4 h-4" />
                      {session.time}
                    </div>
                    <button className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm hover:bg-primary/90 transition">
                      View Details
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Student Profiles */}
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Student Profiles</h2>
            {studentProfiles.map((student, idx) => (
              <div key={idx} className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
                {/* Header */}
                <div className={`p-4 flex items-center justify-between ${
                  student.risk === 'red' ? 'bg-red-50 border-b-2 border-red-300' :
                  student.risk === 'yellow' ? 'bg-amber-50 border-b-2 border-amber-300' :
                  'bg-emerald-50 border-b-2 border-emerald-300'
                }`}>
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-gradient-to-br from-primary to-secondary rounded-full flex items-center justify-center text-white font-semibold">
                      {student.name.split(' ').map(n => n[0]).join('')}
                    </div>
                    <div>
                      <div className="font-semibold text-foreground">{student.name}</div>
                      <div className="text-sm text-muted-foreground">{student.age} years • {student.grade} Grade</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className={`px-3 py-1.5 rounded-full text-sm font-medium ${
                      student.risk === 'red' ? 'bg-red-200 text-red-800' :
                      student.risk === 'yellow' ? 'bg-amber-200 text-amber-800' :
                      'bg-emerald-200 text-emerald-800'
                    }`}>
                      {student.risk === 'red' ? 'High Risk' : student.risk === 'yellow' ? 'Moderate' : 'Low Risk'}
                    </div>
                  </div>
                </div>

                {/* Content */}
                <div className="p-6 space-y-4">
                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <div className="text-sm font-medium text-muted-foreground mb-2">Main Concerns</div>
                      <div className="flex flex-wrap gap-2">
                        {student.mainConcerns.map((concern, cIdx) => (
                          <span key={cIdx} className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm">
                            {concern}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <div className="text-sm font-medium text-muted-foreground mb-1">Last Session</div>
                        <div className="text-sm text-foreground">{student.lastSession}</div>
                      </div>
                      <div>
                        <div className="text-sm font-medium text-muted-foreground mb-1">Emotional Trend</div>
                        <div className="flex items-center gap-2">
                          <TrendingUp className={`w-4 h-4 ${
                            student.emotionalTrend === 'Improving' ? 'text-emerald-600' :
                            student.emotionalTrend === 'Concerning' ? 'text-red-600' : 'text-gray-600'
                          }`} />
                          <span className="text-sm text-foreground">{student.emotionalTrend}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div>
                    <div className="text-sm font-medium text-muted-foreground mb-2">AI-Generated Summary</div>
                    <div className={`p-4 rounded-lg text-sm leading-relaxed ${
                      student.risk === 'red' ? 'bg-red-50 text-red-900 border border-red-200' :
                      student.risk === 'yellow' ? 'bg-amber-50 text-amber-900 border border-amber-200' :
                      'bg-blue-50 text-blue-900 border border-blue-200'
                    }`}>
                      {student.aiSummary}
                    </div>
                  </div>

                  <div className="flex gap-3 pt-2">
                    <button className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition">
                      Schedule Session
                    </button>
                    <button className="px-4 py-2 bg-muted text-foreground rounded-lg hover:bg-muted/80 transition">
                      View Full History
                    </button>
                    <button className="px-4 py-2 bg-muted text-foreground rounded-lg hover:bg-muted/80 transition">
                      Add Note
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
