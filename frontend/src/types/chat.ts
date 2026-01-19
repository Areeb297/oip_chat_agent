// Chat types for OIP Assistant

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  status?: 'sending' | 'streaming' | 'sent' | 'error';
}

export interface ChatSession {
  id: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
  messages: Message[];
}

export interface ChatRequest {
  message: string;
  session_id?: string;
}

export interface ChatResponse {
  response: string;
  session_id: string;
}

export interface RunSSERequest {
  appName: string;
  userId: string;
  sessionId: string;
  newMessage: {
    role: string;
    parts: { text: string }[];
  };
  streaming: boolean;
  // User context parameters (required)
  username: string;
  // Optional user context
  userRole?: string | null;
  userRoleCode?: string | null;
  // Support multiple projects/teams/regions as arrays
  projectNames?: string[] | null;
  teamNames?: string[] | null;
  regionNames?: string[] | null;
  // Legacy single project/team/region (fallback)
  projectCode?: string | null;
  team?: string | null;
  region?: string | null;
}

export interface UserContext {
  username: string | null;
  userRole: string | null;
  userRoleCode: string | null;
  // Support multiple projects/teams/regions
  projectNames?: string[] | null;
  teamNames?: string[] | null;
  regionNames?: string[] | null;
  // Legacy single project/team/region
  projectCode?: string | null;
  team?: string | null;
  region?: string | null;
}

export interface SSEData {
  text: string;
}

export interface ChatWidgetProps {
  apiBaseUrl?: string;
  position?: 'bottom-right' | 'bottom-left';
  defaultOpen?: boolean;
  sessionId?: string;
  onExpandClick?: () => void;
  onNewSession?: (sessionId: string) => void;
}
