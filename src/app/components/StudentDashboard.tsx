/**
 * Comrade — the chat surface, at `/student/comrade`.
 *
 * This file used to be the whole student experience: sidebar, wellness cards,
 * mood card and chat in one 500-line component mounted at `/student`. It now
 * does one thing. The shell moved to StudentLayout, the wellness score moved
 * to Growth, and the mood card moved to Home.
 *
 * What did NOT change: the onboarding gate, the mandatory check-in that runs
 * before the app is usable, conversation history, New Chat, delete, the
 * typewriter reveal on the freshest reply, the suggested prompts, and the
 * privacy note under the composer.
 *
 * `?c=<conversation_id>` opens a specific conversation, which is how Home's
 * "Continue where you left off" and the sidebar's Recent Chats link in.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Loader2, Send, X } from 'lucide-react';
import { KioMascot } from './KioMascot';
import { StudentLayout } from './student/StudentLayout';
import { ConversationSidebar } from './student/ConversationSidebar';
import { useConversations, useMessages } from '../../hooks/useConversations';
import { useWellnessScore } from '../../hooks/useWellness';
import { StudentOnboarding } from './StudentOnboarding';
import { DailyCheckinModal } from './DailyCheckinModal';
import { ChatMessage } from './ChatMessage';
import { Disclaimer } from './Disclaimer';
import api from '../../lib/api';
import type { DailyCheckinStatusResponse, OnboardingResponse } from '../../lib/types';

const SUGGESTED_PROMPTS = [
  'I feel stressed before exams',
  'I feel lonely',
  'How can I improve my confidence?',
  'Help me make a study plan',
];

export function StudentDashboard() {
  const {
    conversations,
    isLoading: convsLoading,
    createConversation,
    deleteConversation,
    refetch: refetchConversations,
  } = useConversations();

  const [searchParams, setSearchParams] = useSearchParams();

  // First-login onboarding: show the wizard once until completed
  const [showOnboarding, setShowOnboarding] = useState(false);
  useEffect(() => {
    let cancelled = false;
    api
      .get<OnboardingResponse | null>('/onboarding/')
      .then((res) => {
        if (!cancelled && !res.data) setShowOnboarding(true);
      })
      .catch(() => {
        /* non-fatal: skip onboarding gate on error */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Mandatory mood check-in. Unchanged: it gates the app until this window's
  // check-in exists, and records a reason as well as a mood because the
  // wellness engine and parent insights both depend on it.
  const [showCheckin, setShowCheckin] = useState(false);

  const fetchCheckinStatus = useCallback(async () => {
    try {
      const { data } = await api.get<DailyCheckinStatusResponse>('/wellness/checkin/today');
      setShowCheckin(!data.completed_today);
    } catch {
      /* non-fatal: skip the gate if the status check fails */
    }
  }, []);

  useEffect(() => {
    fetchCheckinStatus();
  }, [fetchCheckinStatus]);

  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const {
    messages,
    isLoading: msgsLoading,
    isSending,
    sendError,
    clearSendError,
    sendMessage,
  } = useMessages(activeConversationId);
  const { refetch: refetchWellness } = useWellnessScore();

  const [messageInput, setMessageInput] = useState('');
  const [chatListOpen, setChatListOpen] = useState(false);
  // Message id of the freshest AI reply — the only one that types itself out.
  const [typingId, setTypingId] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const scrollToEnd = useCallback(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  // Open the conversation named in the URL, else fall back to the most recent.
  // Landing on the newest chat is fine *here* — this is the chat screen. It is
  // Home that login now opens, which is what stops Kio dropping a student
  // straight back into their last conversation before they have said hello.
  useEffect(() => {
    if (activeConversationId || conversations.length === 0) return;
    const requested = searchParams.get('c');
    const match = requested
      ? conversations.find((c) => c.conversation_id === requested)
      : undefined;
    setActiveConversationId(match?.conversation_id ?? conversations[0].conversation_id);
  }, [conversations, activeConversationId, searchParams]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const selectConversation = (id: string) => {
    setActiveConversationId(id);
    setChatListOpen(false);
    // Keep the URL shareable/reloadable without stacking history entries.
    setSearchParams({ c: id }, { replace: true });
  };

  const handleSendMessage = async () => {
    const text = messageInput.trim();
    if (!text || isSending) return;

    let convId = activeConversationId;
    if (!convId) {
      try {
        const newConv = await createConversation(text.slice(0, 50));
        convId = newConv.conversation_id;
        setActiveConversationId(convId);
      } catch {
        return;
      }
    }

    setMessageInput('');

    try {
      const data = await sendMessage(text);
      setTypingId(data.ai_message.message_id);
      refetchConversations();
      // The intelligence pipeline runs as a background task after the chat
      // response returns, so give it a moment before pulling the updated score.
      setTimeout(() => refetchWellness(), 8000);
    } catch {
      // Put the message back in the box. The hook has already rolled the
      // optimistic bubble out of the transcript and set `sendError`, so
      // without this the student's words would exist nowhere at all — which
      // is exactly what used to happen.
      setMessageInput((current) => (current.trim() ? current : text));
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleNewConversation = async () => {
    try {
      const newConv = await createConversation();
      selectConversation(newConv.conversation_id);
    } catch {
      // Error handled by hook
    }
  };

  const handleDeleteConversation = async (convId: string) => {
    await deleteConversation(convId);
    if (activeConversationId === convId) setActiveConversationId(null);
  };

  const activeConversation = conversations.find(
    (c) => c.conversation_id === activeConversationId,
  );

  const conversationList = (variant: 'rail' | 'panel') => (
    <ConversationSidebar
      variant={variant}
      conversations={conversations}
      activeConversationId={activeConversationId}
      isLoading={convsLoading}
      onSelect={selectConversation}
      onNew={handleNewConversation}
      onDelete={handleDeleteConversation}
    />
  );

  return (
    <StudentLayout
      variant="full"
      // Comrade's rail replaces the student navigation rather than sitting
      // beside it; `Back to Kio` at its top is the way out.
      sidebar={conversationList('rail')}
      headerRight={
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setChatListOpen(true)}
            className="rounded-full px-3 py-1.5 text-sm text-muted-foreground transition hover:bg-muted/60 hover:text-foreground md:hidden"
          >
            Chats
          </button>
          <span className="hidden text-xs text-muted-foreground sm:inline sm:text-sm">
            Safe &amp; Private
          </span>
        </div>
      }
    >
      {showOnboarding && <StudentOnboarding onComplete={() => setShowOnboarding(false)} />}
      {!showOnboarding && showCheckin && (
        <DailyCheckinModal
          onComplete={() => {
            setShowCheckin(false);
            fetchCheckinStatus();
            refetchWellness();
          }}
        />
      )}

      <div className="flex min-h-0 flex-1">
        {/* ── Conversation panel (phone) ───────────────────────────
            The rail itself is the shell's sidebar at md and up; this is the
            same list in a drawer for widths that have no room for one. */}
        {chatListOpen && (
          <div className="fixed inset-0 z-40 md:hidden">
            <div
              className="absolute inset-0 bg-black/40"
              onClick={() => setChatListOpen(false)}
              aria-hidden="true"
            />
            <div className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col bg-card p-3 shadow-xl">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-medium">Your chats</span>
                <button
                  type="button"
                  onClick={() => setChatListOpen(false)}
                  aria-label="Close chat list"
                  className="rounded-lg p-1.5 transition hover:bg-muted"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              {conversationList('panel')}
            </div>
          </div>
        )}

        {/* ── Transcript ───────────────────────────────────────────── */}
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="border-b border-border/60 px-4 py-3 md:px-6">
            <h1 className="truncate font-heading text-base font-semibold text-primary">
              {activeConversation?.title || 'Talk to Comrade'}
            </h1>
          </div>

          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4 md:p-6">
            {msgsLoading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="h-6 w-6 motion-safe:animate-spin text-muted-foreground" />
              </div>
            ) : messages.length === 0 ? (
              <>
                <div className="flex flex-col items-center py-6 text-center">
                  <KioMascot size={104} state="responding" />
                  <p className="mt-4 max-w-sm text-foreground">
                    Hey! I'm <strong>Comrade</strong>, your trusted companion here on
                    Kio. How are you feeling today?
                  </p>
                </div>
                <div className="space-y-3">
                  <p className="text-center text-sm text-muted-foreground">
                    Try asking about:
                  </p>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    {SUGGESTED_PROMPTS.map((prompt) => (
                      <button
                        key={prompt}
                        type="button"
                        onClick={() => setMessageInput(prompt)}
                        className="rounded-xl border border-border/60 bg-card px-4 py-3 text-left text-sm transition hover:border-border hover:bg-muted/50"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              messages.map((msg) => (
                <ChatMessage
                  key={msg.message_id}
                  message={msg}
                  typewriter={msg.message_id === typingId}
                  onGrow={scrollToEnd}
                />
              ))
            )}

            {isSending && (
              <div className="flex justify-start">
                <KioMascot
                  size={32}
                  state="thinking"
                  withParticles={false}
                  className="mr-2 mt-0.5"
                  label="Comrade is thinking"
                />
                <div className="flex max-w-[80%] items-center rounded-2xl bg-muted px-4 py-3 text-muted-foreground md:max-w-[70%]">
                  <span className="text-sm font-medium">Comrade is thinking…</span>
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* ── Composer ───────────────────────────────────────────── */}
          <div className="border-t border-border/60 bg-card p-4 md:p-6">
            {/* A failed send is announced, not swallowed. `assertive` because
                the transcript has just changed underneath a screen-reader user
                — their message was removed and nothing replaced it. */}
            {sendError && (
              <div
                role="alert"
                aria-live="assertive"
                className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-xl bg-destructive/[0.07] px-4 py-3 text-sm text-destructive"
              >
                <span className="min-w-0 flex-1">{sendError}</span>
                <button
                  type="button"
                  onClick={() => {
                    clearSendError();
                    handleSendMessage();
                  }}
                  disabled={!messageInput.trim() || isSending}
                  className="shrink-0 rounded-lg px-2.5 py-1 font-medium underline-offset-2 transition hover:bg-destructive/10 hover:underline disabled:opacity-50"
                >
                  Try again
                </button>
              </div>
            )}
            <div className="flex gap-3">
              <label htmlFor="chat-input" className="sr-only">
                Message Comrade
              </label>
              <input
                id="chat-input"
                type="text"
                value={messageInput}
                onChange={(e) => setMessageInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Share what's on your mind... This is a safe space."
                className="flex-1 rounded-xl border border-border bg-input-background px-4 py-3 focus:outline-none focus:ring-2 focus:ring-ring"
                disabled={isSending}
              />
              <button
                type="button"
                onClick={handleSendMessage}
                disabled={!messageInput.trim() || isSending}
                aria-label="Send message"
                className="rounded-xl bg-primary px-6 py-3 text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Send className="h-5 w-5" />
              </button>
            </div>
            <p className="mt-3 text-center text-xs text-muted-foreground">
              Your conversations are private and encrypted. Parents receive insights, not
              raw chats.
            </p>
            <Disclaimer variant="short" className="mt-2 justify-center text-center" />
          </div>
        </div>
      </div>
    </StudentLayout>
  );
}
