/**
 * Notification bell — the in-app end of the crisis escalation path.
 *
 * These rows are how a high-risk alert reaches a counselor who is already
 * signed in. Before this component they were written by
 * app/intelligence/crisis.py and read by nothing, so the cases worth pinning
 * are: the unread count is visible without opening anything, alerts actually
 * render, and a failing poll degrades quietly instead of blanking the header
 * a counselor is working in.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NotificationBell } from './NotificationBell';

const getMock = vi.fn();
const putMock = vi.fn();

vi.mock('../../lib/api', () => ({
  default: {
    get: (...args: unknown[]) => getMock(...args),
    put: (...args: unknown[]) => putMock(...args),
  },
}));

function notification(overrides: Record<string, unknown> = {}) {
  return {
    notification_id: 'n1',
    user_id: 'u1',
    title: 'High-risk alert',
    message: 'High-risk alert: Sarah Johnson -- review required.',
    is_read: false,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function respondWith(notifications: unknown[], unread_count: number) {
  getMock.mockResolvedValue({
    data: { notifications, total: notifications.length, unread_count },
  });
}

describe('NotificationBell', () => {
  beforeEach(() => {
    getMock.mockReset();
    putMock.mockReset();
    putMock.mockResolvedValue({});
  });

  it('shows the unread count without the dropdown being opened', async () => {
    respondWith([notification()], 1);

    render(<NotificationBell />);

    // The badge is the entire point: a counselor must see there is something
    // waiting without clicking anything.
    expect(await screen.findByText('1')).toBeInTheDocument();
    expect(
      screen.getByLabelText('Notifications, 1 unread'),
    ).toBeInTheDocument();
  });

  it('caps the badge at 9+', async () => {
    respondWith([notification()], 23);
    render(<NotificationBell />);
    expect(await screen.findByText('9+')).toBeInTheDocument();
  });

  it('renders a crisis alert when opened', async () => {
    respondWith([notification()], 1);
    render(<NotificationBell />);

    await userEvent.click(await screen.findByRole('button', { name: /notifications/i }));

    expect(await screen.findByText('High-risk alert')).toBeInTheDocument();
    expect(
      screen.getByText(/Sarah Johnson -- review required/),
    ).toBeInTheDocument();
  });

  it('marks a notification read and drops the badge', async () => {
    respondWith([notification()], 1);
    render(<NotificationBell />);

    await userEvent.click(await screen.findByRole('button', { name: /notifications/i }));
    await userEvent.click(await screen.findByText('High-risk alert'));

    await waitFor(() =>
      expect(putMock).toHaveBeenCalledWith('/notifications/n1/read'),
    );
    // Optimistic: badge clears without waiting for a refetch.
    expect(screen.queryByText('1')).not.toBeInTheDocument();
  });

  it('marks all read', async () => {
    respondWith([notification(), notification({ notification_id: 'n2' })], 2);
    render(<NotificationBell />);

    await userEvent.click(await screen.findByRole('button', { name: /notifications/i }));
    await userEvent.click(await screen.findByText(/mark all read/i));

    await waitFor(() =>
      expect(putMock).toHaveBeenCalledWith('/notifications/read-all'),
    );
  });

  it('shows an empty state rather than an empty box', async () => {
    respondWith([], 0);
    render(<NotificationBell />);

    await userEvent.click(await screen.findByRole('button', { name: /notifications/i }));

    expect(await screen.findByText(/all caught up/i)).toBeInTheDocument();
  });

  it('degrades quietly when the poll fails', async () => {
    // A failed poll must not blank or crash the header a counselor is working
    // in — the bell stays, and offers a retry when opened.
    getMock.mockRejectedValue(new Error('network'));

    render(<NotificationBell />);

    const bell = await screen.findByRole('button', { name: /notifications/i });
    expect(bell).toBeInTheDocument();
    // No badge, because we have no count — not a fabricated zero-state alert.
    expect(screen.queryByText('9+')).not.toBeInTheDocument();

    await userEvent.click(bell);
    expect(await screen.findByText(/couldn't load notifications/i)).toBeInTheDocument();
  });
});
