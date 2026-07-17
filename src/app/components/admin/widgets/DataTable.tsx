import { useEffect, useRef, useState, type ComponentType, type ReactNode } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Search } from 'lucide-react';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { Skeleton } from '../../ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../ui/table';
import { cn } from '../../ui/utils';
import { EmptyState } from './EmptyState';

export interface DataTableColumn<T> {
  key: string;
  header: ReactNode;
  sortable?: boolean;
  className?: string;
  render?: (row: T) => ReactNode;
}

export interface DataTableSort {
  key: string;
  dir: 'asc' | 'desc';
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  /** Server-side pagination. Omit total to hide the pager. */
  total?: number;
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
  sort?: DataTableSort;
  onSortChange?: (sort: DataTableSort) => void;
  /** Debounced search box (300 ms). Omit onSearchChange to hide it. */
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
  /** Extra filter controls rendered next to the search box. */
  filters?: ReactNode;
  /** Right-aligned toolbar actions (e.g. an Add button). */
  actions?: ReactNode;
  loading?: boolean;
  empty?: {
    icon?: ComponentType<{ className?: string }>;
    title: string;
    description?: string;
    action?: ReactNode;
  };
  onRowClick?: (row: T) => void;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  total,
  page = 1,
  pageSize = 20,
  onPageChange,
  sort,
  onSortChange,
  searchValue = '',
  onSearchChange,
  searchPlaceholder = 'Search…',
  filters,
  actions,
  loading = false,
  empty = { title: 'Nothing here yet' },
  onRowClick,
}: DataTableProps<T>) {
  const [search, setSearch] = useState(searchValue);
  const searchTimer = useRef<ReturnType<typeof setTimeout>>();

  // Keep the local input in sync if the parent resets the search externally.
  useEffect(() => setSearch(searchValue), [searchValue]);

  const handleSearchInput = (value: string) => {
    setSearch(value);
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => onSearchChange?.(value), 300);
  };

  const handleSortClick = (key: string) => {
    if (!onSortChange) return;
    const dir = sort?.key === key && sort.dir === 'desc' ? 'asc' : 'desc';
    onSortChange({ key, dir });
  };

  const totalPages = total !== undefined ? Math.max(1, Math.ceil(total / pageSize)) : 1;
  const showToolbar = onSearchChange || filters || actions;
  const showPager = total !== undefined && onPageChange && total > pageSize;

  return (
    <div className="space-y-3">
      {showToolbar && (
        <div className="flex flex-wrap items-center gap-2">
          {onSearchChange && (
            <div className="relative w-full max-w-xs">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => handleSearchInput(e.target.value)}
                placeholder={searchPlaceholder}
                className="pl-8"
              />
            </div>
          )}
          {filters}
          {actions && <div className="ml-auto flex items-center gap-2">{actions}</div>}
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border bg-card">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              {columns.map((col) => (
                <TableHead key={col.key} className={col.className}>
                  {col.sortable && onSortChange ? (
                    <button
                      type="button"
                      onClick={() => handleSortClick(col.key)}
                      className="inline-flex items-center gap-1 hover:text-foreground"
                    >
                      {col.header}
                      {sort?.key === col.key ? (
                        sort.dir === 'desc' ? <ArrowDown className="h-3.5 w-3.5" /> : <ArrowUp className="h-3.5 w-3.5" />
                      ) : (
                        <ArrowUpDown className="h-3.5 w-3.5 opacity-40" />
                      )}
                    </button>
                  ) : (
                    col.header
                  )}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              Array.from({ length: Math.min(pageSize, 8) }).map((_, i) => (
                <TableRow key={`skeleton-${i}`}>
                  {columns.map((col) => (
                    <TableCell key={col.key}>
                      <Skeleton className="h-4 w-full max-w-32" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : rows.length === 0 ? (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={columns.length} className="p-0">
                  <EmptyState {...empty} />
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row) => (
                <TableRow
                  key={rowKey(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={cn(onRowClick && 'cursor-pointer')}
                >
                  {columns.map((col) => (
                    <TableCell key={col.key} className={col.className}>
                      {col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key] ?? '')}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {showPager && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {total} result{total === 1 ? '' : 's'}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={loading || page <= 1}
              onClick={() => onPageChange(page - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <span className="tabular-nums">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={loading || page >= totalPages}
              onClick={() => onPageChange(page + 1)}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
