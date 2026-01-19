'use client';

import { MessageCircle, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ChatIconProps {
  isOpen: boolean;
  onClick: () => void;
  hasUnread?: boolean;
  position?: 'bottom-right' | 'bottom-left';
}

export function ChatIcon({
  isOpen,
  onClick,
  hasUnread = false,
  position = 'bottom-right',
}: ChatIconProps) {
  return (
    <Button
      onClick={onClick}
      className={cn(
        'fixed z-50 h-14 w-14 rounded-full transition-all duration-300',
        'bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white',
        'shadow-xl shadow-blue-500/30 hover:shadow-blue-500/50 hover:scale-105',
        position === 'bottom-right' ? 'right-6 bottom-6' : 'left-6 bottom-6',
        isOpen && 'rotate-90'
      )}
      aria-label={isOpen ? 'Close chat' : 'Open chat'}
    >
      {isOpen ? (
        <X className="h-6 w-6" />
      ) : (
        <>
          <MessageCircle className="h-6 w-6" />
          {hasUnread && (
            <span className="absolute -right-1 -top-1 h-5 w-5 rounded-full bg-red-500 text-[10px] font-bold flex items-center justify-center ring-2 ring-white animate-pulse">
              !
            </span>
          )}
        </>
      )}
    </Button>
  );
}
