'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import type { Message, ChatSession, UserContext } from '@/types/chat';
import { sendStreamingMessage, createSession } from '@/lib/api';
import { API_CONFIG } from '@/config/api.config';

interface UseChatOptions {
  initialSessionId?: string;
  initialMessages?: Message[];
  onNewSession?: (sessionId: string) => void;
  userContext?: UserContext;
}

export function useChat(options: UseChatOptions = {}) {
  const [messages, setMessages] = useState<Message[]>(options.initialMessages || []);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string>(
    options.initialSessionId || uuidv4()
  );

  const abortControllerRef = useRef<AbortController | null>(null);
  const streamingMessageRef = useRef<string>('');

  // Use ref to always get the latest userContext value
  // This ensures sendMessage callback always has access to current context
  const userContextRef = useRef<UserContext | undefined>(options.userContext);

  // Keep the ref updated when userContext changes
  useEffect(() => {
    console.log('[useChat] userContext updated:', options.userContext);
    userContextRef.current = options.userContext;
  }, [options.userContext]);

  const initSession = useCallback(async () => {
    try {
      const { session_id } = await createSession();
      setSessionId(session_id);
      setMessages([]);
      options.onNewSession?.(session_id);
      return session_id;
    } catch (err) {
      console.error('Failed to create session:', err);
      // Generate client-side session ID as fallback
      const newSessionId = uuidv4();
      setSessionId(newSessionId);
      setMessages([]);
      options.onNewSession?.(newSessionId);
      return newSessionId;
    }
  }, [options]);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return;

      setError(null);

      // Add user message
      const userMessage: Message = {
        id: uuidv4(),
        role: 'user',
        content: content.trim(),
        timestamp: new Date(),
        status: 'sent',
      };

      // Add assistant message placeholder
      const assistantMessageId = uuidv4();
      const assistantMessage: Message = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        status: 'streaming',
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsLoading(true);
      setLoadingStatus('Analyzing your request...');
      streamingMessageRef.current = '';

      try {
        await sendStreamingMessage(
          content.trim(),
          sessionId,
          API_CONFIG.defaultUserId,
          // onChunk - replace content (each chunk is the full response)
          (text: string) => {
            streamingMessageRef.current = text;
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, content: text }
                  : msg
              )
            );
          },
          // onComplete
          () => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, status: 'sent' }
                  : msg
              )
            );
            setIsLoading(false);
            setLoadingStatus('');
          },
          // onError
          (error: Error) => {
            setError(error.message);
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? {
                      ...msg,
                      content: 'Sorry, an error occurred. Please try again.',
                      status: 'error',
                    }
                  : msg
              )
            );
            setIsLoading(false);
            setLoadingStatus('');
          },
          // userContext - use ref to get latest value
          userContextRef.current,
          // onStatus
          (status: string) => {
            setLoadingStatus(status);
          }
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        setIsLoading(false);
      }
    },
    [isLoading, sessionId]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    streamingMessageRef.current = '';
  }, []);

  const newChat = useCallback(async () => {
    clearMessages();
    return initSession();
  }, [clearMessages, initSession]);

  // Load messages for a specific session
  const loadSession = useCallback((newSessionId: string, sessionMessages: Message[]) => {
    setSessionId(newSessionId);
    setMessages(sessionMessages);
    streamingMessageRef.current = '';
    setError(null);
  }, []);

  return {
    messages,
    isLoading,
    loadingStatus,
    error,
    sessionId,
    sendMessage,
    clearMessages,
    newChat,
    initSession,
    loadSession,
  };
}
