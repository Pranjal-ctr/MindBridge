/**
 * Audit Logs — the immutable trail of sensitive actions.
 *
 * The backend for this (filters + CSV export) shipped in the admin P0 commit,
 * and `listAuditLogs` / `exportAuditLogsCsv` have been sitting in admin-api.ts
 * unused ever since: the page was a stub, so the trail was unreachable.
 *
 * This is the page you open when someone asks "who looked at that student's
 * conversation, and when" — break-glass access, tenant suspension, password
 * resets and counselor verification all land here.
 */

import { useCallback, useEffect, useState } from 'react';
import { Download, ScrollText } from 'lucide-react';
import { toast } from 'sonner';
import {
  apiErrorDetail,
  downloadBlob,
  exportAuditLogsCsv,
  listAuditLogs,
} from '../../../../lib/admin-api';
import type { AuditLogEntry, AuditLogFilters } from '../../../../lib/admin-types';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { DataTable, type DataTableColumn } from '../widgets/DataTable';
import { PageHeader } from '../widgets/PageHeader';

const PAGE_SIZE = 50;

/** Actions worth one-click filtering — the security-relevant ones. */
const QUICK_FILTERS: { label: string; action: string }[] = [
  { label: 'All', action: '' },
  { label: 'Break-glass', action: 'break_glass' },
  { label: 'Crisis', action: 'crisis' },
  { label: 'Tenant', action: 'tenant.' },
  { label: 'User', action: 'user.' },
  { label: 'Counselor', action: 'counselor' },
];

function RoleCell({ entry }: { entry: AuditLogEntry }) {
  if (!entry.user_name) {
    // A null actor is the system itself (background pipeline), not a gap.
    return <span className="text-muted-foreground">System</span>;
  }
  return (
    <div className="min-w-0">
      <div className="truncate">{entry.user_name}</div>
      {entry.user_role && (
        <div className="text-xs text-muted-foreground">{entry.user_role}</div>
      )}
    </div>
  );
}

export function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  const [action, setAction] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const filters: AuditLogFilters = {
    ...(action ? { action } : {}),
    // The API takes datetimes; a bare date means "from midnight" / "to
    // end of day", otherwise a same-day range would return nothing.
    ...(dateFrom ? { date_from: `${dateFrom}T00:00:00` } : {}),
    ...(dateTo ? { date_to: `${dateTo}T23:59:59` } : {}),
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listAuditLogs(page, PAGE_SIZE, filters);
      setLogs(data.logs);
      setTotal(data.total);
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Could not load audit logs.'));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, action, dateFrom, dateTo]);

  useEffect(() => {
    load();
  }, [load]);

  // Any filter change invalidates the current page number.
  useEffect(() => {
    setPage(1);
  }, [action, dateFrom, dateTo]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await exportAuditLogsCsv(filters);
      downloadBlob(blob, `kio-audit-logs-${new Date().toISOString().slice(0, 10)}.csv`);
      toast.success('Export downloaded.');
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Export failed.'));
    } finally {
      setExporting(false);
    }
  };

  const columns: DataTableColumn<AuditLogEntry>[] = [
    {
      key: 'created_at',
      header: 'When',
      className: 'whitespace-nowrap',
      render: (row) => (
        <span title={new Date(row.created_at).toISOString()}>
          {new Date(row.created_at).toLocaleString()}
        </span>
      ),
    },
    { key: 'user', header: 'Actor', render: (row) => <RoleCell entry={row} /> },
    {
      key: 'action',
      header: 'Action',
      render: (row) => <code className="text-xs">{row.action}</code>,
    },
    {
      key: 'entity',
      header: 'Entity',
      render: (row) =>
        row.entity_type ? (
          <div className="min-w-0">
            <div className="text-sm">{row.entity_type}</div>
            {row.entity_id && (
              <div
                className="truncate text-xs text-muted-foreground"
                title={row.entity_id}
              >
                {row.entity_id.slice(0, 8)}…
              </div>
            )}
          </div>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      key: 'ip_address',
      header: 'IP',
      className: 'whitespace-nowrap',
      render: (row) => row.ip_address || <span className="text-muted-foreground">—</span>,
    },
    {
      key: 'details',
      header: 'Details',
      render: (row) =>
        row.details && Object.keys(row.details).length > 0 ? (
          <details className="max-w-xs">
            <summary className="cursor-pointer text-xs text-primary">View</summary>
            <pre className="mt-1 overflow-x-auto rounded bg-muted p-2 text-xs">
              {JSON.stringify(row.details, null, 2)}
            </pre>
          </details>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Audit Logs"
        description="Immutable trail of every sensitive action. Records are never edited or deleted."
        actions={
          <Button variant="outline" onClick={handleExport} disabled={exporting}>
            <Download className="h-4 w-4" />
            {exporting ? 'Exporting…' : 'Export CSV'}
          </Button>
        }
      />

      <DataTable
        columns={columns}
        rows={logs}
        rowKey={(row) => row.audit_id}
        total={total}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        loading={loading}
        filters={
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex flex-wrap gap-1">
              {QUICK_FILTERS.map((f) => (
                <Button
                  key={f.label}
                  size="sm"
                  variant={action === f.action ? 'default' : 'outline'}
                  onClick={() => setAction(f.action)}
                >
                  {f.label}
                </Button>
              ))}
            </div>
            <Input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-auto"
              aria-label="From date"
            />
            <Input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-auto"
              aria-label="To date"
            />
          </div>
        }
        empty={{
          icon: ScrollText,
          title: 'No audit entries',
          description:
            action || dateFrom || dateTo
              ? 'No entries match these filters.'
              : 'Sensitive actions will appear here as they happen.',
        }}
      />
    </>
  );
}
