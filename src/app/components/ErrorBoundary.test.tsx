/**
 * Error boundary.
 *
 * The failure being prevented is a blank white page. For someone who opened
 * Kio because they are struggling, that reads as the app being gone — so the
 * cases pinned here are that something calm renders, that it never contains a
 * stack trace, and that there is always a way forward.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ErrorBoundary } from './ErrorBoundary';

function Boom(): never {
  throw new Error('render exploded at /src/app/components/Secret.tsx:42');
}

describe('ErrorBoundary', () => {
  beforeEach(() => {
    // React logs the caught error itself; silence it so the run stays readable.
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete (window as unknown as { Sentry?: unknown }).Sentry;
  });

  it('renders children when nothing throws', () => {
    render(
      <ErrorBoundary>
        <p>All good</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText('All good')).toBeInTheDocument();
  });

  it('shows a calm fallback instead of a blank page', () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/This page didn't load/i)).toBeInTheDocument();
    expect(screen.getByText(/not yours/i)).toBeInTheDocument();
  });

  it('never exposes the error text or a stack trace', () => {
    const { container } = render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    const rendered = container.textContent ?? '';
    expect(rendered).not.toMatch(/render exploded/);
    expect(rendered).not.toMatch(/Secret\.tsx/);
    expect(rendered).not.toMatch(/at .*:\d+/);
  });

  it('always offers a way forward', () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByRole('button', { name: /Try again/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Go home/i })).toBeInTheDocument();
  });

  it('points to a human when the app itself cannot help', () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/school counselor or a local helpline/i)).toBeInTheDocument();
  });

  it('recovers when retried after the cause is gone', async () => {
    const user = userEvent.setup();
    let shouldThrow = true;

    function Flaky() {
      if (shouldThrow) throw new Error('transient');
      return <p>Recovered</p>;
    }

    render(
      <ErrorBoundary>
        <Flaky />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/This page didn't load/i)).toBeInTheDocument();

    shouldThrow = false;
    await user.click(screen.getByRole('button', { name: /Try again/i }));
    expect(screen.getByText('Recovered')).toBeInTheDocument();
  });

  it('reports to Sentry and shows the reference it returns', () => {
    const captureException = vi.fn().mockReturnValue('abc123ref');
    (window as unknown as { Sentry: unknown }).Sentry = { captureException };

    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );

    expect(captureException).toHaveBeenCalled();
    expect(screen.getByText(/abc123ref/)).toBeInTheDocument();
  });

  it('renders the fallback even when reporting throws', () => {
    (window as unknown as { Sentry: unknown }).Sentry = {
      captureException: () => {
        throw new Error('sentry is down');
      },
    };

    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/This page didn't load/i)).toBeInTheDocument();
  });

  it('shows no reference when reporting is not configured', () => {
    const { container } = render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    // Nobody should be asked to quote an id that leads nowhere.
    expect(container.textContent).not.toMatch(/Reference:/);
  });
});
