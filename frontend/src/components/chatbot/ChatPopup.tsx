'use client';

import { useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { ChatHeader } from './ChatHeader';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';
import { useChat } from '@/hooks/useChat';
import { useChatHistory } from '@/hooks/useChatHistory';
import { useUser } from '@/contexts/UserContext';
import { cn } from '@/lib/utils';

interface ChatPopupProps {
  isOpen: boolean;
  onClose: () => void;
  onExpand?: () => void;
  position?: 'bottom-right' | 'bottom-left';
  sessionId?: string;
  onNewSession?: (sessionId: string) => void;
}

export function ChatPopup({
  isOpen,
  onClose,
  onExpand,
  position = 'bottom-right',
  sessionId,
  onNewSession,
}: ChatPopupProps) {
  // Get user context
  const { username, roleName, roleCode, projectCode, team } = useUser();

  const { messages, isLoading, loadingStatus, error, sendMessage, newChat, sessionId: currentSessionId } =
    useChat({
      initialSessionId: sessionId,
      onNewSession,
      userContext: {
        username,
        userRole: roleName,
        userRoleCode: roleCode,
        // Convert single values to arrays for the new API format
        projectNames: projectCode ? [projectCode] : null,
        teamNames: team ? [team] : null,
        // Also keep legacy fields for backwards compatibility
        projectCode,
        team,
      },
    });

  const { saveSession } = useChatHistory();

  // Save session when messages change
  useEffect(() => {
    if (messages.length > 0) {
      saveSession(currentSessionId, messages);
    }
  }, [messages, currentSessionId, saveSession]);

  if (!isOpen) return null;

  return (
    <Card
      className={cn(
        'fixed z-40 flex flex-col overflow-hidden',
        'w-[400px] h-[600px]',
        'rounded-2xl border border-slate-200/60',
        'shadow-[0_25px_50px_-12px_rgba(0,0,0,0.25)]',
        'animate-in fade-in-0 slide-in-from-bottom-5 duration-300',
        position === 'bottom-right'
          ? 'right-6 bottom-24'
          : 'left-6 bottom-24'
      )}
    >
      <ChatHeader
        onClose={onClose}
        onExpand={onExpand}
        onNewChat={newChat}
        showExpandButton={!!onExpand}
      />

      <div className="flex-1 overflow-hidden">
        <ChatMessages messages={messages} isLoading={isLoading} loadingStatus={loadingStatus} />
      </div>

      {error && (
        <div className="px-4 py-2 bg-destructive/10 text-destructive text-sm">
          {error}
        </div>
      )}

      <ChatInput onSend={sendMessage} isLoading={isLoading} />
    </Card>
  );
}
