/**
 * Kio School Analytics API.
 *
 * Everything here is school-wide and aggregate — there is deliberately no
 * per-student endpoint. A school admin sees patterns, never conversations.
 */

import api from './api';
import type { AnalyticsOverview } from './types';

/** School-wide overview for the signed-in admin's school. */
export async function getAnalyticsOverview(): Promise<AnalyticsOverview> {
  const { data } = await api.get<AnalyticsOverview>('/analytics/overview');
  return data;
}
