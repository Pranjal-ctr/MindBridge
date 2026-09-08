/**
 * Shared chrome for the Terms and Privacy pages.
 *
 * Public routes — reachable signed out, because signup links to them before an
 * account exists.
 */

import type { ReactNode } from 'react';
import { ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';
import { KioLogo } from '../KioLogo';

export function PolicyLayout({
  title,
  version,
  children,
}: {
  title: string;
  version: string;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-4">
          <Link to="/">
            <KioLogo className="h-7 w-auto" />
          </Link>
          <Link
            to="/"
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1
          className="text-3xl font-semibold tracking-tight"
          style={{ fontFamily: 'var(--font-heading)' }}
        >
          {title}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">Version {version}</p>

        {/*
          This banner is not decoration. These documents are engineering drafts
          describing what the software actually does; they have not been
          reviewed by a lawyer and are not sufficient for launch. Removing the
          banner should be the last step after that review, not the first.
        */}
        <div className="mt-6 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          <strong className="block">Draft — pending legal review</strong>
          This document describes how Kio currently handles data, written by the
          engineering team. It has not been reviewed by a qualified lawyer and must
          not be relied on as a final legal agreement.
        </div>

        <div className="prose-kio mt-8 space-y-6 text-sm leading-relaxed">{children}</div>
      </main>
    </div>
  );
}

/** Section heading + body, so both documents read consistently. */
export function Section({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold text-foreground">{heading}</h2>
      <div className="space-y-2 text-muted-foreground">{children}</div>
    </section>
  );
}
