'use client';

import { useState, useCallback } from 'react';
import { ChatIcon } from './ChatIcon';
import { ChatPopup } from './ChatPopup';
import type { ChatWidgetProps } from '@/types/chat';

export function ChatWidget({
  position = 'bottom-right',
  defaultOpen = false,
  sessionId,
  onExpandClick,
  onNewSession,
}: ChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [hasUnread, setHasUnread] = useState(false);

  const handleToggle = useCallback(() => {
    setIsOpen((prev) => !prev);
    if (!isOpen) {
      setHasUnread(false);
    }
  }, [isOpen]);

  const handleClose = useCallback(() => {
    setIsOpen(false);
  }, []);

  const handleExpand = useCallback(() => {
    if (onExpandClick) {
      onExpandClick();
    } else {
      // Default: navigate to full chat page
      window.location.href = '/chat';
    }
  }, [onExpandClick]);

  return (
    <>
      <ChatPopup
        isOpen={isOpen}
        onClose={handleClose}
        onExpand={handleExpand}
        position={position}
        sessionId={sessionId}
        onNewSession={onNewSession}
      />
      <ChatIcon
        isOpen={isOpen}
        onClick={handleToggle}
        hasUnread={hasUnread}
        position={position}
      />
    </>
  );
}
