/**
 * Kio Child Insights Hook
 * Parent-facing aggregated insights for a linked child.
 *
 * Refresh strategy: a long background interval (5 min) + refetch when the
 * window regains focus, plus an explicit `refetch` for a manual "Refresh"
 * button -- deliberately not aggressive polling, since the underlying data
 * only changes after a student interaction.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import api from '../lib/api';
import type { ChildInsightResponse } from '../lib/types';

const POLL_INTERVAL_MS = 5 * 60 * 1000;

export function useChildInsights(studentId: string | null) {
  const [insights, setInsights] = useState<ChildInsightResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const studentIdRef = useRef(studentId);
  studentIdRef.current = studentId;

  const fetchInsights = useCallback(async (opts?: { silent?: boolean }) => {
    const id = studentIdRef.current;
    if (!id) {
      setInsights(null);
      return;
    }
    try {
      if (opts?.silent) setIsRefreshing(true);
      else setIsLoading(true);
      const { data } = await api.get<ChildInsightResponse>(`/parents/children/${id}/insights`);
      setInsights(data);
    } catch {
      if (!opts?.silent) setInsights(null);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchInsights();
  }, [studentId, fetchInsights]);

  useEffect(() => {
    const interval = setInterval(() => fetchInsights({ silent: true }), POLL_INTERVAL_MS);
    const onFocus = () => fetchInsights({ silent: true });
    window.addEventListener('focus', onFocus);
    return () => {
      clearInterval(interval);
      window.removeEventListener('focus', onFocus);
    };
  }, [fetchInsights]);

  return {
    insights,
    isLoading,
    isRefreshing,
    refetch: () => fetchInsights({ silent: true }),
  };
}
