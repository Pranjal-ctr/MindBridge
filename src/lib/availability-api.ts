/**
 * Kio availability engine client.
 *
 * Counselors state a recurring weekly pattern; students and parents search by
 * time and get back concrete slots. There are no slot rows to create or claim —
 * the backend derives slots on request and re-derives them again inside the
 * booking transaction, so anything here is a display of what *was* true a
 * moment ago, never a reservation.
 */

import api from './api';
import type {
  AvailabilitySearchResponse,
  AvailableSlot,
  BookResponse,
  CounselorSchedule,
  CounselorScheduleException,
  DayOfWeek,
  ExceptionListResponse,
  ScheduleListResponse,
  SessionSettings,
} from './types';

export const DAY_NAMES = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
] as const;

/** Presets offered instead of making people think in 24-hour ranges. */
export const TIME_WINDOWS = [
  { id: 'morning', label: 'Morning', sublabel: '8am – 12pm', startHour: 8, endHour: 12 },
  { id: 'afternoon', label: 'Afternoon', sublabel: '12pm – 5pm', startHour: 12, endHour: 17 },
  { id: 'evening', label: 'Evening', sublabel: '5pm – 9pm', startHour: 17, endHour: 21 },
  { id: 'night', label: 'Night', sublabel: '9pm – 12am', startHour: 21, endHour: 24 },
] as const;

export type TimeWindowId = (typeof TIME_WINDOWS)[number]['id'];

/**
 * The viewer's own IANA zone.
 *
 * Used only to render times and to turn "6pm on the 12th" into an instant. The
 * backend still decides what is bookable; this never widens what is offered.
 */
export function viewerTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata';
  } catch {
    return 'Asia/Kolkata';
  }
}

/**
 * Turn a local date and hour range into an absolute UTC window.
 *
 * `hour` 24 means midnight at the end of that day, which is how the Night
 * preset expresses "until the day is over" without naming the next date.
 */
export function toUtcWindow(day: Date, startHour: number, endHour: number): {
  window_start: string;
  window_end: string;
} {
  const start = new Date(day);
  start.setHours(startHour, 0, 0, 0);
  const end = new Date(day);
  end.setHours(0, 0, 0, 0);
  end.setHours(end.getHours() + endHour);
  return { window_start: start.toISOString(), window_end: end.toISOString() };
}

/** Local YYYY-MM-DD, avoiding toISOString()'s shift into the previous day. */
export function toLocalDateString(day: Date): string {
  const month = `${day.getMonth() + 1}`.padStart(2, '0');
  const date = `${day.getDate()}`.padStart(2, '0');
  return `${day.getFullYear()}-${month}-${date}`;
}

// ── Search & booking (student and parent) ─────────────────────────────

export async function searchAvailability(params: {
  window_start: string;
  window_end: string;
  counselor_id?: string;
  duration_minutes?: number;
  limit?: number;
}): Promise<AvailabilitySearchResponse> {
  const { data } = await api.get<AvailabilitySearchResponse>(
    '/counselors/availability/search',
    { params: { ...params, timezone: viewerTimeZone() } },
  );
  return data;
}

/**
 * Book a concrete slot.
 *
 * `student_id` is required for parents and ignored for students — the backend
 * resolves a student's own profile rather than trusting the field.
 */
export async function bookSlot(slot: AvailableSlot, studentId?: string): Promise<BookResponse> {
  const { data } = await api.post<BookResponse>('/counselors/book', {
    counselor_id: slot.counselor_id,
    starts_at: slot.start,
    ...(studentId ? { student_id: studentId } : {}),
  });
  return data;
}

export async function cancelSession(sessionId: string, reason?: string): Promise<BookResponse> {
  const { data } = await api.post<BookResponse>(
    `/counselors/sessions/${sessionId}/cancel`,
    { reason: reason ?? null },
  );
  return data;
}

/** Group slots by counselor so the UI can show one card per person. */
export function groupByCounselor(slots: AvailableSlot[]) {
  const groups = new Map<string, { counselorId: string; name: string; slots: AvailableSlot[] }>();
  for (const slot of slots) {
    const existing = groups.get(slot.counselor_id);
    if (existing) {
      existing.slots.push(slot);
    } else {
      groups.set(slot.counselor_id, {
        counselorId: slot.counselor_id,
        name: slot.counselor_name,
        slots: [slot],
      });
    }
  }
  return [...groups.values()];
}

// ── Counselor: recurring schedule ─────────────────────────────────────

export async function listSchedules(): Promise<ScheduleListResponse> {
  const { data } = await api.get<ScheduleListResponse>('/counselors/schedules');
  return data;
}

export async function createSchedule(payload: {
  day_of_week: DayOfWeek;
  start_time: string;
  end_time: string;
}): Promise<CounselorSchedule> {
  const { data } = await api.post<CounselorSchedule>('/counselors/schedules', payload);
  return data;
}

export async function updateSchedule(
  scheduleId: string,
  payload: Partial<{ start_time: string; end_time: string; is_active: boolean }>,
): Promise<CounselorSchedule> {
  const { data } = await api.patch<CounselorSchedule>(
    `/counselors/schedules/${scheduleId}`,
    payload,
  );
  return data;
}

export async function deleteSchedule(scheduleId: string): Promise<void> {
  await api.delete(`/counselors/schedules/${scheduleId}`);
}

// ── Counselor: exceptions ─────────────────────────────────────────────

export async function listExceptions(): Promise<ExceptionListResponse> {
  const { data } = await api.get<ExceptionListResponse>('/counselors/exceptions');
  return data;
}

export async function createException(payload: {
  exception_date: string;
  start_time?: string | null;
  end_time?: string | null;
  is_available: boolean;
  reason?: string | null;
}): Promise<CounselorScheduleException> {
  const { data } = await api.post<CounselorScheduleException>(
    '/counselors/exceptions',
    payload,
  );
  return data;
}

export async function deleteException(exceptionId: string): Promise<void> {
  await api.delete(`/counselors/exceptions/${exceptionId}`);
}

// ── Counselor: session settings ───────────────────────────────────────

export async function getSessionSettings(): Promise<SessionSettings> {
  const { data } = await api.get<SessionSettings>('/counselors/settings');
  return data;
}

export async function updateSessionSettings(
  payload: Partial<SessionSettings>,
): Promise<SessionSettings> {
  const { data } = await api.put<SessionSettings>('/counselors/settings', payload);
  return data;
}

/** "09:00:00" -> "9:00 AM", for a UI that never shows seconds. */
export function formatTime(value: string): string {
  const [hourText, minute] = value.split(':');
  const hour = Number(hourText);
  const suffix = hour >= 12 ? 'PM' : 'AM';
  const display = hour % 12 === 0 ? 12 : hour % 12;
  return `${display}:${minute} ${suffix}`;
}
