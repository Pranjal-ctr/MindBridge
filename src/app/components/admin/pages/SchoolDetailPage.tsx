import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Archive,
  ArrowLeft,
  Ban,
  CheckCircle2,
  CreditCard,
  Flag,
  KeyRound,
  Loader2,
  Pencil,
  UserPlus,
  Users,
} from 'lucide-react';
import {
  apiErrorDetail,
  archiveSchool,
  createStaffUser,
  getSchoolDetail,
  listSchoolUsers,
  setSchoolSubscription,
  updateSchool,
  updateUserAdmin,
} from '../../../../lib/admin-api';
import type {
  TenantDetail,
  TenantUserRow,
} from '../../../../lib/admin-types';
import { Button } from '../../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../../ui/dropdown-menu';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../ui/select';
import { Skeleton } from '../../ui/skeleton';
import { Textarea } from '../../ui/textarea';
import { Tooltip, TooltipContent, TooltipTrigger } from '../../ui/tooltip';
import { ConfirmActionDialog } from '../widgets/ConfirmActionDialog';
import { DataTable, type DataTableColumn } from '../widgets/DataTable';
import { StatCard } from '../widgets/StatCard';
import { StatusBadge } from '../widgets/StatusBadge';

const PLANS = ['free', 'starter', 'professional', 'enterprise'];
const USERS_PAGE_SIZE = 10;

export function SchoolDetailPage() {
  const { tenantId } = useParams<{ tenantId: string }>();
  const navigate = useNavigate();
  const [tenant, setTenant] = useState<TenantDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [showEdit, setShowEdit] = useState(false);
  const [showAssignAdmin, setShowAssignAdmin] = useState(false);

  const load = useCallback(async () => {
    if (!tenantId) return;
    try {
      setTenant(await getSchoolDetail(tenantId));
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Failed to load school'));
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading || !tenant) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-64" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  const archived = tenant.deleted_at !== null;
  const suspended = tenant.status === 'suspended';
  const seatPct = tenant.stats.seat_limit
    ? Math.min(100, Math.round((tenant.stats.seats_used / tenant.stats.seat_limit) * 100))
    : 0;

  const setStatus = async (status: 'active' | 'suspended') => {
    try {
      await updateSchool(tenant.tenant_id, { status });
      toast.success(status === 'suspended' ? 'School suspended' : 'School activated');
      load();
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Failed to update school'));
      throw err;
    }
  };

  return (
    <>
      {/* Header */}
      <div className="space-y-4">
        <Link
          to="/admin/schools"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> All schools
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            {tenant.logo_url ? (
              <img src={tenant.logo_url} alt="" className="h-12 w-12 rounded-lg object-cover" />
            ) : (
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-lg font-semibold text-primary">
                {tenant.tenant_name.slice(0, 2).toUpperCase()}
              </div>
            )}
            <div>
              <div className="flex items-center gap-2">
                <h1
                  className="text-xl font-semibold tracking-tight"
                  style={{ fontFamily: 'var(--font-heading)' }}
                >
                  {tenant.tenant_name}
                </h1>
                <StatusBadge status={tenant.status} />
              </div>
              <p className="font-mono text-sm text-muted-foreground">
                {tenant.school_code ?? 'No school code'}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowEdit(true)}>
              <Pencil className="h-4 w-4" /> Edit
            </Button>
            {!archived && (suspended ? (
              <ConfirmActionDialog
                trigger={
                  <Button variant="outline" size="sm">
                    <CheckCircle2 className="h-4 w-4" /> Activate
                  </Button>
                }
                title={`Activate ${tenant.tenant_name}?`}
                description="Users of this school will be able to sign in again."
                confirmLabel="Activate"
                onConfirm={() => setStatus('active')}
              />
            ) : (
              <ConfirmActionDialog
                trigger={
                  <Button variant="outline" size="sm">
                    <Ban className="h-4 w-4" /> Suspend
                  </Button>
                }
                title={`Suspend ${tenant.tenant_name}?`}
                description="All students, parents, and staff of this school will be blocked from signing in until it is reactivated."
                confirmLabel="Suspend"
                destructive
                onConfirm={() => setStatus('suspended')}
              />
            ))}
            <Button variant="outline" size="sm" onClick={() => setShowAssignAdmin(true)}>
              <UserPlus className="h-4 w-4" /> Assign Admin
            </Button>
            {!archived && (
              <ConfirmActionDialog
                trigger={
                  <Button variant="outline" size="sm" className="text-destructive">
                    <Archive className="h-4 w-4" /> Archive
                  </Button>
                }
                title={`Archive ${tenant.tenant_name}?`}
                description="The school is hidden from listings and all its users are locked out. Data is kept and the school can be restored later by reactivating it. This is a soft delete — nothing is permanently removed."
                confirmLabel="Archive school"
                destructive
                onConfirm={async () => {
                  try {
                    await archiveSchool(tenant.tenant_id);
                    toast.success(`${tenant.tenant_name} archived`);
                    navigate('/admin/schools');
                  } catch (err) {
                    toast.error(apiErrorDetail(err, 'Failed to archive school'));
                    throw err;
                  }
                }}
              />
            )}
            {/* Future modules — intentionally disabled placeholders */}
            <Tooltip>
              <TooltipTrigger asChild>
                <span>
                  <Button variant="outline" size="sm" disabled>
                    <CreditCard className="h-4 w-4" /> Billing
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>Coming soon</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <span>
                  <Button variant="outline" size="sm" disabled>
                    <Flag className="h-4 w-4" /> Feature Flags
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>Coming soon</TooltipContent>
            </Tooltip>
          </div>
        </div>

        {/* Stats */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Students" value={tenant.stats.students} />
          <StatCard label="Parents" value={tenant.stats.parents} />
          <StatCard label="Counselors" value={tenant.stats.counselors} />
          <StatCard label="School Admins" value={tenant.stats.school_admins} />
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          {/* Profile */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">School profile</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                <ProfileField label="City" value={tenant.city} />
                <ProfileField label="Principal" value={tenant.principal_name} />
                <ProfileField label="Contact email" value={tenant.contact_email} />
                <ProfileField label="Contact phone" value={tenant.contact_phone} />
                <div className="col-span-2">
                  <ProfileField label="Address" value={tenant.address} />
                </div>
              </dl>
              <div className="mt-4 border-t pt-4">
                <div className="mb-2 flex justify-between text-sm">
                  <span className="font-medium">Seat usage</span>
                  <span className="text-muted-foreground tabular-nums">
                    {tenant.stats.seats_used} / {tenant.stats.seat_limit}
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div
                    className={`h-full rounded-full ${seatPct >= 90 ? 'bg-destructive' : 'bg-primary'}`}
                    style={{ width: `${seatPct}%` }}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Subscription */}
          <SubscriptionCard tenant={tenant} onSaved={load} />
        </div>

        {/* Users */}
        <SchoolUsersCard tenantId={tenant.tenant_id} />
      </div>

      <EditSchoolDialog
        tenant={tenant}
        open={showEdit}
        onOpenChange={setShowEdit}
        onSaved={() => {
          setShowEdit(false);
          load();
        }}
      />
      <AssignAdminDialog
        tenantId={tenant.tenant_id}
        open={showAssignAdmin}
        onOpenChange={setShowAssignAdmin}
        onCreated={() => {
          setShowAssignAdmin(false);
          load();
        }}
      />
    </>
  );
}

function ProfileField({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-medium">{value || '—'}</dd>
    </div>
  );
}

// ── Subscription ──────────────────────────────────────────────────────

function SubscriptionCard({ tenant, onSaved }: { tenant: TenantDetail; onSaved: () => void }) {
  const [form, setForm] = useState({
    plan_name: tenant.subscription?.plan_name ?? tenant.subscription_plan,
    student_limit: tenant.subscription?.student_limit ?? tenant.student_limit,
    billing_cycle: tenant.subscription?.billing_cycle ?? 'annual',
    amount: tenant.subscription?.amount ?? 0,
    start_date: tenant.subscription?.start_date ?? new Date().toISOString().slice(0, 10),
    renewal_date: tenant.subscription?.renewal_date ?? '',
  });
  const [saving, setSaving] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await setSchoolSubscription(tenant.tenant_id, {
        ...form,
        renewal_date: form.renewal_date || null,
      });
      toast.success('Subscription updated');
      onSaved();
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Failed to update subscription'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Subscription</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid grid-cols-2 gap-3 text-sm">
          <div className="grid gap-1.5">
            <Label>Plan</Label>
            <Select value={form.plan_name} onValueChange={(v) => setForm({ ...form, plan_name: v })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PLANS.map((p) => (
                  <SelectItem key={p} value={p} className="capitalize">
                    {p}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label>Seats</Label>
            <Input
              type="number"
              min={1}
              value={form.student_limit}
              onChange={(e) => setForm({ ...form, student_limit: parseInt(e.target.value) || 1 })}
            />
          </div>
          <div className="grid gap-1.5">
            <Label>Billing</Label>
            <Select
              value={form.billing_cycle}
              onValueChange={(v) => setForm({ ...form, billing_cycle: v })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="monthly">Monthly</SelectItem>
                <SelectItem value="quarterly">Quarterly</SelectItem>
                <SelectItem value="annual">Annual</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label>Amount (USD)</Label>
            <Input
              type="number"
              min={0}
              step="0.01"
              value={form.amount}
              onChange={(e) => setForm({ ...form, amount: parseFloat(e.target.value) || 0 })}
            />
          </div>
          <div className="grid gap-1.5">
            <Label>Start date</Label>
            <Input
              type="date"
              value={form.start_date}
              onChange={(e) => setForm({ ...form, start_date: e.target.value })}
            />
          </div>
          <div className="grid gap-1.5">
            <Label>Renewal date</Label>
            <Input
              type="date"
              value={form.renewal_date ?? ''}
              onChange={(e) => setForm({ ...form, renewal_date: e.target.value })}
            />
          </div>
          <div className="col-span-2">
            <Button type="submit" disabled={saving} className="w-full">
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Save subscription
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

// ── Users card ────────────────────────────────────────────────────────

function SchoolUsersCard({ tenantId }: { tenantId: string }) {
  const [rows, setRows] = useState<TenantUserRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [role, setRole] = useState('all');
  const [loading, setLoading] = useState(true);
  const [resetUser, setResetUser] = useState<TenantUserRow | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listSchoolUsers(
        tenantId, page, USERS_PAGE_SIZE, role === 'all' ? undefined : role,
      );
      setRows(data.users);
      setTotal(data.total);
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Failed to load users'));
    } finally {
      setLoading(false);
    }
  }, [tenantId, page, role]);

  useEffect(() => {
    load();
  }, [load]);

  const toggleActive = async (u: TenantUserRow) => {
    try {
      await updateUserAdmin(u.user_id, { is_active: !u.is_active });
      toast.success(u.is_active ? `${u.first_name} suspended` : `${u.first_name} activated`);
      load();
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Failed to update user'));
    }
  };

  const columns: DataTableColumn<TenantUserRow>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (u) => (
        <div>
          <p className="font-medium">{u.first_name} {u.last_name}</p>
          <p className="text-xs text-muted-foreground">{u.email}</p>
        </div>
      ),
    },
    {
      key: 'role',
      header: 'Role',
      render: (u) => <span className="capitalize">{u.role.replace('_', ' ')}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (u) => <StatusBadge status={u.is_active ? 'active' : 'inactive'} />,
    },
    {
      key: 'actions',
      header: '',
      className: 'w-12 text-right',
      render: (u) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" onClick={(e) => e.stopPropagation()}>
              ⋯
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
            <DropdownMenuItem onClick={() => setResetUser(u)}>
              <KeyRound className="h-4 w-4" /> Reset password
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => toggleActive(u)}>
              {u.is_active ? (
                <><Ban className="h-4 w-4" /> Suspend</>
              ) : (
                <><CheckCircle2 className="h-4 w-4" /> Activate</>
              )}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Users className="h-4 w-4" /> Users
        </CardTitle>
      </CardHeader>
      <CardContent>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(u) => u.user_id}
          total={total}
          page={page}
          pageSize={USERS_PAGE_SIZE}
          onPageChange={setPage}
          filters={
            <Select
              value={role}
              onValueChange={(v) => {
                setRole(v);
                setPage(1);
              }}
            >
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Role" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All roles</SelectItem>
                <SelectItem value="student">Students</SelectItem>
                <SelectItem value="parent">Parents</SelectItem>
                <SelectItem value="counselor">Counselors</SelectItem>
                <SelectItem value="school_admin">School Admins</SelectItem>
              </SelectContent>
            </Select>
          }
          loading={loading}
          empty={{ icon: Users, title: 'No users in this school yet' }}
        />
        {resetUser && (
          <ResetPasswordDialog
            user={resetUser}
            open
            onOpenChange={(open) => !open && setResetUser(null)}
          />
        )}
      </CardContent>
    </Card>
  );
}

export function ResetPasswordDialog({
  user,
  open,
  onOpenChange,
}: {
  user: { user_id: string; first_name: string; last_name: string; email: string };
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [password, setPassword] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await updateUserAdmin(user.user_id, { new_password: password });
      toast.success(`Password reset for ${user.first_name} ${user.last_name}`);
      onOpenChange(false);
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Failed to reset password'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Reset password</DialogTitle>
          <DialogDescription>
            Set a new password for {user.first_name} {user.last_name} ({user.email}).
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid gap-1.5">
            <Label htmlFor="new-password">New password</Label>
            <Input
              id="new-password"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">Minimum 8 characters.</p>
          </div>
          <DialogFooter>
            <Button type="submit" disabled={saving || password.length < 8}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Reset password
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Edit school ───────────────────────────────────────────────────────

function EditSchoolDialog({
  tenant,
  open,
  onOpenChange,
  onSaved,
}: {
  tenant: TenantDetail;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
    tenant_name: tenant.tenant_name,
    city: tenant.city ?? '',
    address: tenant.address ?? '',
    contact_email: tenant.contact_email ?? '',
    contact_phone: tenant.contact_phone ?? '',
    principal_name: tenant.principal_name ?? '',
    logo_url: tenant.logo_url ?? '',
  });
  const [saving, setSaving] = useState(false);

  const set = (key: string, value: string) => setForm((f) => ({ ...f, [key]: value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await updateSchool(tenant.tenant_id, {
        tenant_name: form.tenant_name,
        city: form.city || null,
        address: form.address || null,
        contact_email: form.contact_email || null,
        contact_phone: form.contact_phone || null,
        principal_name: form.principal_name || null,
        logo_url: form.logo_url || null,
      });
      toast.success('School updated');
      onSaved();
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Failed to update school'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit school</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid gap-1.5">
            <Label>School name</Label>
            <Input
              required
              value={form.tenant_name}
              onChange={(e) => set('tenant_name', e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label>City</Label>
              <Input value={form.city} onChange={(e) => set('city', e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label>Principal</Label>
              <Input
                value={form.principal_name}
                onChange={(e) => set('principal_name', e.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label>Contact email</Label>
              <Input
                type="email"
                value={form.contact_email}
                onChange={(e) => set('contact_email', e.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label>Contact phone</Label>
              <Input
                value={form.contact_phone}
                onChange={(e) => set('contact_phone', e.target.value)}
              />
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label>Address</Label>
            <Textarea
              rows={2}
              value={form.address}
              onChange={(e) => set('address', e.target.value)}
            />
          </div>
          <div className="grid gap-1.5">
            <Label>Logo URL</Label>
            <Input
              type="url"
              placeholder="https://…"
              value={form.logo_url}
              onChange={(e) => set('logo_url', e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Save changes
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Assign school admin ───────────────────────────────────────────────

function AssignAdminDialog({
  tenantId,
  open,
  onOpenChange,
  onCreated,
}: {
  tenantId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
  });
  const [saving, setSaving] = useState(false);

  const set = (key: string, value: string) => setForm((f) => ({ ...f, [key]: value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await createStaffUser({
        tenant_id: tenantId,
        role: 'school_admin',
        ...form,
      });
      toast.success(`School admin account created for ${form.email}`);
      onCreated();
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Failed to create school admin'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Assign school admin</DialogTitle>
          <DialogDescription>
            Creates a school_admin account for this school. Share the credentials securely.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label>First name</Label>
              <Input
                required
                value={form.first_name}
                onChange={(e) => set('first_name', e.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label>Last name</Label>
              <Input
                required
                value={form.last_name}
                onChange={(e) => set('last_name', e.target.value)}
              />
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label>Email</Label>
            <Input
              type="email"
              required
              value={form.email}
              onChange={(e) => set('email', e.target.value)}
            />
          </div>
          <div className="grid gap-1.5">
            <Label>Temporary password</Label>
            <Input
              type="password"
              required
              minLength={8}
              value={form.password}
              onChange={(e) => set('password', e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Create account
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
