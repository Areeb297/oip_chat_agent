'use client';

import { Plus, MessageSquare, Trash2, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import type { ChatSession } from '@/types/chat';
import { useState } from 'react';

interface ChatSidebarProps {
  sessions: ChatSession[];
  activeSessionId?: string;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onDeleteSession: (sessionId: string) => void;
}

export function ChatSidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
}: ChatSidebarProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredSessions = sessions.filter((session) =>
    session.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatDate = (date: Date) => {
    const now = new Date();
    const sessionDate = new Date(date);
    const diffDays = Math.floor(
      (now.getTime() - sessionDate.getTime()) / (1000 * 60 * 60 * 24)
    );

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    return sessionDate.toLocaleDateString();
  };

  return (
    <div className="flex h-full w-64 flex-col border-r bg-slate-50/50">
      {/* Header */}
      <div className="flex items-center justify-between border-b bg-white p-4">
        <h2 className="text-lg font-semibold text-[#1e3a5f]">Chats</h2>
        <Button
          onClick={onNewChat}
          size="sm"
          className="bg-[#3b82f6] hover:bg-[#2563eb] text-white"
        >
          <Plus className="mr-1 h-4 w-4" />
          New
        </Button>
      </div>

      {/* Search */}
      <div className="p-3 bg-white border-b">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input
            placeholder="Search chats..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 bg-slate-50 border-slate-200"
          />
        </div>
      </div>

      {/* Session List */}
      <ScrollArea className="flex-1">
        <div className="flex flex-col gap-1 p-2">
          {filteredSessions.length === 0 ? (
            <div className="p-4 text-center text-sm text-slate-400">
              {searchQuery ? 'No chats found' : 'No chat history yet'}
            </div>
          ) : (
            filteredSessions.map((session) => (
              <div
                key={session.id}
                className={cn(
                  'group flex items-start gap-2 rounded-lg p-3 cursor-pointer transition-colors',
                  activeSessionId === session.id
                    ? 'bg-[#3b82f6]/10 text-[#3b82f6] border border-[#3b82f6]/20'
                    : 'hover:bg-slate-100 text-slate-600'
                )}
                onClick={() => onSelectSession(session.id)}
              >
                <MessageSquare className="mt-0.5 h-4 w-4 shrink-0" />
                <div className="flex-1 overflow-hidden">
                  <p className="truncate text-sm font-medium">
                    {session.title}
                  </p>
                  <p className="text-xs text-slate-400">
                    {formatDate(session.updatedAt)}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 opacity-0 group-hover:opacity-100 hover:bg-red-50 hover:text-red-500"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(session.id);
                  }}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            ))
          )}
        </div>
      </ScrollArea>

      {/* Footer */}
      <div className="border-t bg-white p-3">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <div className="h-2 w-2 rounded-full bg-[#22c55e]" />
          <span>OIP Assistant Online</span>
        </div>
      </div>
    </div>
  );
}
