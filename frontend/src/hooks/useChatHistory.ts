'use client';

import { useState, useEffect, useCallback } from 'react';
import type { ChatSession, Message } from '@/types/chat';

const STORAGE_KEY = 'oip-chat-history';

export function useChatHistory() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        // Convert date strings back to Date objects
        const sessionsWithDates = parsed.map((session: ChatSession) => ({
          ...session,
          createdAt: new Date(session.createdAt),
          updatedAt: new Date(session.updatedAt),
          messages: session.messages.map((msg: Message) => ({
            ...msg,
            timestamp: new Date(msg.timestamp),
          })),
        }));
        setSessions(sessionsWithDates);
      }
    } catch (error) {
      console.error('Failed to load chat history:', error);
    }
    setIsLoaded(true);
  }, []);

  // Save to localStorage when sessions change
  useEffect(() => {
    if (isLoaded) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
      } catch (error) {
        console.error('Failed to save chat history:', error);
      }
    }
  }, [sessions, isLoaded]);

  const saveSession = useCallback(
    (sessionId: string, messages: Message[]) => {
      setSessions((prev) => {
        const existingIndex = prev.findIndex((s) => s.id === sessionId);

        // Generate title from first user message
        const firstUserMessage = messages.find((m) => m.role === 'user');
        const title = firstUserMessage
          ? firstUserMessage.content.slice(0, 50) +
            (firstUserMessage.content.length > 50 ? '...' : '')
          : 'New Chat';

        const session: ChatSession = {
          id: sessionId,
          title,
          createdAt:
            existingIndex >= 0 ? prev[existingIndex].createdAt : new Date(),
          updatedAt: new Date(),
          messages,
        };

        if (existingIndex >= 0) {
          const updated = [...prev];
          updated[existingIndex] = session;
          return updated;
        }

        return [session, ...prev];
      });
    },
    []
  );

  const getSession = useCallback(
    (sessionId: string): ChatSession | undefined => {
      return sessions.find((s) => s.id === sessionId);
    },
    [sessions]
  );

  const deleteSession = useCallback((sessionId: string) => {
    setSessions((prev) => prev.filter((s) => s.id !== sessionId));
  }, []);

  const clearHistory = useCallback(() => {
    setSessions([]);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return {
    sessions,
    isLoaded,
    saveSession,
    getSession,
    deleteSession,
    clearHistory,
  };
}
