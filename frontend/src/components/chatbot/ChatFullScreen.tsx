'use client';

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ChatSidebar } from './ChatSidebar';
import { ChatHeader } from './ChatHeader';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';
import { useChat } from '@/hooks/useChat';
import { useChatHistory } from '@/hooks/useChatHistory';
import { useUser } from '@/contexts/UserContext';

export function ChatFullScreen() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const searchParams = useSearchParams();
  const router = useRouter();
  const urlSessionId = searchParams.get('session');

  // Get user context
  const { username, roleName, roleCode, projectCode, team, isLoggedIn, isLoaded: userLoaded } = useUser();

  // Redirect to login if not logged in (wait for context to load first)
  useEffect(() => {
    if (userLoaded && !isLoggedIn) {
      router.push('/login');
    }
  }, [userLoaded, isLoggedIn, router]);

  const { sessions, saveSession, getSession, deleteSession, isLoaded } =
    useChatHistory();

  const {
    messages,
    isLoading,
    error,
    sessionId,
    sendMessage,
    newChat,
    clearMessages,
    loadSession,
  } = useChat({
    onNewSession: (newSessionId) => {
      // Update URL when new session is created
      router.push(`/chat?session=${newSessionId}`, { scroll: false });
    },
    userContext: {
      username,
      userRole: roleName,
      userRoleCode: roleCode,
      projectCode,
      team,
    },
  });

  // Load session from URL when component mounts or URL changes
  useEffect(() => {
    if (isLoaded && urlSessionId) {
      const session = getSession(urlSessionId);
      if (session && session.id !== sessionId) {
        loadSession(session.id, session.messages);
      } else if (!session && urlSessionId !== sessionId) {
        // Session not found in history, start fresh with this ID
        loadSession(urlSessionId, []);
      }
    }
  }, [isLoaded, urlSessionId, getSession, loadSession, sessionId]);

  // Save session when messages change
  useEffect(() => {
    if (messages.length > 0) {
      saveSession(sessionId, messages);
    }
  }, [messages, sessionId, saveSession]);

  const handleSelectSession = useCallback(
    (selectedSessionId: string) => {
      const session = getSession(selectedSessionId);
      if (session) {
        // Load the session messages directly
        loadSession(session.id, session.messages);
        // Update URL without full page reload
        router.push(`/chat?session=${selectedSessionId}`, { scroll: false });
      }
    },
    [getSession, loadSession, router]
  );

  const handleNewChat = useCallback(async () => {
    const newSessionId = await newChat();
    router.push(`/chat?session=${newSessionId}`, { scroll: false });
  }, [newChat, router]);

  const handleDeleteSession = useCallback(
    (sessionIdToDelete: string) => {
      deleteSession(sessionIdToDelete);
      if (sessionIdToDelete === sessionId) {
        handleNewChat();
      }
    },
    [deleteSession, sessionId, handleNewChat]
  );

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      {sidebarOpen && (
        <ChatSidebar
          sessions={sessions}
          activeSessionId={sessionId}
          onSelectSession={handleSelectSession}
          onNewChat={handleNewChat}
          onDeleteSession={handleDeleteSession}
        />
      )}

      {/* Main Chat Area */}
      <div className="flex flex-1 flex-col">
        {/* Top bar with back button */}
        <div className="flex items-center gap-2 border-b bg-white px-4 py-2">
          <Button
            variant="ghost"
            size="sm"
            asChild
            className="text-slate-500 hover:text-[#3b82f6] hover:bg-slate-50"
          >
            <Link href="/">
              <ArrowLeft className="mr-1 h-4 w-4" />
              Back to Demo
            </Link>
          </Button>
        </div>

        <ChatHeader
          title="OIP Assistant"
          subtitle="Ask me anything about OIP"
          onNewChat={handleNewChat}
          showExpandButton={false}
          showContextSelectors={true}
          showUserInfo={true}
        />

        <div className="flex-1 overflow-hidden">
          <ChatMessages messages={messages} isLoading={isLoading} />
        </div>

        {error && (
          <div className="px-4 py-2 bg-destructive/10 text-destructive text-sm text-center">
            {error}
          </div>
        )}

        <ChatInput
          onSend={sendMessage}
          isLoading={isLoading}
          placeholder="Ask about tickets, SLAs, inventory, or any OIP feature..."
        />
      </div>
    </div>
  );
}
