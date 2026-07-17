/**
 * Mood check-in modal: 5-point scale with required fields gating submit,
 * the payload matches the API contract, update mode is dismissible, and an
 * exhausted window (409) unblocks the dashboard instead of trapping the student.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DailyCheckinModal } from './DailyCheckinModal';

const postMock = vi.fn();
vi.mock('../../lib/api', () => ({
  default: { post: (...args: unknown[]) => postMock(...args) },
}));

describe('DailyCheckinModal', () => {
  beforeEach(() => {
    postMock.mockReset();
  });

  it('renders the 5-point mood scale and all ten reasons', () => {
    render(<DailyCheckinModal onComplete={() => {}} />);
    for (const label of ['Very Happy', 'Happy', 'Neutral', 'Sad', 'Very Low']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    for (const label of [
      'Academics', 'Family', 'Friends', 'Relationship', 'Health',
      'Career', 'Sports', 'Financial', 'Social Media', 'Other',
    ]) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument();
    }
  });

  it('keeps submit disabled until both mood and reason are chosen', async () => {
    const user = userEvent.setup();
    render(<DailyCheckinModal onComplete={() => {}} />);
    const submit = screen.getByRole('button', { name: /complete check-in/i });

    expect(submit).toBeDisabled();

    await user.click(screen.getByText('Happy'));
    expect(submit).toBeDisabled(); // mood alone is not enough

    await user.click(screen.getByRole('button', { name: 'Academics' }));
    expect(submit).toBeEnabled();
  });

  it('submits the check-in payload and calls onComplete', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup();
    const onComplete = vi.fn();
    postMock.mockResolvedValue({ data: {} });

    render(<DailyCheckinModal onComplete={onComplete} />);
    await user.click(screen.getByText('Sad'));
    await user.click(screen.getByRole('button', { name: 'Family' }));
    await user.type(
      screen.getByPlaceholderText(/a sentence or two/i),
      'Rough morning.'
    );
    await user.click(screen.getByRole('button', { name: /complete check-in/i }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith('/wellness/checkin', {
        mood: 'low',
        reason: 'family',
        reflection: 'Rough morning.',
      });
    });

    // Success state, then the dashboard unblocks
    expect(await screen.findByText(/thanks for checking in/i)).toBeInTheDocument();
    vi.advanceTimersByTime(1500);
    expect(onComplete).toHaveBeenCalled();
    vi.useRealTimers();
  });

  it('sends null reflection when the field is left empty', async () => {
    const user = userEvent.setup();
    postMock.mockResolvedValue({ data: {} });

    render(<DailyCheckinModal onComplete={() => {}} />);
    await user.click(screen.getByText('Neutral'));
    await user.click(screen.getByRole('button', { name: 'Sports' }));
    await user.click(screen.getByRole('button', { name: /complete check-in/i }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith('/wellness/checkin', {
        mood: 'okay',
        reason: 'sports',
        reflection: null,
      });
    });
  });

  it('treats an exhausted window (409) as done instead of blocking', async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    postMock.mockRejectedValue({ response: { status: 409 } });

    render(<DailyCheckinModal onComplete={onComplete} />);
    await user.click(screen.getByText('Happy'));
    await user.click(screen.getByRole('button', { name: 'Other' }));
    await user.click(screen.getByRole('button', { name: /complete check-in/i }));

    await waitFor(() => expect(onComplete).toHaveBeenCalled());
  });

  it('shows an error and stays open on server failure', async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    postMock.mockRejectedValue({ response: { status: 500 } });

    render(<DailyCheckinModal onComplete={onComplete} />);
    await user.click(screen.getByText('Happy'));
    await user.click(screen.getByRole('button', { name: 'Health' }));
    await user.click(screen.getByRole('button', { name: /complete check-in/i }));

    expect(await screen.findByText(/could not save/i)).toBeInTheDocument();
    expect(onComplete).not.toHaveBeenCalled();
  });

  it('update mode has its own copy, an update button, and a close control', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<DailyCheckinModal mode="update" onClose={onClose} onComplete={() => {}} />);

    expect(screen.getByText(/update your mood/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /update mood/i })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /close/i }));
    expect(onClose).toHaveBeenCalled();
  });
});
