// API Configuration for OIP Chat Agent

export const API_CONFIG = {
  // Production: /api (IIS reverse proxies to backend)
  // Development: set NEXT_PUBLIC_API_URL=http://localhost:8080 in .env.development
  baseUrl: process.env.NEXT_PUBLIC_API_URL || '/api',
  endpoints: {
    chat: '/chat',
    runSse: '/run_sse',
    newSession: '/session/new',
    health: '/health',
  },
  appName: 'my_agent',
  defaultUserId: 'web_user',
} as const;

export type ApiConfig = typeof API_CONFIG;
