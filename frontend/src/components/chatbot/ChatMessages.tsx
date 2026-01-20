'use client';

import { useEffect, useRef, useState } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ChatMessage } from './ChatMessage';
import { TypingIndicator } from './TypingIndicator';
import { FAQSection } from './FAQSection';
import type { Message } from '@/types/chat';
import { HelpCircle, MessageSquare } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ChatMessagesProps {
  messages: Message[];
  isLoading?: boolean;
  loadingStatus?: string;
  onSendMessage?: (message: string) => void;
  /** If true, this is in popup mode and FAQ should scroll */
  isPopup?: boolean;
}

export function ChatMessages({ messages, isLoading, loadingStatus, onSendMessage, isPopup = false }: ChatMessagesProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showFAQ, setShowFAQ] = useState(false);

  const handleFAQQuestionClick = (question: string) => {
    setShowFAQ(false); // Hide FAQ when a question is selected
    if (onSendMessage) {
      onSendMessage(question);
    }
  };

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  // Show FAQ view (either no messages or user toggled FAQ on)
  if (messages.length === 0 || showFAQ) {
    return (
      <div className="flex h-full flex-col bg-gradient-to-b from-slate-50/50 to-white relative">
        {/* Header section */}
        <div className="flex items-center justify-between py-3 px-4 border-b border-slate-100 shrink-0">
          <div className="flex-1 text-center">
            <h3 className="text-base font-semibold text-[#1e3a5f] mb-0.5">
              {messages.length > 0 ? 'Frequently Asked Questions' : 'Welcome to OIP Help'}
            </h3>
            <p className="text-xs text-slate-500">
              Select a topic or ask a question below
            </p>
          </div>
          {/* Back to chat button - only show if there are messages */}
          {messages.length > 0 && (
            <button
              onClick={() => setShowFAQ(false)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-full',
                'bg-blue-600 text-white text-xs font-medium',
                'hover:bg-blue-700 transition-colors shadow-sm'
              )}
            >
              <MessageSquare className="h-3.5 w-3.5" />
              Back to Chat
            </button>
          )}
        </div>

        {/* FAQ Section - scrollable in popup, not in full screen */}
        <div className="flex-1 min-h-0">
          <FAQSection onQuestionClick={handleFAQQuestionClick} noScroll={!isPopup} />
        </div>
      </div>
    );
  }

  // Show messages view with FAQ toggle button
  return (
    <div className="relative h-full">
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

      {/* Floating FAQ button */}
      <button
        onClick={() => setShowFAQ(true)}
        className={cn(
          'absolute bottom-4 right-4 flex items-center gap-2 px-3 py-2 rounded-full',
          'bg-white border border-slate-200 shadow-md',
          'text-slate-600 text-xs font-medium',
          'hover:bg-blue-50 hover:border-blue-200 hover:text-blue-600',
          'transition-all duration-200'
        )}
        title="View FAQs"
      >
        <HelpCircle className="h-4 w-4" />
        <span>FAQs</span>
      </button>
    </div>
  );
}
