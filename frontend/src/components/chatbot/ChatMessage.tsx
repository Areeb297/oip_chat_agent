'use client';

import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { cn } from '@/lib/utils';
import type { Message } from '@/types/chat';
import { Bot, User, Copy, Check } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);

  const formatTime = (date: Date) => {
    return new Date(date).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const handleCopy = async () => {
    const textContent = message.content.replace(/<[^>]*>/g, '');
    await navigator.clipboard.writeText(textContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Render message content - HTML for assistant, plain text for user
  const renderContent = () => {
    if (!message.content) {
      return <span className="italic text-slate-400">...</span>;
    }

    // User messages are plain text
    if (isUser) {
      return <span className="whitespace-pre-wrap break-words">{message.content}</span>;
    }

    // Assistant messages may contain HTML formatting
    return (
      <div
        className="chat-html-content prose prose-sm max-w-none prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5"
        dangerouslySetInnerHTML={{ __html: message.content }}
      />
    );
  };

  return (
    <div
      className={cn(
        'group flex gap-3 px-4 py-4',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      <Avatar
        className={cn(
          'h-9 w-9 shrink-0 ring-2 ring-offset-2',
          isUser
            ? 'bg-[#3b82f6] ring-[#3b82f6]/20'
            : 'bg-gradient-to-br from-blue-50 to-blue-100 ring-blue-100'
        )}
      >
        <AvatarFallback
          className={cn(
            isUser
              ? 'bg-[#3b82f6] text-white'
              : 'bg-gradient-to-br from-blue-50 to-blue-100 text-[#3b82f6]'
          )}
        >
          {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
        </AvatarFallback>
      </Avatar>

      <div
        className={cn(
          'flex flex-col gap-1.5',
          isUser ? 'items-end' : 'items-start',
          'max-w-[85%] min-w-0'
        )}
      >
        <div
          className={cn(
            'relative rounded-2xl px-4 py-3 text-sm',
            isUser
              ? 'bg-[#3b82f6] text-white rounded-br-sm'
              : 'bg-slate-100 text-[#1e3a5f] rounded-bl-sm',
            message.status === 'error' && 'bg-red-50 text-red-600',
            'break-words overflow-hidden'
          )}
        >
          {renderContent()}
          {message.status === 'streaming' && (
            <span className="ml-1 inline-block h-4 w-0.5 animate-pulse bg-current" />
          )}
        </div>

        <div
          className={cn(
            'flex items-center gap-2',
            isUser ? 'flex-row-reverse' : 'flex-row'
          )}
        >
          <span className="text-xs text-slate-400">
            {formatTime(message.timestamp)}
          </span>
          {!isUser && message.content && (
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity text-slate-400 hover:text-slate-600"
              onClick={handleCopy}
            >
              {copied ? (
                <Check className="h-3 w-3 text-green-500" />
              ) : (
                <Copy className="h-3 w-3" />
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
