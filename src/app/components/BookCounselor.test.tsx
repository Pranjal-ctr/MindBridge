/**
 * Time-first booking flow.
 *
 * The cases worth pinning are the ones where the UI could lie to someone about
 * whether they have a session: an empty result must say so rather than render
 * an empty list, a lost race must correct itself instead of leaving a stale
 * slot on screen, and nothing may be booked without an explicit confirmation.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { BookCounselor } from './BookCounselor';

const getMock = vi.fn();
const postMock = vi.fn();

vi.mock('../../lib/api', () => ({
  default: {
    get: (...args: unknown[]) => getMock(...args),
    post: (...args: unknown[]) => postMock(...args),
  },
}));

let mockRole = 'student';
vi.mock('../../lib/auth-context', () => ({
  useAuth: () => ({ user: { role: mockRole, user_id: 'u1' } }),
}));

function slot(overrides: Record<string, unknown> = {}) {
  const start = new Date();
  start.setDate(start.getDate() + 1);
  start.setHours(18, 0, 0, 0);
  const end = new Date(start.getTime() + 30 * 60 * 1000);
  return {
    counselor_id: 'c1',
    counselor_name: 'Dana Counsel',
    start: start.toISOString(),
    end: end.toISOString(),
    duration_minutes: 30,
    display_start: '6:00 PM',
    display_end: '6:30 PM',
    display_date: '2027-01-05',
    ...overrides,
  };
}

function searchReturns(slots: unknown[]) {
  getMock.mockImplementation((url: string) => {
    if (url === '/counselors/availability/search') {
      return Promise.resolve({
        data: {
          timezone: 'Asia/Kolkata',
          window_start: new Date().toISOString(),
          window_end: new Date().toISOString(),
          slots,
          counselors_considered: slots.length,
        },
      });
    }
    return Promise.resolve({ data: { children: [] } });
  });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <BookCounselor />
    </MemoryRouter>,
  );
}

async function searchEvening(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: /Evening/i }));
}

describe('BookCounselor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRole = 'student';
  });

  it('asks for a time before showing any counselors', () => {
    searchReturns([]);
    renderPage();

    expect(screen.getByText(/Choose a date/i)).toBeInTheDocument();
    expect(screen.getByText(/Choose a time/i)).toBeInTheDocument();
    // Nothing is searched until a time window is chosen.
    expect(getMock).not.toHaveBeenCalledWith(
      '/counselors/availability/search',
      expect.anything(),
    );
  });

  it('shows real slots grouped by counselor after a search', async () => {
    const user = userEvent.setup();
    searchReturns([slot(), slot({ display_start: '6:30 PM', start: new Date(Date.now() + 90e6).toISOString() })]);
    renderPage();

    await searchEvening(user);

    await waitFor(() => expect(screen.getByText(/2 slots available/i)).toBeInTheDocument());
    expect(screen.getByText('Dana Counsel')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '6:00 PM' })).toBeInTheDocument();
  });

  it('says nobody is available rather than rendering an empty list', async () => {
    const user = userEvent.setup();
    searchReturns([]);
    renderPage();

    await searchEvening(user);

    await waitFor(() =>
      expect(
        screen.getByText(/No counselors are available during this time/i),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole('button', { name: /Try another time/i })).toBeInTheDocument();
  });

  it('requires an explicit confirmation before booking anything', async () => {
    const user = userEvent.setup();
    searchReturns([slot()]);
    renderPage();

    await searchEvening(user);
    await waitFor(() => screen.getByRole('button', { name: '6:00 PM' }));
    await user.click(screen.getByRole('button', { name: '6:00 PM' }));

    // Choosing a slot opens a confirmation step; it does not book.
    expect(screen.getByText(/Confirm your session/i)).toBeInTheDocument();
    expect(screen.getByText(/Nothing is booked until you confirm/i)).toBeInTheDocument();
    expect(postMock).not.toHaveBeenCalled();
  });

  it('books the selected slot and confirms', async () => {
    const user = userEvent.setup();
    const chosen = slot();
    searchReturns([chosen]);
    postMock.mockResolvedValue({
      data: {
        counselor_session_id: 's1',
        counselor_id: 'c1',
        counselor_name: 'Dana Counsel',
        scheduled_at: chosen.start,
        status: 'scheduled',
        message: 'Session booked',
      },
    });
    renderPage();

    await searchEvening(user);
    await waitFor(() => screen.getByRole('button', { name: '6:00 PM' }));
    await user.click(screen.getByRole('button', { name: '6:00 PM' }));
    await user.click(screen.getByRole('button', { name: /Confirm booking/i }));

    await waitFor(() => expect(screen.getByText(/Session booked/i)).toBeInTheDocument());
    expect(postMock).toHaveBeenCalledWith('/counselors/book', {
      counselor_id: 'c1',
      starts_at: chosen.start,
    });
  });

  it('recovers from losing the race and refreshes availability', async () => {
    const user = userEvent.setup();
    searchReturns([slot()]);
    postMock.mockRejectedValue({ response: { status: 409 } });
    renderPage();

    await searchEvening(user);
    await waitFor(() => screen.getByRole('button', { name: '6:00 PM' }));
    await user.click(screen.getByRole('button', { name: '6:00 PM' }));
    await user.click(screen.getByRole('button', { name: /Confirm booking/i }));

    await waitFor(() =>
      expect(screen.getByText(/That slot was just booked/i)).toBeInTheDocument(),
    );
    // Back on the search step with a re-run query, not stranded on a dead slot.
    expect(screen.queryByText(/Confirm your session/i)).not.toBeInTheDocument();
    const searches = getMock.mock.calls.filter(
      ([url]) => url === '/counselors/availability/search',
    );
    expect(searches.length).toBeGreaterThanOrEqual(2);
  });

  it('reports a failed search instead of showing nothing', async () => {
    const user = userEvent.setup();
    getMock.mockImplementation((url: string) => {
      if (url === '/counselors/availability/search') return Promise.reject(new Error('boom'));
      return Promise.resolve({ data: { children: [] } });
    });
    renderPage();

    await searchEvening(user);

    await waitFor(() =>
      expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument(),
    );
  });

  it('offers the earliest slot as a shortcut', async () => {
    const user = userEvent.setup();
    searchReturns([slot(), slot({ counselor_id: 'c2', counselor_name: 'Rae Listener' })]);
    renderPage();

    await searchEvening(user);

    await waitFor(() =>
      expect(screen.getByText(/Earliest: 6:00 PM with Dana Counsel/i)).toBeInTheDocument(),
    );
  });

  it('makes a parent pick which child the session is for', async () => {
    mockRole = 'parent';
    const user = userEvent.setup();
    const chosen = slot();
    getMock.mockImplementation((url: string) => {
      if (url === '/counselors/availability/search') {
        return Promise.resolve({
          data: {
            timezone: 'Asia/Kolkata',
            window_start: '',
            window_end: '',
            slots: [chosen],
            counselors_considered: 1,
          },
        });
      }
      return Promise.resolve({
        data: {
          children: [
            { link_id: 'l1', student_id: 'st1', first_name: 'Riya', last_name: 'Sharma' },
            { link_id: 'l2', student_id: 'st2', first_name: 'Arjun', last_name: 'Sharma' },
          ],
        },
      });
    });
    postMock.mockResolvedValue({
      data: {
        counselor_session_id: 's1',
        counselor_id: 'c1',
        counselor_name: 'Dana Counsel',
        scheduled_at: chosen.start,
        status: 'scheduled',
        message: 'Session booked',
      },
    });
    renderPage();

    await waitFor(() => screen.getByText(/Who is this for/i));
    await user.click(screen.getByRole('button', { name: 'Riya Sharma' }));
    await searchEvening(user);
    await waitFor(() => screen.getByRole('button', { name: '6:00 PM' }));
    await user.click(screen.getByRole('button', { name: '6:00 PM' }));
    await user.click(screen.getByRole('button', { name: /Confirm booking/i }));

    // The child id travels with the booking; the backend still verifies the link.
    await waitFor(() =>
      expect(postMock).toHaveBeenCalledWith('/counselors/book', {
        counselor_id: 'c1',
        starts_at: chosen.start,
        student_id: 'st1',
      }),
    );
  });
});
