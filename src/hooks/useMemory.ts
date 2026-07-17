/**
 * Kio Memory Hook
 * Manages student memory items (Growth Profile).
 */

import { useCallback, useEffect, useState } from 'react';
import api from '../lib/api';
import type { MemoryItem, MemoryListResponse, MemoryType } from '../lib/types';

export function useMemories(filterType?: MemoryType | null) {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMemories = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const params: Record<string, string> = {};
      if (filterType) params.memory_type = filterType;

      const { data } = await api.get<MemoryListResponse>('/memory/', { params });
      setMemories(data.items);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load memories';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [filterType]);

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);

  const deleteMemory = useCallback(async (memoryId: string) => {
    await api.delete(`/memory/${memoryId}`);
    setMemories((prev) => prev.filter((m) => m.memory_id !== memoryId));
  }, []);

  const togglePin = useCallback(async (memoryId: string, isPinned: boolean) => {
    const { data } = await api.patch<MemoryItem>(`/memory/${memoryId}/pin`, {
      is_pinned: !isPinned,
    });
    setMemories((prev) =>
      prev.map((m) => (m.memory_id === memoryId ? data : m))
    );
  }, []);

  // Group memories by type
  const groupedMemories = memories.reduce(
    (acc, mem) => {
      if (!acc[mem.memory_type]) acc[mem.memory_type] = [];
      acc[mem.memory_type].push(mem);
      return acc;
    },
    {} as Record<string, MemoryItem[]>
  );

  return {
    memories,
    groupedMemories,
    isLoading,
    error,
    deleteMemory,
    togglePin,
    refetch: fetchMemories,
  };
}
