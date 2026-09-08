/**
 * Kio Notifications API.
 *
 * These rows are how a crisis alert reaches a human: app/intelligence/crisis.py
 * fans out to counselors, school admins and (content-free) linked parents when
 * a risk assessment crosses the threshold. Until this client existed, nothing
 * in the frontend read them.
 */

import api from './api';
import type { NotificationListResponse } from './types';

/**
 * Recent notifications for the signed-in user, newest first.
 *
 * Note the trailing slash — the backend route is `/notifications/`, and
 * without it FastAPI answers with a 307 redirect.
 */
export async function listNotifications(
  page = 1,
  pageSize = 20,
): Promise<NotificationListResponse> {
  const { data } = await api.get<NotificationListResponse>('/notifications/', {
    params: { page, page_size: pageSize },
  });
  return data;
}

export async function markNotificationRead(notificationId: string): Promise<void> {
  await api.put(`/notifications/${notificationId}/read`);
}

export async function markAllNotificationsRead(): Promise<void> {
  await api.put('/notifications/read-all');
}
