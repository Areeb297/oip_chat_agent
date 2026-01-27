// API client for OIP Chat Agent backend

import { API_CONFIG } from '@/config/api.config';
import type { ChatRequest, ChatResponse, RunSSERequest, UserContext } from '@/types/chat';

/**
 * Simple chat endpoint (non-streaming)
 */
export async function sendChatMessage(
  message: string,
  sessionId?: string
): Promise<ChatResponse> {
  const response = await fetch(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.chat}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      session_id: sessionId,
    } as ChatRequest),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Create a new chat session
 */
export async function createSession(): Promise<{ session_id: string }> {
  const response = await fetch(
    `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.newSession}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to create session: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Health check
 */
export async function healthCheck(): Promise<{ status: string }> {
  const response = await fetch(
    `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.health}`
  );

  if (!response.ok) {
    throw new Error(`Health check failed: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Send message with SSE streaming support
 */
export async function sendStreamingMessage(
  message: string,
  sessionId: string,
  userId: string = API_CONFIG.defaultUserId,
  onChunk: (text: string) => void,
  onComplete: () => void,
  onError: (error: Error) => void,
  userContext?: UserContext,
  onStatus?: (status: string) => void
): Promise<void> {
  const requestBody: RunSSERequest = {
    appName: API_CONFIG.appName,
    userId,
    sessionId,
    newMessage: {
      role: 'user',
      parts: [{ text: message }],
    },
    streaming: true,
    // Include user context (username is required)
    username: userContext?.username || 'anonymous',
    userRole: userContext?.userRole,
    userRoleCode: userContext?.userRoleCode,
    // Prefer array format for projects/teams/regions
    projectNames: userContext?.projectNames,
    teamNames: userContext?.teamNames,
    regionNames: userContext?.regionNames,
    // Also send legacy fields for backwards compatibility
    projectCode: userContext?.projectCode,
    team: userContext?.team,
    region: userContext?.region,
  };

  // Debug: Log what we're sending
  console.log('[API] Sending request with userContext:', {
    username: requestBody.username,
    projectNames: requestBody.projectNames,
    teamNames: requestBody.teamNames,
    regionNames: requestBody.regionNames,
    projectCode: requestBody.projectCode,
    team: requestBody.team,
    region: requestBody.region,
  });

  // Debug: Log actual JSON being sent
  const jsonBody = JSON.stringify(requestBody);
  console.log('[API] JSON body being sent:', jsonBody);

  try {
    const response = await fetch(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.runSse}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      }
    );

    if (!response.ok) {
      throw new Error(`Streaming request failed: ${response.statusText}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        onComplete();
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');

      // Keep the last incomplete line in the buffer
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim();

          if (data === '[DONE]') {
            onComplete();
            return;
          }

          try {
            const parsed = JSON.parse(data);
            if (parsed.text) {
              onChunk(parsed.text);
            } else if (parsed.status && onStatus) {
              onStatus(parsed.status);
            }
          } catch {
            // Ignore JSON parse errors for malformed chunks
          }
        }
      }
    }
  } catch (error) {
    onError(error instanceof Error ? error : new Error('Unknown error'));
  }
}
