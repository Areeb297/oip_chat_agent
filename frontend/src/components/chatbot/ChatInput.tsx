'use client';

import { useState, useRef, useEffect, KeyboardEvent, ChangeEvent } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({
  onSend,
  isLoading = false,
  disabled = false,
  placeholder = 'Type your message...',
}: ChatInputProps) {
  const [message, setMessage] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea based on content
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      // Reset height to auto to get the correct scrollHeight
      textarea.style.height = 'auto';
      // Set the height to scrollHeight, with min and max limits
      const newHeight = Math.min(Math.max(textarea.scrollHeight, 44), 200);
      textarea.style.height = `${newHeight}px`;
    }
  }, [message]);

  const handleSend = () => {
    if (message.trim() && !isLoading && !disabled) {
      onSend(message);
      setMessage('');
      // Reset textarea height after sending
      if (textareaRef.current) {
        textareaRef.current.style.height = '44px';
      }
      textareaRef.current?.focus();
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
  };

  return (
    <div className="border-t border-slate-100 bg-gradient-to-t from-slate-50/80 to-white p-4">
      <div className="flex items-end gap-2 rounded-2xl border border-slate-200/80 bg-white p-2 shadow-sm focus-within:border-blue-300 focus-within:ring-2 focus-within:ring-blue-100 transition-all duration-200">
        <textarea
          ref={textareaRef}
          value={message}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled || isLoading}
          rows={1}
          className={cn(
            'flex-1 resize-none bg-transparent px-3 py-2.5 text-sm',
            'placeholder:text-slate-400 text-[#1e3a5f]',
            'focus:outline-none',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'min-h-[44px] max-h-[200px]'
          )}
          style={{ height: '44px' }}
          aria-label="Chat message input"
        />
        <Button
          onClick={handleSend}
          disabled={!message.trim() || isLoading || disabled}
          size="icon"
          className={cn(
            'h-10 w-10 shrink-0 rounded-xl',
            'bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white',
            'shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40',
            'disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none',
            'transition-all duration-200'
          )}
          aria-label="Send message"
        >
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </Button>
      </div>
      <p className="mt-3 text-center text-[11px] text-slate-400">
        AI can make mistakes. Please review sensitive information.
      </p>
    </div>
  );
}
