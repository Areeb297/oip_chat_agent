'use client';

import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { cn } from '@/lib/utils';
import type { Message } from '@/types/chat';
import { Bot, User } from 'lucide-react';

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  const formatTime = (date: Date) => {
    return new Date(date).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Render message content - HTML for assistant, plain text for user
  const renderContent = () => {
    if (!message.content) {
      return <span className="italic text-slate-400">...</span>;
    }

    // User messages are plain text
    if (isUser) {
      return message.content;
    }

    // Assistant messages may contain HTML formatting
    return (
      <div
        className="chat-html-content"
        dangerouslySetInnerHTML={{ __html: message.content }}
      />
    );
  };

  return (
    <div
      className={cn(
        'flex gap-3 px-4 py-3',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      <Avatar className={cn('h-8 w-8 shrink-0', isUser ? 'bg-[#3b82f6]' : 'bg-blue-50')}>
        <AvatarFallback className={cn(isUser ? 'bg-[#3b82f6] text-white' : 'bg-blue-50 text-[#3b82f6]')}>
          {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
        </AvatarFallback>
      </Avatar>

      <div
        className={cn(
          'flex max-w-[80%] flex-col gap-1',
          isUser ? 'items-end' : 'items-start'
        )}
      >
        <div
          className={cn(
            'rounded-2xl px-4 py-3 text-sm',
            isUser
              ? 'bg-[#3b82f6] text-white rounded-br-md'
              : 'bg-slate-100 text-[#1e3a5f] rounded-bl-md',
            message.status === 'error' && 'bg-red-50 text-red-600'
          )}
        >
          {renderContent()}
          {message.status === 'streaming' && (
            <span className="ml-1 inline-block h-4 w-1 animate-pulse bg-current" />
          )}
        </div>
        <span className="text-xs text-slate-400">
          {formatTime(message.timestamp)}
        </span>
      </div>
    </div>
  );
}
