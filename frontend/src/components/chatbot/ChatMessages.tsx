'use client';

import { useEffect, useRef } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ChatMessage } from './ChatMessage';
import { TypingIndicator } from './TypingIndicator';
import type { Message } from '@/types/chat';
import { MessageCircle } from 'lucide-react';

interface ChatMessagesProps {
  messages: Message[];
  isLoading?: boolean;
  loadingStatus?: string;
}

export function ChatMessages({ messages, isLoading, loadingStatus }: ChatMessagesProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  if (messages.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 py-8 text-center bg-gradient-to-b from-slate-50/50 to-white">
        {/* Icon with subtle animation */}
        <div className="relative mb-6">
          <div className="absolute inset-0 bg-blue-400/20 rounded-full blur-xl animate-pulse" />
          <div className="relative flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-blue-50 to-blue-100 ring-4 ring-blue-50">
            <MessageCircle className="h-7 w-7 text-[#3b82f6]" />
          </div>
        </div>

        {/* Welcome text */}
        <h3 className="text-lg font-semibold text-[#1e3a5f] mb-1">
          Welcome to OIP Assistant
        </h3>
        <p className="text-sm text-slate-500 max-w-[280px] leading-relaxed">
          Ask me anything about the Operations Intelligence Platform
        </p>

        {/* Suggestion chips */}
        <div className="mt-6 w-full">
          <p className="text-xs font-medium text-slate-400 mb-3">Try asking:</p>
          <div className="flex flex-wrap justify-center gap-2">
            {[
              'What is OIP?',
              'Explain ticket tracking',
              'Show SLA metrics',
            ].map((suggestion) => (
              <button
                key={suggestion}
                className="rounded-full bg-white border border-slate-200 px-4 py-2 text-xs font-medium text-slate-600 hover:bg-blue-50 hover:border-blue-200 hover:text-blue-600 cursor-pointer transition-all duration-200 shadow-sm hover:shadow"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <ScrollArea className="h-full bg-white" ref={scrollRef}>
      <div className="flex flex-col py-2">
        {messages.map((message, index) => (
          <ChatMessage
            key={message.id}
            message={message}
            loadingStatus={index === messages.length - 1 && message.status === 'streaming' ? loadingStatus : undefined}
          />
        ))}
        {isLoading &&
          messages[messages.length - 1]?.status !== 'streaming' && (
            <TypingIndicator status={loadingStatus} />
          )}
      </div>
    </ScrollArea>
  );
}
