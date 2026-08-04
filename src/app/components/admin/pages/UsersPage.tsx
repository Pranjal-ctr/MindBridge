import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import {
  Ban,
  CheckCircle2,
  KeyRound,
  Loader2,
  MoreHorizontal,
  Pencil,
  Trash2,
  Users,
} from 'lucide-react';
import {
  apiErrorDetail,
  deleteUserAdmin,
  listSchools,
  listUsers,
  updateUserAdmin,
} from '../../../../lib/admin-api';
import type { AdminUserRow, TenantRow } from '../../../../lib/admin-types';
import { Button } from '../../ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
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
import { Tabs, TabsList, TabsTrigger } from '../../ui/tabs';
import { ConfirmActionDialog } from '../widgets/ConfirmActionDialog';
import { DataTable, type DataTableColumn } from '../widgets/DataTable';
import { PageHeader } from '../widgets/PageHeader';
import { StatusBadge } from '../widgets/StatusBadge';
import { ResetPasswordDialog } from './SchoolDetailPage';

const PAGE_SIZE = 20;

const ROLE_TABS = [
  { value: 'all', label: 'All' },
  { value: 'student', label: 'Students' },
  { value: 'parent', label: 'Parents' },
  { value: 'school_admin', label: 'School Admins' },
  { value: 'counselor', label: 'Counselors' },
  { value: 'admin', label: 'Platform Admins' },
];

function userStatus(u: AdminUserRow): string {
  if (u.deleted_at) return 'deleted';
  return u.is_active ? 'active' : 'suspended';
}

export function UsersPage() {
  const [rows, setRows] = useState<AdminUserRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [role, setRole] = useState('all');
  const [search, setSearch] = useState('');
  const [tenantFilter, setTenantFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [schools, setSchools] = useState<TenantRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [resetUser, setResetUser] = useState<AdminUserRow | null>(null);
  const [editUser, setEditUser] = useState<AdminUserRow | null>(null);
  const [deleteUser, setDeleteUser] = useState<AdminUserRow | null>(null);

  useEffect(() => {
    // School filter options (first 100 schools is plenty for pilots)
    listSchools(1, 100)
      .then((data) => setSchools(data.tenants))
      .catch(() => undefined);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listUsers(page, PAGE_SIZE, {
        role: role === 'all' ? undefined : role,
        search: search || undefined,
        tenant_id: tenantFilter === 'all' ? undefined : tenantFilter,
        status:
          statusFilter === 'all'
            ? undefined
            : (statusFilter as 'active' | 'inactive' | 'deleted'),
      });
      setRows(data.users);
      setTotal(data.total);
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Failed to load users'));
    } finally {
      setLoading(false);
    }
  }, [page, role, search, tenantFilter, statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const toggleActive = async (u: AdminUserRow) => {
    try {
      await updateUserAdmin(u.user_id, { is_active: !u.is_active });
      toast.success(
        u.is_active
          ? `${u.first_name} ${u.last_name} suspended`
          : `${u.first_name} ${u.last_name} activated`,
      );
      load();
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Failed to update user'));
    }
  };

  const columns: DataTableColumn<AdminUserRow>[] = [
    {
      key: 'name',
      header: 'User',
      render: (u) => (
        <div className="flex items-center gap-2.5">
          {u.profile_image ? (
            <img src={u.profile_image} alt="" className="h-7 w-7 rounded-full object-cover" />
          ) : (
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-muted text-xs font-medium">
              {u.first_name[0]}
              {u.last_name[0] ?? ''}
            </div>
          )}
          <div>
            <p className="font-medium">
              {u.first_name} {u.last_name}
            </p>
            <p className="text-xs text-muted-foreground">{u.email}</p>
          </div>
        </div>
      ),
    },
    {
      key: 'role',
      header: 'Role',
      render: (u) => <span className="capitalize">{u.role.replace('_', ' ')}</span>,
    },
    { key: 'tenant_name', header: 'School', render: (u) => u.tenant_name ?? '—' },
    { key: 'status', header: 'Status', render: (u) => <StatusBadge status={userStatus(u)} /> },
    {
      key: 'last_login',
      header: 'Last login',
      render: (u) => (u.last_login ? new Date(u.last_login).toLocaleDateString() : 'Never'),
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (u) => new Date(u.created_at).toLocaleDateString(),
    },
    {
      key: 'actions',
      header: '',
      className: 'w-12 text-right',
      render: (u) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => setEditUser(u)}>
              <Pencil className="h-4 w-4" /> Edit
            </DropdownMenuItem>
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
            {!u.deleted_at && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="destructive" onClick={() => setDeleteUser(u)}>
                  <Trash2 className="h-4 w-4" /> Delete
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];

  return (
    <>
      <PageHeader title="Users" description="Manage every user across the platform" />
      <Tabs
        value={role}
        onValueChange={(v) => {
          setRole(v);
          setPage(1);
        }}
      >
        <TabsList>
          {ROLE_TABS.map((t) => (
            <TabsTrigger key={t.value} value={t.value}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(u) => u.user_id}
        total={total}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        searchValue={search}
        onSearchChange={(v) => {
          setSearch(v);
          setPage(1);
        }}
        searchPlaceholder="Search by name or email…"
        filters={
          <>
            <Select
              value={tenantFilter}
              onValueChange={(v) => {
                setTenantFilter(v);
                setPage(1);
              }}
            >
              <SelectTrigger className="w-44">
                <SelectValue placeholder="School" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All schools</SelectItem>
                {schools.map((s) => (
                  <SelectItem key={s.tenant_id} value={s.tenant_id}>
                    {s.tenant_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={statusFilter}
              onValueChange={(v) => {
                setStatusFilter(v);
                setPage(1);
              }}
            >
              <SelectTrigger className="w-36">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="inactive">Suspended</SelectItem>
                <SelectItem value="deleted">Deleted</SelectItem>
              </SelectContent>
            </Select>
          </>
        }
        loading={loading}
        empty={{
          icon: Users,
          title: 'No users found',
          description: 'Try a different search or clear the filters.',
        }}
      />

      {resetUser && (
        <ResetPasswordDialog
          user={resetUser}
          open
          onOpenChange={(open) => !open && setResetUser(null)}
        />
      )}
      {editUser && (
        <EditUserDialog
          user={editUser}
          open
          onOpenChange={(open) => !open && setEditUser(null)}
          onSaved={() => {
            setEditUser(null);
            load();
          }}
        />
      )}
      {deleteUser && (
        <ConfirmActionDialog
          open
          onOpenChange={(open) => !open && setDeleteUser(null)}
          title={`Delete ${deleteUser.first_name} ${deleteUser.last_name}?`}
          description="This is a soft delete: the account is blocked immediately but the record is kept for audit trails. You can find deleted users with the status filter."
          confirmLabel="Delete user"
          destructive
          onConfirm={async () => {
            try {
              await deleteUserAdmin(deleteUser.user_id);
              toast.success(`${deleteUser.first_name} ${deleteUser.last_name} deleted`);
              setDeleteUser(null);
              load();
            } catch (err) {
              toast.error(apiErrorDetail(err, 'Failed to delete user'));
              throw err;
            }
          }}
        />
      )}
    </>
  );
}

function EditUserDialog({
  user,
  open,
  onOpenChange,
  onSaved,
}: {
  user: AdminUserRow;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
    first_name: user.first_name,
    last_name: user.last_name,
    phone: user.phone ?? '',
  });
  const [saving, setSaving] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await updateUserAdmin(user.user_id, {
        first_name: form.first_name,
        last_name: form.last_name,
        phone: form.phone || undefined,
      });
      toast.success('User updated');
      onSaved();
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Failed to update user'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Edit user</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label>First name</Label>
              <Input
                required
                value={form.first_name}
                onChange={(e) => setForm({ ...form, first_name: e.target.value })}
              />
            </div>
            <div className="grid gap-1.5">
              <Label>Last name</Label>
              <Input
                required
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              />
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label>Phone</Label>
            <Input
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Email changes are not supported yet.
          </p>
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
