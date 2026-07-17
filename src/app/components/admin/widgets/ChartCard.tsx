import type { ReactNode } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../ui/card';
import { Skeleton } from '../../ui/skeleton';
import { EmptyState } from './EmptyState';
import { BarChart3 } from 'lucide-react';

interface ChartCardProps {
  title: string;
  description?: string;
  /** Right-aligned header slot (e.g. a range selector). */
  action?: ReactNode;
  loading?: boolean;
  /** Render the empty state instead of children (e.g. no data yet). */
  empty?: boolean;
  emptyLabel?: string;
  /** Chart body — wrap Recharts in a ResponsiveContainer; height comes from here. */
  height?: number;
  children: ReactNode;
}

export function ChartCard({
  title,
  description,
  action,
  loading = false,
  empty = false,
  emptyLabel = 'No data for this period yet',
  height = 260,
  children,
}: ChartCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="text-base">{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </div>
        {action}
      </CardHeader>
      <CardContent>
        <div style={{ height }}>
          {loading ? (
            <Skeleton className="h-full w-full" />
          ) : empty ? (
            <EmptyState icon={BarChart3} title={emptyLabel} />
          ) : (
            children
          )}
        </div>
      </CardContent>
    </Card>
  );
}
