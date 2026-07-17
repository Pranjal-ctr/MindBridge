/**
 * Kio Wellness Hook
 * Student's computed wellness score + one-tap mood check-in.
 */

import { useCallback, useEffect, useState } from 'react';
import api from '../lib/api';
import type { MoodCheckin, MoodCheckinResponse, WellnessScoreResponse } from '../lib/types';

export function useWellnessScore() {
  const [score, setScore] = useState<WellnessScoreResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchScore = useCallback(async () => {
    try {
      const { data } = await api.get<WellnessScoreResponse>('/wellness/score');
      setScore(data);
    } catch {
      setScore(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchScore();
  }, [fetchScore]);

  const checkInMood = useCallback(async (mood: MoodCheckin): Promise<MoodCheckinResponse> => {
    const { data } = await api.post<MoodCheckinResponse>('/wellness/mood', { mood });
    setScore(data.wellness);
    return data;
  }, []);

  return { score, isLoading, checkInMood, refetch: fetchScore };
}
