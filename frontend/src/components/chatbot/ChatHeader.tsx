'use client';

import { Minimize2, Maximize2, RotateCcw, X, LogOut, User } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useUser } from '@/contexts/UserContext';
import { PROJECTS, TEAMS } from '@/lib/constants';

interface ChatHeaderProps {
  title?: string;
  subtitle?: string;
  onClose?: () => void;
  onExpand?: () => void;
  onNewChat?: () => void;
  isExpanded?: boolean;
  showExpandButton?: boolean;
  showContextSelectors?: boolean;
  showUserInfo?: boolean;
}

export function ChatHeader({
  title = 'OIP Assistant',
  subtitle = 'Ask me anything about OIP',
  onClose,
  onExpand,
  onNewChat,
  isExpanded = false,
  showExpandButton = true,
  showContextSelectors = false,
  showUserInfo = false,
}: ChatHeaderProps) {
  const { username, roleName, projectCode, team, setProject, setTeam, logout } = useUser();

  return (
    <div className="flex flex-col border-b border-slate-100 bg-gradient-to-r from-white to-slate-50/50">
      {/* Main header row */}
      <div className="flex items-center justify-between px-4 py-2">
        <div className="flex items-center gap-3">
          {/* Logo icon with gradient */}
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 shadow-lg shadow-blue-500/20">
            <svg
              className="h-5 w-5 text-white"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M12 2L2 7L12 12L22 7L12 2Z"
                fill="white"
                fillOpacity="0.3"
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M2 17L12 22L22 17"
                stroke="white"
                strokeOpacity="0.7"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M2 12L12 17L22 12"
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-[#1e3a5f]">{title}</h2>
            <p className="text-xs text-slate-500">{subtitle}</p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <TooltipProvider>
            {/* Username and role display - only when showUserInfo is true */}
            {showUserInfo && username && (
              <div className="flex items-center gap-1 mr-2 px-2 py-1 bg-slate-100 rounded-md">
                <User className="h-3 w-3 text-slate-500" />
                <span className="text-xs text-slate-600">{username}</span>
                {roleName && (
                  <>
                    <span className="text-xs text-slate-300">|</span>
                    <span className="text-xs text-[#3b82f6] font-medium">{roleName}</span>
                  </>
                )}
              </div>
            )}

            {onNewChat && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-slate-500 hover:bg-slate-100 hover:text-[#3b82f6]"
                    onClick={onNewChat}
                    aria-label="Start new chat"
                  >
                    <RotateCcw className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>New chat</p>
                </TooltipContent>
              </Tooltip>
            )}

            {showExpandButton && onExpand && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-slate-500 hover:bg-slate-100 hover:text-[#3b82f6]"
                    onClick={onExpand}
                    aria-label={isExpanded ? 'Minimize' : 'Expand'}
                  >
                    {isExpanded ? (
                      <Minimize2 className="h-4 w-4" />
                    ) : (
                      <Maximize2 className="h-4 w-4" />
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>{isExpanded ? 'Minimize' : 'Expand'}</p>
                </TooltipContent>
              </Tooltip>
            )}

            {onClose && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-slate-500 hover:bg-slate-100 hover:text-[#3b82f6]"
                    onClick={onClose}
                    aria-label="Close chat"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Close</p>
                </TooltipContent>
              </Tooltip>
            )}

            {/* Logout button - only when showUserInfo is true */}
            {showUserInfo && username && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-slate-500 hover:bg-red-50 hover:text-red-500"
                    onClick={logout}
                    aria-label="Logout"
                  >
                    <LogOut className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Logout</p>
                </TooltipContent>
              </Tooltip>
            )}
          </TooltipProvider>
        </div>
      </div>

      {/* Context selectors row (only shown when enabled) */}
      {showContextSelectors && (
        <div className="flex items-center gap-3 px-4 pb-3">
          <div className="flex items-center gap-2 flex-1">
            <span className="text-xs text-slate-500 whitespace-nowrap">Project:</span>
            <Select
              value={projectCode || 'all'}
              onValueChange={(value) => setProject(value === 'all' ? null : value)}
            >
              <SelectTrigger className="h-8 text-xs flex-1 max-w-[180px]">
                <SelectValue placeholder="All Projects" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Projects</SelectItem>
                {PROJECTS.map((project) => (
                  <SelectItem key={project.code} value={project.code}>
                    {project.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2 flex-1">
            <span className="text-xs text-slate-500 whitespace-nowrap">Team:</span>
            <Select
              value={team || 'all'}
              onValueChange={(value) => setTeam(value === 'all' ? null : value)}
            >
              <SelectTrigger className="h-8 text-xs flex-1 max-w-[180px]">
                <SelectValue placeholder="All Teams" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Teams</SelectItem>
                {TEAMS.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      )}
    </div>
  );
}
