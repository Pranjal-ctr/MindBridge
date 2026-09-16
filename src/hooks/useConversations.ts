/**
 * Kio Conversations Hook
 * Manages conversation list, active conversation, and message sending.
 */

import { useCallback, useEffect, useState } from 'react';
import api, { AI_REQUEST_TIMEOUT_MS } from '../lib/api';
import { chatErrorMessage } from '../lib/chat-errors';
import type {
  ConversationListResponse,
  ConversationResponse,
  MessageCreate,
  MessageListResponse,
  MessageResponse,
  SendMessageResponse,
} from '../lib/types';

// ── Conversations List ────────────────────────────────────────────────

export function useConversations() {
  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConversations = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const { data } = await api.get<ConversationListResponse>('/conversations/', {
        params: { page: 1, page_size: 50 },
      });
      setConversations(data.conversations);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load conversations';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  const createConversation = useCallback(async (title?: string): Promise<ConversationResponse> => {
    const { data } = await api.post<ConversationResponse>('/conversations/', {
      title: title || null,
    });
    setConversations((prev) => [data, ...prev]);
    return data;
  }, []);

  const deleteConversation = useCallback(async (conversationId: string) => {
    await api.delete(`/conversations/${conversationId}`);
    setConversations((prev) =>
      prev.filter((c) => c.conversation_id !== conversationId)
    );
  }, []);

  return {
    conversations,
    isLoading,
    error,
    createConversation,
    deleteConversation,
    refetch: fetchConversations,
  };
}

// ── Messages for Active Conversation ──────────────────────────────────

export function useMessages(conversationId: string | null) {
  const [messages, setMessages] = useState<MessageResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Kept apart from `error`, which describes a failed *load*. A send failure
  // needs its own slot so retrying the send can clear it without hiding a
  // transcript that never arrived.
  const [sendError, setSendError] = useState<string | null>(null);

  const fetchMessages = useCallback(async () => {
    if (!conversationId) {
      setMessages([]);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      const { data } = await api.get<MessageListResponse>(
        `/conversations/${conversationId}/messages`,
        { params: { limit: 100 } }
      );
      setMessages(data.messages);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load messages';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [conversationId]);

  useEffect(() => {
    fetchMessages();
  }, [fetchMessages]);

  const sendMessage = useCallback(
    async (messageText: string): Promise<SendMessageResponse> => {
      if (!conversationId) {
        throw new Error('No active conversation');
      }

      const payload: MessageCreate = {
        message_text: messageText,
        sender_type: 'user',
      };

      // Show the user's message immediately (optimistic) so it's visible while
      // Comrade is thinking, instead of only appearing once the reply lands.
      const tempId = `temp-${Date.now()}`;
      const optimistic: MessageResponse = {
        message_id: tempId,
        conversation_id: conversationId,
        sender_type: 'user',
        sender_id: null,
        message_text: messageText,
        metadata: null,
        token_count: null,
        sentiment: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, optimistic]);

      setIsSending(true);
      setSendError(null);
      try {
        const { data } = await api.post<SendMessageResponse>(
          `/conversations/${conversationId}/messages`,
          payload,
          // Waits on the model: the global timeout would abort a reply the
          // server is still legitimately working on. See AI_REQUEST_TIMEOUT_MS.
          { timeout: AI_REQUEST_TIMEOUT_MS },
        );

        // Swap the optimistic bubble for the server's user message + AI reply.
        setMessages((prev) => [
          ...prev.filter((m) => m.message_id !== tempId),
          data.user_message,
          data.ai_message,
        ]);
        setSendError(null);
        return data;
      } catch (err) {
        // Roll back the optimistic bubble and say why. Without the message the
        // student watched their own words disappear with no explanation — the
        // worst thing this screen can do, and the reason the daily-limit 429
        // was never seen by anyone.
        setMessages((prev) => prev.filter((m) => m.message_id !== tempId));
        setSendError(chatErrorMessage(err));
        throw err;
      } finally {
        setIsSending(false);
      }
    },
    [conversationId]
  );

  return {
    messages,
    isLoading,
    isSending,
    error,
    sendError,
    clearSendError: useCallback(() => setSendError(null), []),
    sendMessage,
    refetch: fetchMessages,
  };
}
