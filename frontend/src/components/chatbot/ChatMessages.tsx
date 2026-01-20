'use client';

import { useEffect, useRef, useState } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ChatMessage } from './ChatMessage';
import { TypingIndicator } from './TypingIndicator';
import { FAQSection } from './FAQSection';
import type { Message } from '@/types/chat';
import { HelpCircle, X, MessageSquare } from 'lucide-react';
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

  if (messages.length === 0) {
    return (
      <div className="flex h-full flex-col bg-gradient-to-b from-slate-50/50 to-white">
        {/* Header section */}
        <div className="flex flex-col items-center py-3 px-4 text-center border-b border-slate-100 shrink-0">
          <h3 className="text-base font-semibold text-[#1e3a5f] mb-0.5">
            Welcome to OIP Help
          </h3>
          <p className="text-xs text-slate-500">
            Select a topic or ask a question below
          </p>
        </div>

        {/* FAQ Section - scrollable in popup, not in full screen */}
        <div className="flex-1 min-h-0">
          <FAQSection onQuestionClick={onSendMessage} noScroll={!isPopup} />
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
