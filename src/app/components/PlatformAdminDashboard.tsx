/**
 * MindBridge Platform Admin Dashboard (super admin)
 * School registration, seat/subscription management, staff provisioning,
 * and break-glass access to student chats for severe cases.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  Brain,
  Building2,
  FlaskConical,
  Loader2,
  LogOut,
  MessageSquare,
  Plus,
  ShieldAlert,
  Users,
  X,
} from 'lucide-react';
import api from '../../lib/api';
import { useAuth } from '../../lib/auth-context';

// ── Types ─────────────────────────────────────────────────────────────

interface TenantRow {
  tenant_id: string;
  tenant_name: string;
  tenant_type: string;
  school_code: string | null;
  subscription_plan: string;
  student_limit: number;
  status: string;
}

interface TenantDetail extends TenantRow {
  stats: {
    students: number;
    parents: number;
    counselors: number;
    school_admins: number;
    seats_used: number;
    seat_limit: number;
  };
  subscription: {
    plan_name: string;
    student_limit: number;
    billing_cycle: string;
    amount: number;
    start_date: string;
    renewal_date: string | null;
    status: string;
  } | null;
}

interface TenantUser {
  user_id: string;
  email: string;
  role: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  student_profile?: { student_id: string } | null;
}

interface BreakGlassConversation {
  conversation_id: string;
  title: string | null;
  total_messages: number;
  updated_at: string;
}

interface BreakGlassMessage {
  message_id: string;
  sender_type: string;
  message_text: string;
  created_at: string;
}

type Tab = 'schools' | 'chat-access';

// ── Component ─────────────────────────────────────────────────────────

export function PlatformAdminDashboard() {
  const { user, logout } = useAuth();
  const [tab, setTab] = useState<Tab>('schools');

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-emerald-50">
      {/* Header */}
      <header className="bg-white border-b border-border px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Brain className="w-8 h-8 text-primary" />
            <div>
              <h1 className="font-semibold">MindBridge Platform Admin</h1>
              <p className="text-xs text-muted-foreground">{user?.email}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/admin/playground"
              className="flex items-center gap-2 px-4 py-2 border border-border rounded-xl text-sm hover:border-primary/50 transition"
            >
              <FlaskConical className="w-4 h-4 text-primary" /> AI Playground
            </Link>
            <button
              onClick={logout}
              className="flex items-center gap-2 px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition"
            >
              <LogOut className="w-4 h-4" /> Sign out
            </button>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="max-w-6xl mx-auto px-6 pt-6">
        <div className="flex gap-2 mb-6">
          {([
            { id: 'schools' as Tab, icon: Building2, label: 'Schools' },
            { id: 'chat-access' as Tab, icon: ShieldAlert, label: 'Chat Access (Break-Glass)' },
          ]).map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition ${
                tab === t.id ? 'bg-primary text-white' : 'bg-white border border-border text-muted-foreground hover:border-primary/50'
              }`}
            >
              <t.icon className="w-4 h-4" /> {t.label}
            </button>
          ))}
        </div>

        {tab === 'schools' ? <SchoolsTab /> : <ChatAccessTab />}
      </div>
    </div>
  );
}

// ── Schools Tab ───────────────────────────────────────────────────────

function SchoolsTab() {
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [selected, setSelected] = useState<TenantDetail | null>(null);
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const { data } = await api.get<{ tenants: TenantRow[] }>('/admin/tenants');
    setTenants(data.tenants);
  }, []);

  useEffect(() => {
    load().catch(() => setError('Failed to load schools'));
  }, [load]);

  const openDetail = async (tenantId: string) => {
    setError(null);
    try {
      const [detailRes, usersRes] = await Promise.all([
        api.get<TenantDetail>(`/admin/tenants/${tenantId}`),
        api.get<{ users: TenantUser[] }>(`/admin/tenants/${tenantId}/users`, {
          params: { page_size: 100 },
        }),
      ]);
      setSelected(detailRes.data);
      setUsers(usersRes.data.users);
    } catch {
      setError('Failed to load school details');
    }
  };

  if (selected) {
    return (
      <SchoolDetail
        tenant={selected}
        users={users}
        onBack={() => { setSelected(null); load(); }}
        onRefresh={() => openDetail(selected.tenant_id)}
      />
    );
  }

  return (
    <div>
      {error && <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">{error}</div>}

      <div className="flex justify-between items-center mb-4">
        <h2 className="font-semibold">Registered Schools ({tenants.length})</h2>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-xl text-sm font-medium hover:bg-primary/90 transition"
        >
          <Plus className="w-4 h-4" /> Register School
        </button>
      </div>

      <div className="bg-white rounded-2xl border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-muted-foreground">
            <tr>
              <th className="text-left px-4 py-3 font-medium">School</th>
              <th className="text-left px-4 py-3 font-medium">Code</th>
              <th className="text-left px-4 py-3 font-medium">Plan</th>
              <th className="text-left px-4 py-3 font-medium">Seats</th>
              <th className="text-left px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {tenants.map((t) => (
              <tr
                key={t.tenant_id}
                onClick={() => openDetail(t.tenant_id)}
                className="border-t border-border hover:bg-blue-50/50 cursor-pointer transition"
              >
                <td className="px-4 py-3 font-medium">{t.tenant_name}</td>
                <td className="px-4 py-3 font-mono text-xs">{t.school_code ?? '—'}</td>
                <td className="px-4 py-3 capitalize">{t.subscription_plan}</td>
                <td className="px-4 py-3">{t.student_limit}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    t.status === 'active' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                  }`}>{t.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <CreateSchoolModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); load(); }}
        />
      )}
    </div>
  );
}

function CreateSchoolModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [plan, setPlan] = useState('starter');
  const [seats, setSeats] = useState(100);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.post('/admin/tenants', {
        tenant_name: name,
        tenant_type: 'school',
        school_code: code || null,
        subscription_plan: plan,
        student_limit: seats,
      });
      onCreated();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Failed to register school');
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl p-6 w-full max-w-md">
        <div className="flex justify-between items-center mb-4">
          <h3 className="font-semibold">Register New School</h3>
          <button onClick={onClose}><X className="w-5 h-5 text-muted-foreground" /></button>
        </div>
        {error && <div className="mb-3 p-2 bg-red-50 text-red-700 text-sm rounded-lg">{error}</div>}
        <form onSubmit={submit} className="space-y-3">
          <div>
            <label className="text-sm font-medium block mb-1">School name</label>
            <input required value={name} onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-border rounded-xl text-sm bg-input-background" />
          </div>
          <div>
            <label className="text-sm font-medium block mb-1">School code (students use this to sign up)</label>
            <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="e.g. RHS2026"
              className="w-full px-3 py-2 border border-border rounded-xl text-sm bg-input-background font-mono" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium block mb-1">Plan</label>
              <select value={plan} onChange={(e) => setPlan(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-xl text-sm bg-input-background">
                <option value="free">Free</option>
                <option value="starter">Starter</option>
                <option value="professional">Professional</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium block mb-1">Student seats</label>
              <input type="number" min={1} value={seats} onChange={(e) => setSeats(parseInt(e.target.value) || 1)}
                className="w-full px-3 py-2 border border-border rounded-xl text-sm bg-input-background" />
            </div>
          </div>
          <button type="submit" disabled={saving}
            className="w-full py-2.5 bg-primary text-white rounded-xl text-sm font-medium disabled:opacity-50">
            {saving ? 'Registering…' : 'Register School'}
          </button>
        </form>
      </div>
    </div>
  );
}

function SchoolDetail({
  tenant, users, onBack, onRefresh,
}: {
  tenant: TenantDetail;
  users: TenantUser[];
  onBack: () => void;
  onRefresh: () => void;
}) {
  const [subSaving, setSubSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [subForm, setSubForm] = useState({
    plan_name: tenant.subscription?.plan_name ?? tenant.subscription_plan,
    student_limit: tenant.subscription?.student_limit ?? tenant.student_limit,
    billing_cycle: tenant.subscription?.billing_cycle ?? 'annual',
    amount: tenant.subscription?.amount ?? 0,
    start_date: tenant.subscription?.start_date ?? new Date().toISOString().slice(0, 10),
    renewal_date: tenant.subscription?.renewal_date ?? '',
  });

  const saveSubscription = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubSaving(true);
    setNotice(null);
    try {
      await api.post(`/admin/tenants/${tenant.tenant_id}/subscription`, {
        ...subForm,
        renewal_date: subForm.renewal_date || null,
      });
      setNotice('Subscription updated.');
      onRefresh();
    } catch {
      setNotice('Failed to update subscription.');
    } finally {
      setSubSaving(false);
    }
  };

  const seatPct = tenant.stats.seat_limit
    ? Math.min(100, Math.round((tenant.stats.seats_used / tenant.stats.seat_limit) * 100))
    : 0;

  return (
    <div>
      <button onClick={onBack} className="text-sm text-primary hover:underline mb-4">← All schools</button>

      <div className="flex items-center gap-3 mb-6">
        <Building2 className="w-7 h-7 text-primary" />
        <div>
          <h2 className="text-lg font-semibold">{tenant.tenant_name}</h2>
          <p className="text-sm text-muted-foreground font-mono">{tenant.school_code}</p>
        </div>
      </div>

      {notice && <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-xl text-blue-700 text-sm">{notice}</div>}

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Students', value: tenant.stats.students },
          { label: 'Parents', value: tenant.stats.parents },
          { label: 'Counselors', value: tenant.stats.counselors },
          { label: 'School Admins', value: tenant.stats.school_admins },
        ].map((s) => (
          <div key={s.label} className="bg-white rounded-2xl border border-border p-4">
            <p className="text-2xl font-semibold">{s.value}</p>
            <p className="text-sm text-muted-foreground">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Seat usage */}
      <div className="bg-white rounded-2xl border border-border p-4 mb-6">
        <div className="flex justify-between text-sm mb-2">
          <span className="font-medium">Seat usage</span>
          <span className="text-muted-foreground">{tenant.stats.seats_used} / {tenant.stats.seat_limit}</span>
        </div>
        <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${seatPct >= 90 ? 'bg-red-500' : 'bg-primary'}`}
            style={{ width: `${seatPct}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Subscription form */}
        <div className="bg-white rounded-2xl border border-border p-4">
          <h3 className="font-semibold mb-3">Subscription</h3>
          <form onSubmit={saveSubscription} className="space-y-3 text-sm">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="font-medium block mb-1">Plan</label>
                <select value={subForm.plan_name}
                  onChange={(e) => setSubForm({ ...subForm, plan_name: e.target.value })}
                  className="w-full px-3 py-2 border border-border rounded-xl bg-input-background">
                  <option value="free">Free</option>
                  <option value="starter">Starter</option>
                  <option value="professional">Professional</option>
                  <option value="enterprise">Enterprise</option>
                </select>
              </div>
              <div>
                <label className="font-medium block mb-1">Seats</label>
                <input type="number" min={1} value={subForm.student_limit}
                  onChange={(e) => setSubForm({ ...subForm, student_limit: parseInt(e.target.value) || 1 })}
                  className="w-full px-3 py-2 border border-border rounded-xl bg-input-background" />
              </div>
              <div>
                <label className="font-medium block mb-1">Billing</label>
                <select value={subForm.billing_cycle}
                  onChange={(e) => setSubForm({ ...subForm, billing_cycle: e.target.value })}
                  className="w-full px-3 py-2 border border-border rounded-xl bg-input-background">
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="annual">Annual</option>
                </select>
              </div>
              <div>
                <label className="font-medium block mb-1">Amount (USD)</label>
                <input type="number" min={0} step="0.01" value={subForm.amount}
                  onChange={(e) => setSubForm({ ...subForm, amount: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-border rounded-xl bg-input-background" />
              </div>
              <div>
                <label className="font-medium block mb-1">Start date</label>
                <input type="date" value={subForm.start_date}
                  onChange={(e) => setSubForm({ ...subForm, start_date: e.target.value })}
                  className="w-full px-3 py-2 border border-border rounded-xl bg-input-background" />
              </div>
              <div>
                <label className="font-medium block mb-1">Renewal date</label>
                <input type="date" value={subForm.renewal_date ?? ''}
                  onChange={(e) => setSubForm({ ...subForm, renewal_date: e.target.value })}
                  className="w-full px-3 py-2 border border-border rounded-xl bg-input-background" />
              </div>
            </div>
            <button type="submit" disabled={subSaving}
              className="w-full py-2.5 bg-primary text-white rounded-xl font-medium disabled:opacity-50">
              {subSaving ? 'Saving…' : 'Save subscription'}
            </button>
          </form>
        </div>

        {/* Users */}
        <div className="bg-white rounded-2xl border border-border p-4">
          <h3 className="font-semibold mb-3 flex items-center gap-2">
            <Users className="w-4 h-4" /> Users ({users.length})
          </h3>
          <div className="max-h-96 overflow-y-auto divide-y divide-border">
            {users.map((u) => (
              <div key={u.user_id} className="py-2 flex justify-between items-center text-sm">
                <div>
                  <p className="font-medium">{u.first_name} {u.last_name}</p>
                  <p className="text-xs text-muted-foreground">{u.email}</p>
                </div>
                <span className="px-2 py-0.5 bg-slate-100 rounded-full text-xs capitalize">{u.role.replace('_', ' ')}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Chat Access (Break-Glass) Tab ─────────────────────────────────────

function ChatAccessTab() {
  const [studentId, setStudentId] = useState('');
  const [reason, setReason] = useState('');
  const [studentName, setStudentName] = useState<string | null>(null);
  const [conversations, setConversations] = useState<BreakGlassConversation[]>([]);
  const [messages, setMessages] = useState<BreakGlassMessage[] | null>(null);
  const [activeConv, setActiveConv] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSearch = studentId.trim().length > 0 && reason.trim().length >= 10;

  const loadConversations = async () => {
    setLoading(true);
    setError(null);
    setMessages(null);
    setActiveConv(null);
    try {
      const { data } = await api.get(`/admin/students/${studentId.trim()}/conversations`, {
        params: { reason: reason.trim() },
      });
      setStudentName(data.student_name);
      setConversations(data.conversations);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Failed to load conversations');
      setStudentName(null);
      setConversations([]);
    } finally {
      setLoading(false);
    }
  };

  const loadMessages = async (conversationId: string) => {
    setActiveConv(conversationId);
    setMessages(null);
    try {
      const { data } = await api.get(`/admin/conversations/${conversationId}/messages`, {
        params: { reason: reason.trim() },
      });
      setMessages(data.messages);
    } catch {
      setError('Failed to load transcript');
    }
  };

  return (
    <div>
      {/* Warning banner */}
      <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-2xl flex gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div className="text-sm text-amber-800">
          <p className="font-semibold mb-1">Break-glass access — severe cases only</p>
          <p>
            Student conversations are private. Use this only for imminent-safety situations.
            Every access is permanently recorded in the audit log with your account and stated reason.
          </p>
        </div>
      </div>

      {/* Search form */}
      <div className="bg-white rounded-2xl border border-border p-4 mb-6 space-y-3">
        <div>
          <label className="text-sm font-medium block mb-1">Student ID</label>
          <input
            value={studentId}
            onChange={(e) => setStudentId(e.target.value)}
            placeholder="Student profile UUID (from the school's user list)"
            className="w-full px-3 py-2 border border-border rounded-xl text-sm bg-input-background font-mono"
          />
        </div>
        <div>
          <label className="text-sm font-medium block mb-1">
            Reason for access <span className="text-muted-foreground">(required, recorded in audit log)</span>
          </label>
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Crisis escalation from counselor Martinez, ticket #4821"
            minLength={10}
            className="w-full px-3 py-2 border border-border rounded-xl text-sm bg-input-background"
          />
        </div>
        <button
          onClick={loadConversations}
          disabled={!canSearch || loading}
          className="flex items-center gap-2 px-5 py-2.5 bg-amber-600 text-white rounded-xl text-sm font-medium disabled:opacity-50 hover:bg-amber-700 transition"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldAlert className="w-4 h-4" />}
          Access conversations
        </button>
      </div>

      {error && <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">{error}</div>}

      {studentName && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white rounded-2xl border border-border p-4">
            <h3 className="font-semibold mb-3">{studentName}'s conversations</h3>
            <div className="space-y-2">
              {conversations.map((c) => (
                <button
                  key={c.conversation_id}
                  onClick={() => loadMessages(c.conversation_id)}
                  className={`w-full text-left p-3 rounded-xl border text-sm transition ${
                    activeConv === c.conversation_id
                      ? 'border-primary bg-blue-50'
                      : 'border-border hover:border-primary/50'
                  }`}
                >
                  <p className="font-medium truncate">{c.title ?? 'Untitled'}</p>
                  <p className="text-xs text-muted-foreground">{c.total_messages} messages</p>
                </button>
              ))}
              {conversations.length === 0 && (
                <p className="text-sm text-muted-foreground">No conversations.</p>
              )}
            </div>
          </div>

          <div className="col-span-2 bg-white rounded-2xl border border-border p-4">
            <h3 className="font-semibold mb-3 flex items-center gap-2">
              <MessageSquare className="w-4 h-4" /> Transcript
            </h3>
            {messages === null ? (
              <p className="text-sm text-muted-foreground">Select a conversation.</p>
            ) : (
              <div className="space-y-3 max-h-[32rem] overflow-y-auto">
                {messages.map((m) => (
                  <div
                    key={m.message_id}
                    className={`p-3 rounded-xl text-sm max-w-[85%] ${
                      m.sender_type === 'user'
                        ? 'bg-blue-50 ml-auto'
                        : 'bg-slate-50'
                    }`}
                  >
                    <p className="text-xs font-medium text-muted-foreground mb-1">
                      {m.sender_type === 'user' ? 'Student' : 'Comrade AI'} ·{' '}
                      {new Date(m.created_at).toLocaleString()}
                    </p>
                    <p className="whitespace-pre-wrap">{m.message_text}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
