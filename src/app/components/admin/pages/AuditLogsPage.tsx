/**
 * Audit Logs — the immutable trail of sensitive actions.
 *
 * This is the page you open when someone asks "who looked at that student's
 * conversation, and when" — break-glass access, tenant suspension, password
 * resets, crisis alerts and counselor verification all land here.
 *
 * Two things shape the design:
 *
 * 1. Filtering and paging are entirely server-side. The table is append-only
 *    and grows without bound, so anything that fetched a large window and
 *    narrowed it in the browser would eventually be asking for the whole
 *    history of the platform.
 *
 * 2. Every row is already content-minimal by the time it arrives — the
 *    backend scrubs `details` on the way *in*, not on the way out. This page
 *    therefore renders what it is given rather than deciding what is safe to
 *    show, which is the only version of that rule that cannot drift.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Download, ScrollText, X } from 'lucide-react';
import { toast } from 'sonner';
import {
  apiErrorDetail,
  downloadBlob,
  exportAuditLogsCsv,
  listAuditLogs,
} from '../../../../lib/admin-api';
import type {
  AuditLogEntry,
  AuditLogFilters,
  AuditResult,
  AuditSeverity,
} from '../../../../lib/admin-types';
import { Badge } from '../../ui/badge';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../ui/select';
import { DataTable, type DataTableColumn } from '../widgets/DataTable';
import { PageHeader } from '../widgets/PageHeader';

const PAGE_SIZE = 50;

/** Actions worth one-click filtering — the security-relevant ones. */
const QUICK_FILTERS: { label: string; action: string }[] = [
  { label: 'All', action: '' },
  { label: 'Break-glass', action: 'break_glass' },
  { label: 'Auth', action: 'auth.' },
  { label: 'Crisis', action: 'crisis' },
  { label: 'Safety', action: 'safety_' },
  { label: 'Risk', action: 'risk' },
  { label: 'School', action: 'tenant.' },
  { label: 'User', action: 'user.' },
  { label: 'Admin', action: 'admin.' },
];

// "any" rather than "" because a Radix Select cannot hold an empty-string value.
const ANY = 'any';

const SEVERITIES: AuditSeverity[] = ['info', 'notice', 'warning', 'critical'];
const RESULTS: AuditResult[] = ['success', 'failure'];
const ROLES = ['student', 'parent', 'counselor', 'school_admin', 'admin', 'system'];

const SEVERITY_STYLES: Record<AuditSeverity, string> = {
  info: 'bg-muted text-muted-foreground',
  notice: 'bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-200',
  warning: 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200',
  critical: 'bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200',
};

function SeverityBadge({ severity }: { severity: AuditSeverity }) {
  return (
    <Badge className={`${SEVERITY_STYLES[severity] ?? SEVERITY_STYLES.info} border-0`}>
      {severity}
    </Badge>
  );
}

function ActorCell({ entry }: { entry: AuditLogEntry }) {
  // A null actor with a `system` role is a background pipeline, not a gap in
  // the record. A null actor with no role is genuinely unattributed — most
  // often a failed login for an address that matches no account.
  const name = entry.user_name ?? (entry.user_role === 'system' ? 'System' : '—');
  return (
    <div className="min-w-0">
      <div className="truncate">{name}</div>
      {entry.user_role && (
        <div className="text-xs text-muted-foreground">{entry.user_role}</div>
      )}
    </div>
  );
}

/** Slide-over showing one event in full. */
function DetailDrawer({
  entry,
  onClose,
}: {
  entry: AuditLogEntry;
  onClose: () => void;
}) {
  const rows: [string, string][] = [
    ['Time', new Date(entry.created_at).toLocaleString()],
    ['Time (UTC)', new Date(entry.created_at).toISOString()],
    ['Action', entry.action],
    ['Result', entry.result],
    ['Severity', entry.severity],
    ['Actor', entry.user_name ?? (entry.user_role === 'system' ? 'System' : '—')],
    ['Actor role', entry.user_role ?? '—'],
    ['Actor id', entry.user_id ?? '—'],
    ['School', entry.school_name ?? '—'],
    ['Entity type', entry.entity_type ?? '—'],
    ['Entity id', entry.entity_id ?? '—'],
    ['IP address', entry.ip_address ?? '—'],
    ['User agent', entry.user_agent ?? '—'],
    ['Request id', entry.request_id ?? '—'],
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-label="Audit event detail"
      onClick={onClose}
    >
      <div
        className="h-full w-full max-w-lg overflow-y-auto bg-background p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="truncate font-heading text-lg">{entry.action}</h2>
            <p className="text-xs text-muted-foreground">{entry.audit_id}</p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </div>

        <dl className="space-y-2 text-sm">
          {rows.map(([label, value]) => (
            <div key={label} className="grid grid-cols-3 gap-2">
              <dt className="text-muted-foreground">{label}</dt>
              <dd className="col-span-2 break-all">{value}</dd>
            </div>
          ))}
        </dl>

        <div className="mt-6">
          <h3 className="mb-2 text-sm font-medium">Metadata</h3>
          {entry.details && Object.keys(entry.details).length > 0 ? (
            <pre className="overflow-x-auto rounded bg-muted p-3 text-xs">
              {JSON.stringify(entry.details, null, 2)}
            </pre>
          ) : (
            <p className="text-sm text-muted-foreground">No metadata recorded.</p>
          )}
          <p className="mt-3 text-xs text-muted-foreground">
            Audit records never contain message content, risk narratives,
            passwords or tokens. Metadata is references and short values only.
          </p>
        </div>
      </div>
    </div>
  );
}

export function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [selected, setSelected] = useState<AuditLogEntry | null>(null);

  const [action, setAction] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [severity, setSeverity] = useState<string>(ANY);
  const [result, setResult] = useState<string>(ANY);
  const [actorRole, setActorRole] = useState<string>(ANY);
  const [requestId, setRequestId] = useState('');

  const filters: AuditLogFilters = useMemo(
    () => ({
      ...(action ? { action } : {}),
      // The API takes datetimes; a bare date means "from midnight" / "to
      // end of day", otherwise a same-day range would return nothing.
      ...(dateFrom ? { date_from: `${dateFrom}T00:00:00` } : {}),
      ...(dateTo ? { date_to: `${dateTo}T23:59:59` } : {}),
      ...(severity !== ANY ? { severity: severity as AuditSeverity } : {}),
      ...(result !== ANY ? { result: result as AuditResult } : {}),
      ...(actorRole !== ANY ? { actor_role: actorRole } : {}),
      ...(requestId.trim() ? { request_id: requestId.trim() } : {}),
    }),
    [action, dateFrom, dateTo, severity, result, actorRole, requestId],
  );

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
  }, [page, filters]);

  useEffect(() => {
    load();
  }, [load]);

  // Any filter change invalidates the current page number.
  useEffect(() => {
    setPage(1);
  }, [filters]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await exportAuditLogsCsv(filters);
      downloadBlob(
        blob,
        `kio-audit-logs-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '')}Z.csv`,
      );
      toast.success('Export downloaded. This export was itself recorded.');
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
    { key: 'user', header: 'Actor', render: (row) => <ActorCell entry={row} /> },
    {
      key: 'school',
      header: 'School',
      render: (row) =>
        row.school_name || <span className="text-muted-foreground">—</span>,
    },
    {
      key: 'action',
      header: 'Action',
      render: (row) => <code className="text-xs">{row.action}</code>,
    },
    {
      key: 'entity',
      header: 'Target',
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
      key: 'result',
      header: 'Result',
      render: (row) =>
        row.result === 'failure' ? (
          <span className="text-destructive">failure</span>
        ) : (
          <span className="text-muted-foreground">success</span>
        ),
    },
    {
      key: 'severity',
      header: 'Severity',
      render: (row) => <SeverityBadge severity={row.severity} />,
    },
    {
      key: 'request_id',
      header: 'Request',
      className: 'whitespace-nowrap',
      render: (row) =>
        row.request_id ? (
          <code className="text-xs" title={row.request_id}>
            {row.request_id.slice(0, 8)}…
          </code>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Audit Logs"
        description="Immutable trail of every sensitive action. Records are never edited or deleted, and viewing or exporting this page is itself recorded."
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
        onRowClick={setSelected}
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

            <Select value={severity} onValueChange={setSeverity}>
              <SelectTrigger className="w-[140px]" aria-label="Severity">
                <SelectValue placeholder="Severity" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>Any severity</SelectItem>
                {SEVERITIES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={result} onValueChange={setResult}>
              <SelectTrigger className="w-[130px]" aria-label="Result">
                <SelectValue placeholder="Result" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>Any result</SelectItem>
                {RESULTS.map((r) => (
                  <SelectItem key={r} value={r}>
                    {r}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={actorRole} onValueChange={setActorRole}>
              <SelectTrigger className="w-[150px]" aria-label="Actor role">
                <SelectValue placeholder="Role" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>Any role</SelectItem>
                {ROLES.map((r) => (
                  <SelectItem key={r} value={r}>
                    {r}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Input
              value={requestId}
              onChange={(e) => setRequestId(e.target.value)}
              placeholder="Request id"
              className="w-[160px]"
              aria-label="Request id"
            />
          </div>
        }
        empty={{
          icon: ScrollText,
          title: 'No audit entries',
          description:
            Object.keys(filters).length > 0
              ? 'No entries match these filters.'
              : 'Sensitive actions will appear here as they happen.',
        }}
      />

      {selected && (
        <DetailDrawer entry={selected} onClose={() => setSelected(null)} />
      )}
    </>
  );
}
