/**
 * Comrade's rail — the sidebar that replaces the student navigation while a
 * conversation is open.
 *
 * It used to render *inside* the chat content, beside the global nav, so at
 * desktop width Comrade showed two sidebars competing for the same job. It is
 * now passed to `StudentLayout` as the single sidebar's contents, which is why
 * it carries the way back to Kio at the top: taking the nav away leaves a
 * student in a room with no door, and on desktop the mobile bottom bar is not
 * there to be one.
 *
 * The same component fills the phone drawer (`variant="panel"`), where the
 * drawer has its own header and the bottom bar is already the way out — so the
 * Kio header is dropped rather than duplicated.
 */

import { Link } from 'react-router-dom';
import { ArrowLeft, Loader2, MessageSquare, Plus, Trash2 } from 'lucide-react';
import { KioLogo } from '../KioLogo';
import type { ConversationResponse } from '../../../lib/types';

interface ConversationSidebarProps {
  conversations: ConversationResponse[];
  activeConversationId: string | null;
  isLoading: boolean;
  onSelect: (conversationId: string) => void;
  onNew: () => void;
  onDelete: (conversationId: string) => void;
  /** 'rail' is the desktop sidebar; 'panel' is the phone drawer. */
  variant?: 'rail' | 'panel';
}

export function ConversationSidebar({
  conversations,
  activeConversationId,
  isLoading,
  onSelect,
  onNew,
  onDelete,
  variant = 'rail',
}: ConversationSidebarProps) {
  return (
    <>
      {variant === 'rail' && (
        <div className="border-b border-border/60 px-4 pt-6 pb-4">
          <Link to="/student" aria-label="Kio home">
            <KioLogo className="h-7 w-auto" />
          </Link>
          {/* A real control, not a breadcrumb. Taking the student navigation
              away for the chat makes this the only way back on desktop, and as
              a line of small grey text it was easy to miss entirely. It is a
              full-width row with a ~42px hit area and a surface of its own —
              but a tinted one, so it stays a step below the filled New Chat
              button rather than competing with it. */}
          <Link
            to="/student"
            className="mt-3 flex w-full items-center gap-2 rounded-xl border border-border/60 bg-muted/40 px-3 py-3 text-sm font-medium text-foreground transition hover:border-border hover:bg-muted"
          >
            <ArrowLeft className="h-4 w-4 shrink-0" strokeWidth={2} aria-hidden="true" />
            Back to Home
          </Link>
        </div>
      )}

      <div className={variant === 'rail' ? 'px-3 pt-3' : ''}>
        <button
          type="button"
          onClick={onNew}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" strokeWidth={2} aria-hidden="true" />
          New Chat
        </button>
      </div>

      <div
        className={`mt-3 min-h-0 flex-1 space-y-0.5 overflow-y-auto ${
          variant === 'rail' ? 'px-3 pb-4' : ''
        }`}
      >
        {isLoading ? (
          <div className="flex justify-center py-8">
            <Loader2
              className="h-5 w-5 text-muted-foreground motion-safe:animate-spin"
              aria-hidden="true"
            />
            <span className="sr-only">Loading your conversations</span>
          </div>
        ) : conversations.length === 0 ? (
          <p className="px-2 py-6 text-center text-sm text-muted-foreground">
            No conversations yet.
          </p>
        ) : (
          conversations.map((conv) => {
            const active = conv.conversation_id === activeConversationId;
            return (
              <div
                key={conv.conversation_id}
                className={`group flex items-center rounded-xl transition ${
                  active ? 'bg-secondary/10 text-secondary' : 'hover:bg-muted/60'
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelect(conv.conversation_id)}
                  aria-current={active ? 'true' : undefined}
                  className="flex min-w-0 flex-1 items-center gap-2.5 px-3 py-2 text-left"
                >
                  <MessageSquare className="h-4 w-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
                  <span className="truncate text-sm">{conv.title || 'New Conversation'}</span>
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(conv.conversation_id)}
                  aria-label={`Delete ${conv.title || 'conversation'}`}
                  className="mr-1 rounded-lg p-1.5 text-muted-foreground opacity-0 transition hover:bg-destructive/10 hover:text-destructive focus-visible:opacity-100 group-hover:opacity-100"
                >
                  <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden="true" />
                </button>
              </div>
            );
          })
        )}
      </div>
    </>
  );
}
