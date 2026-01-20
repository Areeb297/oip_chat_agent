'use client';

import { Plus, MessageSquare, Trash2, Search, PanelLeftClose, PanelLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { ChatSession } from '@/types/chat';
import { useState } from 'react';

interface ChatSidebarProps {
  sessions: ChatSession[];
  activeSessionId?: string;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onDeleteSession: (sessionId: string) => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

export function ChatSidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  isCollapsed = false,
  onToggleCollapse,
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

  // Collapsed sidebar view
  if (isCollapsed) {
    return (
      <div className="flex h-full w-16 flex-col border-r bg-slate-50/80 backdrop-blur-sm">
        <TooltipProvider delayDuration={0}>
          {/* Expand button */}
          <div className="flex items-center justify-center border-b bg-white p-3">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onToggleCollapse}
                  className="h-10 w-10 text-slate-500 hover:text-[#3b82f6] hover:bg-blue-50"
                >
                  <PanelLeft className="h-5 w-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">
                <p>Expand sidebar</p>
              </TooltipContent>
            </Tooltip>
          </div>

          {/* New chat button */}
          <div className="flex items-center justify-center p-3">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  onClick={onNewChat}
                  size="icon"
                  className="h-10 w-10 bg-[#3b82f6] hover:bg-[#2563eb] text-white shadow-md"
                >
                  <Plus className="h-5 w-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">
                <p>New chat</p>
              </TooltipContent>
            </Tooltip>
          </div>

          {/* Session icons */}
          <ScrollArea className="flex-1">
            <div className="flex flex-col items-center gap-2 p-2">
              {filteredSessions.slice(0, 10).map((session) => (
                <Tooltip key={session.id}>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className={cn(
                        'h-10 w-10 shrink-0',
                        activeSessionId === session.id
                          ? 'bg-[#3b82f6]/10 text-[#3b82f6]'
                          : 'text-slate-500 hover:text-[#3b82f6] hover:bg-blue-50'
                      )}
                      onClick={() => onSelectSession(session.id)}
                    >
                      <MessageSquare className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-[200px]">
                    <p className="line-clamp-2">{session.title}</p>
                  </TooltipContent>
                </Tooltip>
              ))}
            </div>
          </ScrollArea>

          {/* Status indicator */}
          <div className="border-t bg-white p-3 flex justify-center">
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="h-3 w-3 rounded-full bg-[#22c55e] shadow-sm shadow-green-500/50" />
              </TooltipTrigger>
              <TooltipContent side="right">
                <p>OIP Assistant Online</p>
              </TooltipContent>
            </Tooltip>
          </div>
        </TooltipProvider>
      </div>
    );
  }

  // Expanded sidebar view
  return (
    <div className="flex h-full w-72 flex-col border-r bg-slate-50/80 backdrop-blur-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b bg-white px-4 py-3">
        <h2 className="text-lg font-semibold text-[#1e3a5f]">Chats</h2>
        <div className="flex items-center gap-1">
          <Button
            onClick={onNewChat}
            size="sm"
            className="bg-[#3b82f6] hover:bg-[#2563eb] text-white shadow-sm"
          >
            <Plus className="mr-1 h-4 w-4" />
            New
          </Button>
          {onToggleCollapse && (
            <TooltipProvider delayDuration={0}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={onToggleCollapse}
                    className="h-8 w-8 text-slate-400 hover:text-[#3b82f6] hover:bg-blue-50"
                  >
                    <PanelLeftClose className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Collapse sidebar</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
      </div>

      {/* Search */}
      <div className="p-3 bg-white border-b">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input
            placeholder="Search chats..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 bg-slate-50 border-slate-200 focus:border-[#3b82f6] focus:ring-[#3b82f6]/20"
          />
        </div>
      </div>

      {/* Session List */}
      <ScrollArea className="flex-1 min-h-0">
        <div className="flex flex-col gap-1 p-2">
          {filteredSessions.length === 0 ? (
            <div className="p-6 text-center">
              <MessageSquare className="h-10 w-10 text-slate-300 mx-auto mb-3" />
              <p className="text-sm text-slate-500">
                {searchQuery ? 'No chats found' : 'No chat history yet'}
              </p>
              <p className="text-xs text-slate-400 mt-1">
                Start a new conversation
              </p>
            </div>
          ) : (
            filteredSessions.map((session) => (
              <div
                key={session.id}
                className={cn(
                  'group relative flex items-start gap-3 rounded-xl p-3 cursor-pointer transition-all duration-200',
                  activeSessionId === session.id
                    ? 'bg-[#3b82f6]/10 shadow-sm'
                    : 'hover:bg-white hover:shadow-sm'
                )}
                onClick={() => onSelectSession(session.id)}
              >
                <div
                  className={cn(
                    'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors',
                    activeSessionId === session.id
                      ? 'bg-[#3b82f6] text-white'
                      : 'bg-slate-100 text-slate-500 group-hover:bg-blue-50 group-hover:text-[#3b82f6]'
                  )}
                >
                  <MessageSquare className="h-4 w-4" />
                </div>
                <div className="flex-1 min-w-0 py-0.5">
                  <p
                    className={cn(
                      'text-sm font-medium leading-snug line-clamp-2',
                      activeSessionId === session.id
                        ? 'text-[#3b82f6]'
                        : 'text-slate-700 group-hover:text-[#1e3a5f]'
                    )}
                  >
                    {session.title}
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    {formatDate(session.updatedAt)}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn(
                    'h-7 w-7 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity',
                    'hover:bg-red-50 hover:text-red-500 text-slate-400'
                  )}
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(session.id);
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))
          )}
        </div>
      </ScrollArea>

      {/* Footer */}
      <div className="border-t bg-white p-4">
        <div className="flex items-center gap-2">
          <div className="relative">
            <div className="h-2.5 w-2.5 rounded-full bg-[#22c55e]" />
            <div className="absolute inset-0 h-2.5 w-2.5 rounded-full bg-[#22c55e] animate-ping opacity-75" />
          </div>
          <span className="text-xs text-slate-500 font-medium">OIP Assistant Online</span>
        </div>
      </div>
    </div>
  );
}
