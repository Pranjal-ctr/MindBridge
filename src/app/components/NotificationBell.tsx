/**
 * Notification bell — the UI end of the crisis alert path.
 *
 * `app/intelligence/crisis.py` fans out notifications when a risk assessment
 * crosses the threshold. Before this component those rows were written and
 * never read by anything: no bell, no page, no toast. For counselors and
 * school admins this is the in-app half of the escalation (the other half is
 * the staff email sent from the same workflow).
 *
 * Polling rather than websockets: Kio has no realtime transport yet, and a
 * 60s poll that pauses on a hidden tab is a proportionate amount of machinery
 * for something already backed by email.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Bell, Check, Loader2 } from 'lucide-react';
import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../../lib/notifications-api';
import type { NotificationItem } from '../../lib/types';

const POLL_INTERVAL_MS = 60_000;

/** Compact relative time — avoids pulling a formatting library in for this. */
function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const seconds = Math.floor((Date.now() - then) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function NotificationBell({ className = '' }: { className?: string }) {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const data = await listNotifications(1, 20);
      setItems(data.notifications);
      setUnread(data.unread_count);
      setError(false);
    } catch {
      // A failed poll is not worth interrupting the page for — the bell simply
      // keeps showing the last known state and retries on the next tick.
      setError(true);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Poll, but never while the tab is hidden: a backgrounded dashboard left
  // open overnight would otherwise make ~500 pointless requests.
  useEffect(() => {
    load();

    let timer: ReturnType<typeof setInterval> | null = null;

    const start = () => {
      if (timer === null) timer = setInterval(load, POLL_INTERVAL_MS);
    };
    const stop = () => {
      if (timer !== null) {
        clearInterval(timer);
        timer = null;
      }
    };

    const onVisibility = () => {
      if (document.hidden) {
        stop();
      } else {
        load(); // catch up immediately on return
        start();
      }
    };

    if (!document.hidden) start();
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      stop();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [load]);

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return;

    const onPointerDown = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };

    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  const handleOpen = () => {
    setOpen((prev) => {
      if (!prev) load(); // freshen on open rather than showing a stale list
      return !prev;
    });
  };

  const handleMarkRead = async (id: string) => {
    // Optimistic: the request is idempotent and a failure only means the badge
    // corrects itself on the next poll.
    setItems((prev) =>
      prev.map((n) => (n.notification_id === id ? { ...n, is_read: true } : n)),
    );
    setUnread((n) => Math.max(0, n - 1));
    try {
      await markNotificationRead(id);
    } catch {
      load();
    }
  };

  const handleMarkAllRead = async () => {
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
    setUnread(0);
    try {
      await markAllNotificationsRead();
    } catch {
      load();
    }
  };

  const badge = unread > 9 ? '9+' : String(unread);

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <button
        onClick={handleOpen}
        className="relative p-2 rounded-lg hover:bg-accent transition"
        aria-label={
          unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'
        }
        aria-expanded={open}
        aria-haspopup="true"
      >
        <Bell className="w-5 h-5" />
        {unread > 0 && (
          <span
            className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 flex items-center
                       justify-center rounded-full bg-destructive text-destructive-foreground
                       text-[10px] font-semibold leading-none"
          >
            {badge}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Notifications"
          className="absolute right-0 mt-2 w-80 sm:w-96 max-h-[70vh] overflow-hidden z-50
                     bg-popover border border-border rounded-xl shadow-lg flex flex-col"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <div className="font-medium text-sm">Notifications</div>
            {unread > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="text-xs text-primary hover:underline flex items-center gap-1"
              >
                <Check className="w-3 h-3" />
                Mark all read
              </button>
            )}
          </div>

          <div className="overflow-y-auto">
            {isLoading && items.length === 0 && (
              <div className="flex items-center justify-center py-10 text-muted-foreground text-sm">
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                Loading…
              </div>
            )}

            {!isLoading && error && items.length === 0 && (
              <div className="px-4 py-10 text-center text-sm text-muted-foreground">
                Couldn&apos;t load notifications.
                <button onClick={load} className="block mx-auto mt-2 text-primary hover:underline">
                  Try again
                </button>
              </div>
            )}

            {!isLoading && !error && items.length === 0 && (
              <div className="px-4 py-10 text-center text-sm text-muted-foreground">
                You&apos;re all caught up.
              </div>
            )}

            {items.map((n) => (
              <button
                key={n.notification_id}
                onClick={() => !n.is_read && handleMarkRead(n.notification_id)}
                className={`w-full text-left px-4 py-3 border-b border-border last:border-0
                            hover:bg-accent/50 transition ${n.is_read ? 'opacity-60' : ''}`}
              >
                <div className="flex items-start gap-2">
                  {!n.is_read && (
                    <span
                      className="mt-1.5 w-2 h-2 rounded-full bg-primary flex-shrink-0"
                      aria-hidden="true"
                    />
                  )}
                  <div className={n.is_read ? 'pl-4' : ''}>
                    <div className="text-sm font-medium">{n.title}</div>
                    <div className="text-sm text-muted-foreground mt-0.5">{n.message}</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {timeAgo(n.created_at)}
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
