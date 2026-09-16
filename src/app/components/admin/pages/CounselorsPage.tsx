/**
 * Counselors — the platform counselor roster.
 *
 * Counselors belong to the Kio platform, not to a school (migration 008), so
 * this is the only place they are managed. The consequential control here is
 * `is_verified`: an unverified counselor stays out of the public booking
 * directory, so verification is what actually lets a stranger be booked by a
 * student. It is gated behind a confirm dialog for that reason.
 */

import { useCallback, useEffect, useState } from 'react';
import { HeartHandshake, Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  apiErrorDetail,
  createCounselor,
  listCounselors,
  listSchools,
  updateCounselor,
} from '../../../../lib/admin-api';
import type { CounselorAdmin, TenantRow } from '../../../../lib/admin-types';
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
import { ConfirmActionDialog } from '../widgets/ConfirmActionDialog';
import { DataTable, type DataTableColumn } from '../widgets/DataTable';
import { PageHeader } from '../widgets/PageHeader';
import { StatusBadge } from '../widgets/StatusBadge';

interface NewCounselorForm {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  phone: string;
  qualification: string;
  experience_years: string;
  /** Schools this counselor will serve. Empty means they get no alerts. */
  tenant_ids: string[];
}

const EMPTY_FORM: NewCounselorForm = {
  first_name: '',
  last_name: '',
  email: '',
  password: '',
  phone: '',
  qualification: '',
  experience_years: '',
  tenant_ids: [],
};

export function CounselorsPage() {
  const navigate = useNavigate();

  const [counselors, setCounselors] = useState<CounselorAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState<NewCounselorForm>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const [verifyTarget, setVerifyTarget] = useState<CounselorAdmin | null>(null);

  // Schools to choose from when registering. Loaded once with the roster; the
  // list is small (one row per school on the platform).
  const [schools, setSchools] = useState<TenantRow[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listCounselors();
      setCounselors(data.counselors);
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Could not load counselors.'));
    } finally {
      setLoading(false);
    }
  }, []);

  // Schools for the assignment picker. Failing to load them must not block
  // registration, so this only disables the picker and says why.
  const [schoolsError, setSchoolsError] = useState(false);
  const loadSchools = useCallback(async () => {
    try {
      const data = await listSchools(1, 100);
      setSchools(data.tenants);
      setSchoolsError(false);
    } catch {
      setSchoolsError(true);
    }
  }, []);

  useEffect(() => {
    loadSchools();
  }, [loadSchools]);

  useEffect(() => {
    load();
  }, [load]);

  // The endpoint returns the full roster (it is small and platform-wide), so
  // filtering stays client-side rather than inventing a server param.
  const term = search.trim().toLowerCase();
  const rows = term
    ? counselors.filter(
        (c) =>
          c.name.toLowerCase().includes(term) ||
          c.email.toLowerCase().includes(term) ||
          (c.qualification ?? '').toLowerCase().includes(term),
      )
    : counselors;

  const handleCreate = async () => {
    setSaving(true);
    try {
      await createCounselor({
        email: form.email.trim(),
        password: form.password,
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        ...(form.phone ? { phone: form.phone.trim() } : {}),
        ...(form.qualification ? { qualification: form.qualification.trim() } : {}),
        ...(form.experience_years
          ? { experience_years: Number(form.experience_years) }
          : {}),
        tenant_ids: form.tenant_ids,
      });
      toast.success(
        form.tenant_ids.length
          ? 'Counselor registered. They still need verifying before they appear in the directory.'
          : 'Counselor registered with no school — they will receive no risk alerts until you assign one.',
      );
      setAddOpen(false);
      setForm(EMPTY_FORM);
      load();
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Could not register counselor.'));
    } finally {
      setSaving(false);
    }
  };

  const handleToggleVerified = async (counselor: CounselorAdmin) => {
    try {
      await updateCounselor(counselor.counselor_id, {
        is_verified: !counselor.is_verified,
      });
      toast.success(
        counselor.is_verified
          ? 'Verification withdrawn — removed from the booking directory.'
          : 'Counselor verified and listed in the booking directory.',
      );
      load();
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Could not update counselor.'));
    } finally {
      setVerifyTarget(null);
    }
  };

  const columns: DataTableColumn<CounselorAdmin>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (row) => (
        <div className="min-w-0">
          <div className="truncate font-medium">{row.name}</div>
          <div className="truncate text-xs text-muted-foreground">{row.email}</div>
        </div>
      ),
    },
    {
      key: 'qualification',
      header: 'Qualification',
      render: (row) => row.qualification || <span className="text-muted-foreground">—</span>,
    },
    {
      key: 'experience_years',
      header: 'Experience',
      render: (row) =>
        row.experience_years === null ? (
          <span className="text-muted-foreground">—</span>
        ) : (
          `${row.experience_years} yr`
        ),
    },
    {
      key: 'is_verified',
      header: 'Directory',
      render: (row) => (
        <StatusBadge status={row.is_verified ? 'verified' : 'unverified'} />
      ),
    },
    {
      key: 'is_active',
      header: 'Account',
      render: (row) => <StatusBadge status={row.is_active ? 'active' : 'inactive'} />,
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (row) => (
        <Button
          size="sm"
          variant={row.is_verified ? 'outline' : 'default'}
          onClick={(e) => {
            e.stopPropagation(); // don't also navigate to the detail page
            setVerifyTarget(row);
          }}
        >
          {row.is_verified ? 'Unverify' : 'Verify'}
        </Button>
      ),
    },
  ];

  const canSubmit =
    form.first_name.trim() &&
    form.last_name.trim() &&
    form.email.trim() &&
    form.password.length >= 8;

  return (
    <>
      <PageHeader
        title="Counselors"
        description="Platform-wide counselors. Only verified counselors appear in the student booking directory."
        actions={
          <Button onClick={() => setAddOpen(true)}>
            <Plus className="h-4 w-4" />
            Register counselor
          </Button>
        }
      />

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => row.counselor_id}
        loading={loading}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search name, email, qualification…"
        onRowClick={(row) => navigate(`/admin/counselors/${row.counselor_id}`)}
        empty={{
          icon: HeartHandshake,
          title: term ? 'No matching counselors' : 'No counselors yet',
          description: term
            ? 'Try a different search.'
            : 'Register a counselor to make them bookable by students and parents.',
        }}
      />

      {/* Register */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Register counselor</DialogTitle>
            <DialogDescription>
              Creates the account. They will not appear in the booking directory
              until you verify their credentials.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="first_name">First name</Label>
              <Input
                id="first_name"
                value={form.first_name}
                onChange={(e) => setForm({ ...form, first_name: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="last_name">Last name</Label>
              <Input
                id="last_name"
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="password">Temporary password</Label>
              <Input
                id="password"
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder="At least 8 characters"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="phone">Phone</Label>
              <Input
                id="phone"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="experience_years">Experience (years)</Label>
              <Input
                id="experience_years"
                type="number"
                min={0}
                value={form.experience_years}
                onChange={(e) => setForm({ ...form, experience_years: e.target.value })}
              />
            </div>

            {/* Schools served.
                A counselor is registered into the platform tenant, because
                booking is platform-wide. Alerting is not: the risk queue, the
                roster, the keyword tripwire and the crisis fan-out all resolve
                through these assignments. Leaving this empty registers a
                counselor who is bookable and verified but receives nothing —
                which is why the consequence is spelled out here rather than
                left to the operator to discover during an incident. */}
            <fieldset className="space-y-1.5 sm:col-span-2">
              <legend className="text-sm font-medium">Schools served</legend>
              <p className="text-xs text-muted-foreground">
                Risk alerts, the review queue and the student roster all follow
                this. A counselor with no school receives none of them.
              </p>
              {schoolsError ? (
                <p className="text-xs text-destructive">
                  Couldn&apos;t load schools.{' '}
                  <button
                    type="button"
                    onClick={loadSchools}
                    className="underline underline-offset-2"
                  >
                    Try again
                  </button>{' '}
                  — or assign them after registering.
                </p>
              ) : schools.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No schools yet. Register one first, then assign this counselor.
                </p>
              ) : (
                <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg border border-border p-2">
                  {schools.map((school) => {
                    const checked = form.tenant_ids.includes(school.tenant_id);
                    return (
                      <label
                        key={school.tenant_id}
                        className="flex cursor-pointer items-center gap-2 rounded px-1.5 py-1 text-sm hover:bg-muted/60"
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) =>
                            setForm({
                              ...form,
                              tenant_ids: e.target.checked
                                ? [...form.tenant_ids, school.tenant_id]
                                : form.tenant_ids.filter(
                                    (id) => id !== school.tenant_id,
                                  ),
                            })
                          }
                        />
                        <span className="min-w-0 truncate">{school.tenant_name}</span>
                        {school.school_code && (
                          <span className="shrink-0 text-xs text-muted-foreground">
                            {school.school_code}
                          </span>
                        )}
                      </label>
                    );
                  })}
                </div>
              )}
            </fieldset>
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="qualification">Qualification</Label>
              <Input
                id="qualification"
                value={form.qualification}
                onChange={(e) => setForm({ ...form, qualification: e.target.value })}
                placeholder="M.Phil Clinical Psychology"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={!canSubmit || saving}>
              {saving ? 'Registering…' : 'Register'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Verify / unverify — consequential, so it confirms. */}
      <ConfirmActionDialog
        open={verifyTarget !== null}
        onOpenChange={(open) => !open && setVerifyTarget(null)}
        title={verifyTarget?.is_verified ? 'Withdraw verification?' : 'Verify counselor?'}
        description={
          verifyTarget?.is_verified
            ? `${verifyTarget?.name} will be removed from the booking directory. Existing booked sessions are not cancelled.`
            : `${verifyTarget?.name} will become bookable by any student or parent on the platform. Confirm their credentials have been checked.`
        }
        confirmLabel={verifyTarget?.is_verified ? 'Withdraw' : 'Verify'}
        destructive={verifyTarget?.is_verified}
        onConfirm={async () => {
          if (verifyTarget) await handleToggleVerified(verifyTarget);
        }}
      />
    </>
  );
}
