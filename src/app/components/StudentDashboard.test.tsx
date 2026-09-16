/**
 * Comrade: what a student sees when a message fails to send.
 *
 * The defect this pins, found in the pre-pilot audit: `handleSendMessage`
 * caught the failure with a comment saying the hook handled it, and the hook
 * did set an error — which the screen never rendered. The optimistic bubble
 * was rolled back, the input had already been cleared, and the student's
 * message existed nowhere: not on screen, not in the box, not on the server.
 * The backend's daily-limit 429 had never been seen by a single user.
 *
 * So these tests assert the three things that were missing, from the student's
 * point of view rather than the component's: they are told, their words come
 * back, and they can try again.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AxiosError, AxiosHeaders } from 'axios';

import { StudentDashboard } from './StudentDashboard';

// ── Doubles ───────────────────────────────────────────────────────────
// Only what the screen needs to mount. The layout, onboarding wizard and
// check-in modal are separate surfaces with their own tests; standing them up
// here would test them again and hide what this file is about.

const getMock = vi.fn();
const postMock = vi.fn();
const deleteMock = vi.fn();

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../../lib/api')>('../../lib/api');
  return {
    ...actual,
    default: {
      get: (...args: unknown[]) => getMock(...args),
      post: (...args: unknown[]) => postMock(...args),
      delete: (...args: unknown[]) => deleteMock(...args),
      patch: vi.fn(),
      put: vi.fn(),
    },
  };
});

vi.mock('./student/StudentLayout', () => ({
  StudentLayout: ({ children, sidebar }: { children: React.ReactNode; sidebar?: React.ReactNode }) => (
    <div>
      {sidebar}
      {children}
    </div>
  ),
}));

vi.mock('./StudentOnboarding', () => ({
  StudentOnboarding: () => null,
}));

vi.mock('./DailyCheckinModal', () => ({
  DailyCheckinModal: () => null,
}));

vi.mock('../../hooks/useWellness', () => ({
  useWellnessScore: () => ({ score: null, isLoading: false, refetch: vi.fn() }),
}));

vi.mock('react-router-dom', () => ({
  useSearchParams: () => [new URLSearchParams(), vi.fn()],
  Link: ({ children }: { children: React.ReactNode }) => <a href="#">{children}</a>,
}));

const CONVERSATION_ID = 'c1';

function conversation() {
  return {
    conversation_id: CONVERSATION_ID,
    student_id: 's1',
    title: 'Maths stress',
    ai_generated_title: false,
    is_archived: false,
    total_messages: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

/** Route each GET the screen makes on mount. */
function routeGets() {
  getMock.mockImplementation((url: string) => {
    if (url.startsWith('/conversations/') && url.includes('/messages')) {
      return Promise.resolve({ data: { messages: [], total: 0 } });
    }
    if (url.startsWith('/conversations')) {
      return Promise.resolve({ data: { conversations: [conversation()], total: 1 } });
    }
    if (url.startsWith('/onboarding')) {
      return Promise.resolve({ data: { completed: true } });
    }
    if (url.includes('checkin')) {
      return Promise.resolve({ data: { checkin_required: false, checkin: null } });
    }
    return Promise.resolve({ data: {} });
  });
}

function httpError(status: number, detail?: string): AxiosError {
  const error = new AxiosError('Request failed');
  error.response = {
    status,
    statusText: '',
    data: detail ? { detail } : {},
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
  };
  return error;
}

async function typeAndSend(text: string) {
  const user = userEvent.setup();
  const input = await screen.findByLabelText(/message comrade/i);
  await user.type(input, text);
  await user.click(screen.getByRole('button', { name: /send message/i }));
  return { user, input };
}

describe('StudentDashboard — a failed send', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    routeGets();
  });

  it('tells the student it failed instead of silently dropping the message', async () => {
    postMock.mockRejectedValue(httpError(500));
    render(<StudentDashboard />);

    await typeAndSend('I have a maths test on Friday');

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/try again in a moment/i);
  });

  it("shows the backend's daily-limit wording, which no user could see before", async () => {
    const detail =
      'Daily message limit reached. Comrade will be ready to chat again tomorrow.';
    postMock.mockRejectedValue(httpError(429, detail));
    render(<StudentDashboard />);

    await typeAndSend('one more thing');

    expect(await screen.findByRole('alert')).toHaveTextContent(detail);
  });

  it('puts the message back in the box so it is not lost', async () => {
    postMock.mockRejectedValue(httpError(500));
    render(<StudentDashboard />);

    const { input } = await typeAndSend('something hard to say');

    await waitFor(() => expect(input).toHaveValue('something hard to say'));
  });

  it('offers a retry that resends the same message', async () => {
    postMock.mockRejectedValue(httpError(500));
    render(<StudentDashboard />);

    const { user } = await typeAndSend('please work');
    await screen.findByRole('alert');

    const sendsAfterFirstFailure = postMock.mock.calls.length;
    await user.click(screen.getByRole('button', { name: /try again/i }));

    await waitFor(() =>
      expect(postMock.mock.calls.length).toBeGreaterThan(sendsAfterFirstFailure),
    );
  });

  it('clears the message once a retry succeeds', async () => {
    postMock.mockRejectedValueOnce(httpError(500)).mockResolvedValueOnce({
      data: {
        user_message: {
          message_id: 'm1',
          conversation_id: CONVERSATION_ID,
          sender_type: 'user',
          sender_id: null,
          message_text: 'please work',
          metadata: null,
          token_count: null,
          sentiment: null,
          created_at: new Date().toISOString(),
        },
        ai_message: {
          message_id: 'm2',
          conversation_id: CONVERSATION_ID,
          sender_type: 'ai',
          sender_id: null,
          message_text: 'I hear you.',
          metadata: null,
          token_count: null,
          sentiment: null,
          created_at: new Date().toISOString(),
        },
      },
    });
    render(<StudentDashboard />);

    const { user, input } = await typeAndSend('please work');
    await screen.findByRole('alert');
    await user.click(screen.getByRole('button', { name: /try again/i }));

    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull());
    await waitFor(() => expect(input).toHaveValue(''));
  });

  it('shows nothing alarming when a send succeeds', async () => {
    postMock.mockResolvedValue({
      data: {
        user_message: {
          message_id: 'm1',
          conversation_id: CONVERSATION_ID,
          sender_type: 'user',
          sender_id: null,
          message_text: 'hello',
          metadata: null,
          token_count: null,
          sentiment: null,
          created_at: new Date().toISOString(),
        },
        ai_message: {
          message_id: 'm2',
          conversation_id: CONVERSATION_ID,
          sender_type: 'ai',
          sender_id: null,
          message_text: 'Hi.',
          metadata: null,
          token_count: null,
          sentiment: null,
          created_at: new Date().toISOString(),
        },
      },
    });
    render(<StudentDashboard />);

    await typeAndSend('hello');

    await waitFor(() => expect(postMock).toHaveBeenCalled());
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('gives a chat send the long AI timeout, not the global one', async () => {
    postMock.mockResolvedValue({
      data: {
        user_message: {
          message_id: 'm1',
          conversation_id: CONVERSATION_ID,
          sender_type: 'user',
          sender_id: null,
          message_text: 'hi',
          metadata: null,
          token_count: null,
          sentiment: null,
          created_at: new Date().toISOString(),
        },
        ai_message: {
          message_id: 'm2',
          conversation_id: CONVERSATION_ID,
          sender_type: 'ai',
          sender_id: null,
          message_text: 'Hello.',
          metadata: null,
          token_count: null,
          sentiment: null,
          created_at: new Date().toISOString(),
        },
      },
    });
    render(<StudentDashboard />);

    await typeAndSend('hi');

    await waitFor(() => expect(postMock).toHaveBeenCalled());
    const messageSend = postMock.mock.calls.find(([url]) =>
      String(url).includes('/messages'),
    );
    expect(messageSend?.[2]?.timeout).toBeGreaterThanOrEqual(90_000);
  });
});
