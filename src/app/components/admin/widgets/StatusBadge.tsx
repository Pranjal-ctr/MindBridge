import { Badge } from '../../ui/badge';
import { cn } from '../../ui/utils';

/**
 * Color-coded status pill for tenants, users, counselors, and risk records.
 * Legacy `acknowledged` (pre-P0 counselor reviews) renders as "Under review".
 */

const STATUS_STYLES: Record<string, { label: string; className: string }> = {
  // Tenant / user lifecycle
  active: { label: 'Active', className: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-900' },
  trial: { label: 'Trial', className: 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950 dark:text-sky-300 dark:border-sky-900' },
  inactive: { label: 'Inactive', className: 'bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-900 dark:text-slate-400 dark:border-slate-800' },
  suspended: { label: 'Suspended', className: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-900' },
  archived: { label: 'Archived', className: 'bg-slate-100 text-slate-500 border-slate-200 line-through dark:bg-slate-900 dark:text-slate-500 dark:border-slate-800' },
  deleted: { label: 'Deleted', className: 'bg-slate-100 text-slate-500 border-slate-200 line-through dark:bg-slate-900 dark:text-slate-500 dark:border-slate-800' },
  verified: { label: 'Verified', className: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-900' },
  unverified: { label: 'Unverified', className: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-900' },
  // Risk review workflow
  pending: { label: 'Pending', className: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-900' },
  under_review: { label: 'Under review', className: 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950 dark:text-sky-300 dark:border-sky-900' },
  acknowledged: { label: 'Under review', className: 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950 dark:text-sky-300 dark:border-sky-900' },
  resolved: { label: 'Resolved', className: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-900' },
  escalated: { label: 'Escalated', className: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-300 dark:border-red-900' },
  // Risk levels
  green: { label: 'Low', className: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-900' },
  yellow: { label: 'Medium', className: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-900' },
  red: { label: 'High', className: 'bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950 dark:text-orange-300 dark:border-orange-900' },
  critical: { label: 'Critical', className: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-300 dark:border-red-900' },
};

interface StatusBadgeProps {
  status: string | null | undefined;
  /** Override the derived label (e.g. show the raw value). */
  label?: string;
  className?: string;
}

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const key = (status ?? '').toLowerCase();
  const style = STATUS_STYLES[key];
  return (
    <Badge
      variant="outline"
      className={cn('capitalize', style?.className, className)}
    >
      {label ?? style?.label ?? (status || 'Unknown')}
    </Badge>
  );
}
