import type { ComponentType, ReactNode } from 'react';
import { Card, CardContent } from '../../ui/card';
import { Skeleton } from '../../ui/skeleton';
import { cn } from '../../ui/utils';

interface StatCardProps {
  label: string;
  value: ReactNode;
  icon?: ComponentType<{ className?: string }>;
  /** Small line under the value, e.g. "+12 this week". */
  hint?: ReactNode;
  loading?: boolean;
  className?: string;
}

export function StatCard({ label, value, icon: Icon, hint, loading, className }: StatCardProps) {
  return (
    <Card className={cn('py-4', className)}>
      <CardContent className="px-4">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground">{label}</p>
          {Icon && <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />}
        </div>
        {loading ? (
          <Skeleton className="mt-2 h-7 w-16" />
        ) : (
          <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
        )}
        {hint && !loading && (
          <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
        )}
      </CardContent>
    </Card>
  );
}
