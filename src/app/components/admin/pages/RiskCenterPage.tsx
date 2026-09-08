/**
 * Risk Center — cross-tenant oversight of risk assessments.
 *
 * Deliberately read-only. Recording a verdict is a clinical judgment that
 * belongs to the counselor who owns the case, and the counselor dashboard's
 * RiskQueue already does it. What a platform admin needs, and had no way to
 * see, is the view ACROSS schools: which queues are backing up, what is aging
 * past SLA, which schools have nobody assigned.
 *
 * (The counselor-facing /risk/queue is tenant-scoped to the caller, so an
 * admin hitting it would see their own empty queue — hence /admin/risk.)
 */

import { useCallback, useEffect, useState } from 'react';
import { ShieldAlert } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { apiErrorDetail, listAdminRisk, listSchools } from '../../../../lib/admin-api';
import type {
  AdminRiskFilters,
  AdminRiskRow,
  TenantRow,
} from '../../../../lib/admin-types';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../ui/select';
import { DataTable, type DataTableColumn } from '../widgets/DataTable';
import { PageHeader } from '../widgets/PageHeader';
import { StatusBadge } from '../widgets/StatusBadge';

const PAGE_SIZE = 25;

/** Beyond this, a pending assessment is flagged as aging. */
const STALE_AFTER_HOURS = 24;

// "any" rather than "" — Radix Select treats an empty string value as unset
// and would render the placeholder instead of the chosen option.
const ANY = 'any';

function AgeCell({ row }: { row: AdminRiskRow }) {
  const stale = row.review_status === 'pending' && row.age_hours >= STALE_AFTER_HOURS;
  const label =
    row.age_hours < 1
      ? 'just now'
      : row.age_hours < 48
        ? `${Math.round(row.age_hours)}h`
        : `${Math.round(row.age_hours / 24)}d`;

  return (
    <span
      className={`tabular-nums ${stale ? 'font-medium text-amber-700 dark:text-amber-400' : ''}`}
      title={stale ? `Pending for over ${STALE_AFTER_HOURS} hours` : undefined}
    >
      {label}
    </span>
  );
}

export function RiskCenterPage() {
  const navigate = useNavigate();

  const [rows, setRows] = useState<AdminRiskRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const [schools, setSchools] = useState<TenantRow[]>([]);
  const [status, setStatus] = useState('pending');
  const [level, setLevel] = useState(ANY);
  const [school, setSchool] = useState(ANY);

  useEffect(() => {
    // Populate the school filter once; the list is small and rarely changes.
    listSchools(1, 100)
      .then((data) => setSchools(data.tenants))
      .catch(() => setSchools([]));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    const filters: AdminRiskFilters = {
      ...(status !== ANY ? { review_status: status } : {}),
      ...(level !== ANY ? { risk_level: level } : {}),
      ...(school !== ANY ? { tenant_id: school } : {}),
    };
    try {
      const data = await listAdminRisk(page, PAGE_SIZE, filters);
      setRows(data.items);
      setTotal(data.total);
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Could not load risk assessments.'));
    } finally {
      setLoading(false);
    }
  }, [page, status, level, school]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setPage(1);
  }, [status, level, school]);

  const columns: DataTableColumn<AdminRiskRow>[] = [
    {
      key: 'risk_level',
      header: 'Level',
      render: (row) => <StatusBadge status={row.risk_level} />,
    },
    {
      key: 'student_name',
      header: 'Student',
      render: (row) => <span className="font-medium">{row.student_name}</span>,
    },
    { key: 'school_name', header: 'School' },
    {
      key: 'review_status',
      header: 'Status',
      render: (row) => <StatusBadge status={row.review_status ?? 'pending'} />,
    },
    {
      key: 'assigned_counselor_name',
      header: 'Assigned',
      render: (row) =>
        row.assigned_counselor_name ?? (
          <span className="text-muted-foreground">Unassigned</span>
        ),
    },
    {
      key: 'age_hours',
      header: 'Age',
      className: 'whitespace-nowrap',
      render: (row) => <AgeCell row={row} />,
    },
    {
      key: 'generated_by',
      header: 'Source',
      render: (row) => (
        <span className="text-xs text-muted-foreground">{row.generated_by ?? '—'}</span>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Risk Center"
        description="Assessments across every school, most severe and longest-waiting first. Read-only — counselors record the verdict."
      />

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => row.risk_id}
        total={total}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        loading={loading}
        onRowClick={(row) => navigate(`/admin/risk/${row.risk_id}`)}
        filters={
          <div className="flex flex-wrap items-center gap-2">
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>Any status</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="under_review">Under review</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
                <SelectItem value="escalated">Escalated</SelectItem>
              </SelectContent>
            </Select>

            <Select value={level} onValueChange={setLevel}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="Level" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>Any level</SelectItem>
                <SelectItem value="critical">Critical</SelectItem>
                <SelectItem value="red">High</SelectItem>
                <SelectItem value="yellow">Medium</SelectItem>
                <SelectItem value="green">Low</SelectItem>
              </SelectContent>
            </Select>

            <Select value={school} onValueChange={setSchool}>
              <SelectTrigger className="w-52">
                <SelectValue placeholder="School" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>All schools</SelectItem>
                {schools.map((s) => (
                  <SelectItem key={s.tenant_id} value={s.tenant_id}>
                    {s.tenant_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        }
        empty={{
          icon: ShieldAlert,
          title: 'Nothing to review',
          description:
            status === 'pending'
              ? 'No assessments are currently awaiting review.'
              : 'No assessments match these filters.',
        }}
      />
    </>
  );
}
