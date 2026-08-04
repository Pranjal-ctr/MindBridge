import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Loader2, Plus, School } from 'lucide-react';
import { apiErrorDetail, createSchool, listSchools } from '../../../../lib/admin-api';
import type { TenantRow } from '../../../../lib/admin-types';
import { Button } from '../../ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../ui/select';
import { Switch } from '../../ui/switch';
import { DataTable, type DataTableColumn } from '../widgets/DataTable';
import { PageHeader } from '../widgets/PageHeader';
import { StatusBadge } from '../widgets/StatusBadge';

const PAGE_SIZE = 20;
const PLANS = ['free', 'starter', 'professional', 'enterprise'];

export function SchoolsPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<TenantRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>('all');
  const [includeArchived, setIncludeArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listSchools(page, PAGE_SIZE, {
        search: search || undefined,
        status: status === 'all' ? undefined : status,
        include_archived: includeArchived,
      });
      setRows(data.tenants);
      setTotal(data.total);
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Failed to load schools'));
    } finally {
      setLoading(false);
    }
  }, [page, search, status, includeArchived]);

  useEffect(() => {
    load();
  }, [load]);

  const columns: DataTableColumn<TenantRow>[] = [
    {
      key: 'tenant_name',
      header: 'School',
      render: (t) => (
        <div className="flex items-center gap-2.5">
          {t.logo_url ? (
            <img src={t.logo_url} alt="" className="h-7 w-7 rounded-md object-cover" />
          ) : (
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-xs font-semibold text-primary">
              {t.tenant_name.slice(0, 2).toUpperCase()}
            </div>
          )}
          <div>
            <p className="font-medium">{t.tenant_name}</p>
            <p className="font-mono text-xs text-muted-foreground">{t.school_code ?? '—'}</p>
          </div>
        </div>
      ),
    },
    { key: 'city', header: 'City', render: (t) => t.city ?? '—' },
    {
      key: 'subscription_plan',
      header: 'Plan',
      render: (t) => <span className="capitalize">{t.subscription_plan}</span>,
    },
    {
      key: 'students',
      header: 'Students',
      render: (t) => (
        <span className="tabular-nums">
          {t.active_students} / {t.student_limit}
        </span>
      ),
    },
    { key: 'status', header: 'Status', render: (t) => <StatusBadge status={t.status} /> },
    {
      key: 'created_at',
      header: 'Created',
      render: (t) => new Date(t.created_at).toLocaleDateString(),
    },
  ];

  return (
    <>
      <PageHeader
        title="Schools"
        description="Onboard and manage every school from one place"
        actions={
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4" /> Add School
          </Button>
        }
      />
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(t) => t.tenant_id}
        total={total}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        searchValue={search}
        onSearchChange={(v) => {
          setSearch(v);
          setPage(1);
        }}
        searchPlaceholder="Search by name or code…"
        filters={
          <>
            <Select
              value={status}
              onValueChange={(v) => {
                setStatus(v);
                setPage(1);
              }}
            >
              <SelectTrigger className="w-36">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="trial">Trial</SelectItem>
                <SelectItem value="suspended">Suspended</SelectItem>
                <SelectItem value="inactive">Inactive</SelectItem>
                <SelectItem value="archived">Archived</SelectItem>
              </SelectContent>
            </Select>
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <Switch
                checked={includeArchived}
                onCheckedChange={(v) => {
                  setIncludeArchived(v);
                  setPage(1);
                }}
              />
              Show archived
            </label>
          </>
        }
        loading={loading}
        empty={{
          icon: School,
          title: 'No schools found',
          description: search
            ? 'Try a different search or clear the filters.'
            : 'Register your first school to get started.',
          action: !search ? (
            <Button size="sm" onClick={() => setShowCreate(true)}>
              <Plus className="h-4 w-4" /> Add School
            </Button>
          ) : undefined,
        }}
        onRowClick={(t) => navigate(`/admin/schools/${t.tenant_id}`)}
      />
      <CreateSchoolDialog
        open={showCreate}
        onOpenChange={setShowCreate}
        onCreated={() => {
          setShowCreate(false);
          load();
        }}
      />
    </>
  );
}

function CreateSchoolDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    tenant_name: '',
    school_code: '',
    subscription_plan: 'starter',
    student_limit: 100,
    city: '',
    contact_email: '',
    principal_name: '',
  });
  const [saving, setSaving] = useState(false);

  const set = (key: string, value: string | number) => setForm((f) => ({ ...f, [key]: value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await createSchool({
        tenant_name: form.tenant_name,
        tenant_type: 'school',
        school_code: form.school_code || null,
        subscription_plan: form.subscription_plan,
        student_limit: form.student_limit,
        city: form.city || null,
        contact_email: form.contact_email || null,
        principal_name: form.principal_name || null,
      });
      toast.success(`${form.tenant_name} registered`);
      onCreated();
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Failed to register school'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Register New School</DialogTitle>
          <DialogDescription>
            Students sign up with the school code you set here.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid gap-1.5">
            <Label htmlFor="school-name">School name</Label>
            <Input
              id="school-name"
              required
              value={form.tenant_name}
              onChange={(e) => set('tenant_name', e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="school-code">School code</Label>
              <Input
                id="school-code"
                placeholder="e.g. RHS2026"
                className="font-mono"
                value={form.school_code}
                onChange={(e) => set('school_code', e.target.value.toUpperCase())}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="school-city">City</Label>
              <Input
                id="school-city"
                value={form.city}
                onChange={(e) => set('city', e.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label>Plan</Label>
              <Select
                value={form.subscription_plan}
                onValueChange={(v) => set('subscription_plan', v)}
              >
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
              <Label htmlFor="school-seats">Student seats</Label>
              <Input
                id="school-seats"
                type="number"
                min={1}
                value={form.student_limit}
                onChange={(e) => set('student_limit', parseInt(e.target.value) || 1)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="school-email">Contact email</Label>
              <Input
                id="school-email"
                type="email"
                value={form.contact_email}
                onChange={(e) => set('contact_email', e.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="school-principal">Principal</Label>
              <Input
                id="school-principal"
                value={form.principal_name}
                onChange={(e) => set('principal_name', e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="submit" disabled={saving || !form.tenant_name.trim()}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Register School
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
