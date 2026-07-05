/**
 * MindBridge Conversations Hook
 * Manages conversation list, active conversation, and message sending.
 */

import { useCallback, useEffect, useState } from 'react';
import api from '../lib/api';
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

      setIsSending(true);
      try {
        const { data } = await api.post<SendMessageResponse>(
          `/conversations/${conversationId}/messages`,
          payload
        );

        // Add both user message and AI response to state
        setMessages((prev) => [...prev, data.user_message, data.ai_message]);
        return data;
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
    sendMessage,
    refetch: fetchMessages,
  };
}
