/**
 * Journal — the student's private space.
 *
 * The API for this (`POST`/`GET /wellness/journal`) has existed since the
 * wellness module shipped and had no client at all; the sidebar link was
 * `href="#"`. This is the first screen to use it.
 *
 * Deliberately the plainest surface in the product. A journal competes with a
 * paper notebook, and every control added is a reason to close the tab — so
 * there is one text area, one button, and a quiet list of what came before.
 * Mood is not asked for here: the check-in already records it, and asking
 * twice would turn writing into another form to complete.
 */

import { useCallback, useEffect, useState } from 'react';
import { Loader2, NotebookPen } from 'lucide-react';
import { StudentLayout } from './StudentLayout';
import api from '../../../lib/api';
import type { JournalEntryResponse, JournalListResponse } from '../../../lib/types';

function entryDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });
}

function entryTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  });
}

export function StudentJournal() {
  const [entries, setEntries] = useState<JournalEntryResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const [content, setContent] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [justSaved, setJustSaved] = useState(false);

  const fetchEntries = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data } = await api.get<JournalListResponse>('/wellness/journal');
      setEntries(data.entries);
      setLoadError(false);
    } catch {
      setLoadError(true);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  const handleSave = async () => {
    const text = content.trim();
    if (!text || isSaving) return;

    setIsSaving(true);
    setSaveError(null);
    try {
      const { data } = await api.post<JournalEntryResponse>('/wellness/journal', {
        content: text,
      });
      // Prepend rather than refetch: the entry is already in hand, and the
      // list is newest-first, so a round trip would only add latency to the
      // one moment the student is waiting.
      setEntries((prev) => [data, ...prev]);
      setContent('');
      setJustSaved(true);
      setTimeout(() => setJustSaved(false), 2500);
    } catch {
      // The draft is deliberately left in the box. Losing what someone just
      // wrote because a request failed is the worst thing this screen could do.
      setSaveError("We couldn't save that just now. Your writing is still here — try again.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <StudentLayout>
      <header className="pt-2">
        <h1 className="font-heading text-2xl font-semibold tracking-tight text-primary sm:text-3xl">
          Your journal
        </h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          A private space for your thoughts. Only you can read what you write here.
        </p>
      </header>

      {/* ── Write ──────────────────────────────────────────────────── */}
      <section className="mt-6" aria-labelledby="write-heading">
        <h2 id="write-heading" className="sr-only">
          Write a new entry
        </h2>
        <div className="rounded-2xl border border-border/60 bg-card p-5 sm:p-6">
          <label htmlFor="journal-entry" className="sr-only">
            What's on your mind?
          </label>
          <textarea
            id="journal-entry"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={6}
            placeholder="What's on your mind today?"
            className="w-full resize-y rounded-xl border-0 bg-transparent p-0 text-base leading-relaxed placeholder:text-muted-foreground/70 focus:outline-none focus:ring-0"
          />

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border/50 pt-4">
            <p aria-live="polite" className="text-sm">
              {saveError ? (
                <span className="text-destructive">{saveError}</span>
              ) : justSaved ? (
                <span className="text-teal-600">Saved.</span>
              ) : (
                <span className="text-muted-foreground">
                  Nothing here is shared with your parents or school.
                </span>
              )}
            </p>
            <button
              type="button"
              onClick={handleSave}
              disabled={!content.trim() || isSaving}
              className="inline-flex items-center gap-2 rounded-xl bg-secondary px-4 py-2 text-sm font-medium text-white transition hover:bg-secondary/90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {isSaving && <Loader2 className="h-4 w-4 motion-safe:animate-spin" />}
              {isSaving ? 'Saving…' : 'Save entry'}
            </button>
          </div>
        </div>
      </section>

      {/* ── Past entries ───────────────────────────────────────────── */}
      <section className="mt-10" aria-labelledby="entries-heading">
        <h2 id="entries-heading" className="text-lg font-medium">
          Earlier entries
        </h2>

        {isLoading ? (
          <div className="mt-4 space-y-3">
            {[0, 1].map((i) => (
              <div key={i} className="rounded-2xl border border-border/60 bg-card p-5">
                <div className="h-3 w-40 rounded bg-muted motion-safe:animate-pulse" />
                <div className="mt-3 h-3 w-full rounded bg-muted motion-safe:animate-pulse" />
                <div className="mt-2 h-3 w-2/3 rounded bg-muted motion-safe:animate-pulse" />
              </div>
            ))}
          </div>
        ) : loadError ? (
          <div className="mt-4 rounded-2xl border border-border/60 bg-card p-6 text-center">
            <p className="text-sm text-muted-foreground">
              We couldn't load your earlier entries.
            </p>
            <button
              type="button"
              onClick={fetchEntries}
              className="mt-3 rounded-full bg-secondary/10 px-4 py-2 text-sm font-medium text-secondary transition hover:bg-secondary/15"
            >
              Try again
            </button>
          </div>
        ) : entries.length === 0 ? (
          <div className="mt-4 rounded-2xl border border-dashed border-border bg-card/50 p-8 text-center">
            <NotebookPen
              className="mx-auto h-6 w-6 text-muted-foreground/60"
              strokeWidth={1.5}
              aria-hidden="true"
            />
            <p className="mt-3 text-sm text-muted-foreground">
              Nothing here yet. Whatever you write stays private.
            </p>
          </div>
        ) : (
          <ol className="mt-4 space-y-3">
            {entries.map((entry) => (
              <li
                key={entry.journal_id}
                className="rounded-2xl border border-border/60 bg-card p-5"
              >
                <p className="text-xs text-muted-foreground">
                  {entryDate(entry.created_at)} · {entryTime(entry.created_at)}
                </p>
                {entry.title && (
                  <h3 className="mt-1.5 font-medium text-primary">{entry.title}</h3>
                )}
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
                  {entry.content}
                </p>
              </li>
            ))}
          </ol>
        )}
      </section>
    </StudentLayout>
  );
}
