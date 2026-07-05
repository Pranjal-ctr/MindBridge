import { Link } from 'react-router-dom';
import { Brain, Users, TrendingUp, AlertTriangle, Calendar, BarChart3, Menu, X } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, BarChart, Bar } from 'recharts';
import { useState } from 'react';

export function SchoolAdminDashboard() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const wellnessTrend = [
    { month: 'Jan', score: 68 },
    { month: 'Feb', score: 70 },
    { month: 'Mar', score: 67 },
    { month: 'Apr', score: 72 },
    { month: 'May', score: 75 },
    { month: 'Jun', score: 73 }
  ];

  const riskDistribution = [
    { name: 'Low Risk', value: 780, color: '#10b981' },
    { name: 'Moderate', value: 165, color: '#f59e0b' },
    { name: 'High Risk', value: 25, color: '#ef4444' }
  ];

  const stressByCategory = [
    { category: 'Academic', students: 320 },
    { category: 'Social', students: 180 },
    { category: 'Family', students: 95 },
    { category: 'Future', students: 215 }
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
              <div className="text-sm font-medium">Riverside High School</div>
              <div className="text-xs text-muted-foreground">Admin Portal</div>
            </div>
          </div>

          <nav className="flex-1 p-4 space-y-2">
            <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
              <BarChart3 className="w-5 h-5" />
              <span>Analytics</span>
            </a>
            <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition">
              <Users className="w-5 h-5" />
              <span>Students</span>
            </a>
            <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition">
              <Users className="w-5 h-5" />
              <span>Counselors</span>
            </a>
            <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition">
              <Calendar className="w-5 h-5" />
              <span>Reports</span>
            </a>
            <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition">
              <AlertTriangle className="w-5 h-5" />
              <span>Alerts</span>
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
            <h1 className="text-lg font-semibold">School Analytics Dashboard</h1>
          </div>
          <div className="text-sm text-muted-foreground">
            <span className="hidden sm:inline">Last updated: </span>June 8, 2026
          </div>
        </header>

        <div className="p-4 md:p-6 space-y-6">
          {/* Privacy Notice */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div>
                <div className="font-medium text-blue-900">Anonymous Analytics</div>
                <div className="text-sm text-blue-700 mt-1">
                  All data is aggregated and anonymized to protect student privacy. Individual student conversations are never accessible at the school level.
                </div>
              </div>
            </div>
          </div>

          {/* Key Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-xl p-6 shadow-lg">
              <div className="flex items-center justify-between mb-2">
                <Users className="w-8 h-8 opacity-80" />
                <TrendingUp className="w-5 h-5" />
              </div>
              <div className="text-3xl font-bold mb-1">970</div>
              <div className="text-sm text-blue-100">Total Active Students</div>
            </div>

            <div className="bg-gradient-to-br from-emerald-500 to-emerald-600 text-white rounded-xl p-6 shadow-lg">
              <div className="flex items-center justify-between mb-2">
                <BarChart3 className="w-8 h-8 opacity-80" />
                <span className="text-sm">↑ 3pts</span>
              </div>
              <div className="text-3xl font-bold mb-1">73/100</div>
              <div className="text-sm text-emerald-100">Avg Wellness Score</div>
            </div>

            <div className="bg-gradient-to-br from-purple-500 to-purple-600 text-white rounded-xl p-6 shadow-lg">
              <div className="flex items-center justify-between mb-2">
                <Users className="w-8 h-8 opacity-80" />
              </div>
              <div className="text-3xl font-bold mb-1">8</div>
              <div className="text-sm text-purple-100">Active Counselors</div>
            </div>

            <div className="bg-gradient-to-br from-amber-500 to-amber-600 text-white rounded-xl p-6 shadow-lg">
              <div className="flex items-center justify-between mb-2">
                <Calendar className="w-8 h-8 opacity-80" />
              </div>
              <div className="text-3xl font-bold mb-1">87%</div>
              <div className="text-sm text-amber-100">Counselor Utilization</div>
            </div>
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Wellness Trend */}
            <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
              <h2 className="text-lg font-semibold mb-4">6-Month Wellness Trend</h2>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart id="admin-wellness-trend" data={wellnessTrend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="month" stroke="#6b7280" />
                  <YAxis stroke="#6b7280" domain={[0, 100]} />
                  <Tooltip />
                  <Line type="monotone" dataKey="score" stroke="#2563EB" strokeWidth={3} dot={{ r: 5 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Risk Distribution */}
            <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
              <h2 className="text-lg font-semibold mb-4">Student Risk Distribution</h2>
              <div className="flex items-center justify-between">
                <ResponsiveContainer width="50%" height={250}>
                  <PieChart>
                    <Pie
                      data={riskDistribution}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={90}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {riskDistribution.map((entry) => (
                        <Cell key={entry.name} fill={entry.color} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-3">
                  {riskDistribution.map((item, idx) => (
                    <div key={idx} className="flex items-center gap-3">
                      <div className="w-4 h-4 rounded" style={{ backgroundColor: item.color }}></div>
                      <div>
                        <div className="font-medium text-sm">{item.name}</div>
                        <div className="text-xs text-muted-foreground">{item.value} students</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Stress Distribution */}
          <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
            <h2 className="text-lg font-semibold mb-4">Primary Stress Factors</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart id="admin-stress-categories" data={stressByCategory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="category" stroke="#6b7280" />
                <YAxis stroke="#6b7280" />
                <Tooltip />
                <Bar dataKey="students" fill="#2563EB" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Insights & Recommendations */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Key Insights */}
            <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
              <h2 className="text-lg font-semibold mb-4">Key Insights</h2>
              <div className="space-y-3">
                <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
                  <div className="flex items-start gap-3">
                    <TrendingUp className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <div className="font-medium text-emerald-900">Positive Trend</div>
                      <div className="text-sm text-emerald-700 mt-1">
                        Overall wellness scores have improved by 5% over the last quarter.
                      </div>
                    </div>
                  </div>
                </div>

                <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <div className="font-medium text-amber-900">Academic Stress Peak</div>
                      <div className="text-sm text-amber-700 mt-1">
                        33% of students report high academic stress. Consider exam schedule adjustments.
                      </div>
                    </div>
                  </div>
                </div>

                <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <div className="flex items-start gap-3">
                    <Users className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <div className="font-medium text-blue-900">High Engagement</div>
                      <div className="text-sm text-blue-700 mt-1">
                        87% of students are actively using the platform. 14-day avg streak.
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Action Items */}
            <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
              <h2 className="text-lg font-semibold mb-4">Recommended Actions</h2>
              <div className="space-y-3">
                <div className="p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg">
                  <h3 className="font-medium text-blue-900 mb-2">Schedule Wellness Workshop</h3>
                  <p className="text-sm text-blue-700 mb-3">
                    Given high academic stress levels, consider hosting a stress management workshop for 11th and 12th graders.
                  </p>
                  <button className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition">
                    Schedule Workshop
                  </button>
                </div>

                <div className="p-4 bg-gradient-to-r from-purple-50 to-pink-50 border border-purple-200 rounded-lg">
                  <h3 className="font-medium text-purple-900 mb-2">Increase Counselor Capacity</h3>
                  <p className="text-sm text-purple-700 mb-3">
                    25 high-risk students detected. Consider adding counselor hours or hiring additional staff.
                  </p>
                  <button className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm hover:bg-purple-700 transition">
                    Review Staffing
                  </button>
                </div>

                <div className="p-4 bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200 rounded-lg">
                  <h3 className="font-medium text-emerald-900 mb-2">Parent Communication</h3>
                  <p className="text-sm text-emerald-700">
                    Send monthly wellness newsletter to parents highlighting positive trends and resources.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Monthly Report */}
          <div className="bg-gradient-to-br from-primary to-secondary rounded-xl p-6 text-white">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-xl font-semibold">Monthly Wellness Report</h2>
                <p className="text-sm text-blue-100 mt-1">May 2026 Report Available</p>
              </div>
              <button className="px-6 py-3 bg-white text-primary rounded-lg font-medium hover:bg-blue-50 transition">
                Download Report
              </button>
            </div>
            <div className="grid md:grid-cols-3 gap-4 mt-4">
              <div className="bg-white/10 rounded-lg p-3">
                <div className="text-2xl font-bold">1,247</div>
                <div className="text-sm text-blue-100">Total Interactions</div>
              </div>
              <div className="bg-white/10 rounded-lg p-3">
                <div className="text-2xl font-bold">89</div>
                <div className="text-sm text-blue-100">Counselor Sessions</div>
              </div>
              <div className="bg-white/10 rounded-lg p-3">
                <div className="text-2xl font-bold">97%</div>
                <div className="text-sm text-blue-100">Parent Satisfaction</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
