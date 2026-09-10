/**
 * Top-level error boundary.
 *
 * A render error anywhere below this unmounts the whole tree and leaves a
 * blank white page. For most products that is an annoyance. Here the person
 * looking at it may have opened Kio because they are struggling, and a blank
 * screen tells them the thing they reached for is gone — with no way back and
 * nothing to report.
 *
 * So the fallback is calm, says only that something broke, and always offers a
 * way forward. It never shows a stack trace: students, parents and counselors
 * cannot act on one, and it leaks file paths and internal structure.
 */

import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  /** Overrides the default fallback. Used by tests and by nested boundaries. */
  fallback?: (props: { reset: () => void; reference: string | null }) => ReactNode;
}

interface State {
  hasError: boolean;
  reference: string | null;
}

/** Reports to Sentry when configured, and never throws while doing so. */
function report(error: Error, info: ErrorInfo): string | null {
  try {
    const sentry = (window as unknown as {
      Sentry?: {
        captureException?: (e: unknown, ctx?: unknown) => string | undefined;
      };
    }).Sentry;
    if (sentry?.captureException) {
      return (
        sentry.captureException(error, {
          contexts: { react: { componentStack: info.componentStack } },
        }) ?? null
      );
    }
  } catch {
    // Reporting must never be the reason a fallback fails to render.
  }
  return null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, reference: null };

  static getDerivedStateFromError(): Partial<State> {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Logged so it is visible in the browser console during development and in
    // any log drain that captures console output.
    console.error('Unhandled render error', error);
    const reference = report(error, info);
    if (reference) this.setState({ reference });
  }

  reset = (): void => {
    this.setState({ hasError: false, reference: null });
  };

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;

    if (this.props.fallback) {
      return this.props.fallback({ reset: this.reset, reference: this.state.reference });
    }

    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-6">
        <div className="w-full max-w-md bg-card border border-border rounded-xl p-8 text-center shadow-sm">
          <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
            {/* Inline, so the fallback cannot itself fail on a missing icon import. */}
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              aria-hidden="true"
              className="text-muted-foreground"
            >
              <circle cx="12" cy="12" r="10" />
              <path d="M12 8v4" />
              <path d="M12 16h.01" />
            </svg>
          </div>

          <h1 className="text-lg font-semibold mb-2">This page didn&apos;t load</h1>
          <p className="text-sm text-muted-foreground mb-6">
            Something went wrong on our side, not yours. Your information is safe.
          </p>

          <div className="flex flex-wrap gap-3 justify-center">
            <button
              type="button"
              onClick={this.reset}
              className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition"
            >
              Try again
            </button>
            <button
              type="button"
              onClick={() => window.location.assign('/')}
              className="px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-muted transition"
            >
              Go home
            </button>
          </div>

          {/* A reference only appears when reporting produced one, so nobody is
              asked to quote an id that leads nowhere. */}
          {this.state.reference && (
            <p className="mt-6 text-xs text-muted-foreground">
              Reference: <code className="font-mono">{this.state.reference}</code>
            </p>
          )}

          <p className="mt-6 text-xs text-muted-foreground">
            If you need to talk to someone right now, contact your school counselor or a
            local helpline.
          </p>
        </div>
      </div>
    );
  }
}
