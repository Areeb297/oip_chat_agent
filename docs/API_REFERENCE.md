# OIP Assistant - Chat API Reference

**Version:** 1.0.0
**Base URL:** `http://localhost:8080` (dev) | `https://<production-host>` (prod)
**Protocol:** REST + Server-Sent Events (SSE)
**Backend:** FastAPI + Google ADK (Agent Development Kit)

---

## Overview

The OIP Assistant exposes a chat API that routes user queries through a multi-agent system built on Google ADK. The system uses **Server-Sent Events (SSE)** for real-time streaming responses with status updates as the agent processes requests.

Every request must include the logged-in user's identity so the agent can scope ticket data, permissions, and personalization to that user.

---

## Known Users (Test Data)

These are the usernames currently in the system. The `username` field in all requests must match one of these values.

| Email | Username | Role |
|-------|----------|------|
| `engineer@ebttikar.com.sa` | `fieldengineer` | Field Engineer |
| `logisticssupervisor@ebttikar.com.sa` | `logisticssupervisor` | Logistics Supervisor |
| `residentengineer@ebttikar.com.sa` | `residentengineer` | Resident Engineer |
| `operationsmanager@ebttikar.com.sa` | `operationsmanager` | Operations Manager |
| `areeb@ebttikar.com` | `areeb` | Administrator |
| `shamlankm@ebttikar.com` | `shamlankm` | Supervisor |
| `ahmad@ebttikar.com` | `ahmad` | Engineer |

> **Note:** The `username` is the short name (e.g., `shamlankm`), **not** the email address. This is what gets passed to the stored procedure as `@Username`.

---

## Endpoint Summary

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/chat/session/start` | Create a new chat session |
| `POST` | `/chat/message` | Send a message (streaming SSE) |
| `GET` | `/chat/session/{id}` | Retrieve session details |
| `DELETE` | `/chat/session/{id}` | Delete a chat session |
| `GET` | `/health` | Health check |

### Current Prototype Mapping

| Current Prototype Endpoint | Target Endpoint | Notes |
|---|---|---|
| `POST /session/new` | `POST /chat/session/start` | Currently creates session without user context |
| `POST /run_sse` | `POST /chat/message` | Main endpoint; handles streaming and non-streaming |
| `POST /chat` | `POST /chat/message` | Simple non-streaming variant (legacy) |
| `GET /health` | `GET /health` | No change needed |
| _(not implemented)_ | `GET /chat/session/{id}` | Needs to be built |
| _(not implemented)_ | `DELETE /chat/session/{id}` | Needs to be built |

---

## 1. Create Chat Session

```
POST /chat/session/start
Content-Type: application/json
```

Creates a new chat session and initializes it with user context. Returns a `sessionId` (UUID) used in all subsequent message requests.

### Request Body

```json
{
  "username": "shamlankm",
  "userRole": "Supervisor",
  "userRoleCode": "SUP",
  "projectNames": ["ANB", "Barclays"],
  "teamNames": ["Maintenance"],
  "regionNames": ["Riyadh", "Eastern"]
}
```

### Field Reference

| Field | Type | Required | Description | Example Values |
|-------|------|----------|-------------|----------------|
| `username` | `string` | **MANDATORY** | The logged-in user's short username. This is passed to the SQL Server stored procedure as `@Username` to scope all ticket data. | `"shamlankm"`, `"areeb"`, `"fieldengineer"`, `"ahmad"` |
| `userRole` | `string` | Optional | Display name of the user's role. Used for context in agent responses. | `"Field Engineer"`, `"Supervisor"`, `"Operations Manager"`, `"Administrator"` |
| `userRoleCode` | `string` | Optional | Short code for the role. | `"ENG"`, `"SUP"`, `"OPM"`, `"ADM"` |
| `projectNames` | `string[]` | Optional | Array of project names the user wants to filter by. If omitted or `null`, the agent queries all projects the user has access to. | `["ANB"]`, `["ANB", "Barclays"]`, `null` |
| `teamNames` | `string[]` | Optional | Array of team names to filter by. If omitted or `null`, the agent queries all teams. | `["Maintenance"]`, `["Development", "Test Team"]`, `null` |
| `regionNames` | `string[]` | Optional | Array of region names to filter by. If omitted or `null`, the agent queries all regions. | `["Riyadh"]`, `["Riyadh", "Eastern", "South"]`, `null` |

### Response `200 OK`

```json
{
  "sessionId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `sessionId` | `string` | UUID v4. Pass this in all subsequent `/chat/message` calls. |

### Example: Field Engineer Starting a Session

```json
{
  "username": "fieldengineer",
  "userRole": "Field Engineer",
  "userRoleCode": "ENG",
  "projectNames": ["ANB"],
  "teamNames": null,
  "regionNames": ["Riyadh"]
}
```

### Example: Admin Starting a Session (No Filters)

```json
{
  "username": "areeb",
  "userRole": "Administrator",
  "userRoleCode": "ADM"
}
```

> When optional fields are omitted, the agent queries across all projects, teams, and regions that the user has access to.

---

## 2. Send Chat Message (Streaming SSE)

```
POST /chat/message
Content-Type: application/json
```

Sends a user message and receives a **streaming SSE response**. This is the primary endpoint. The user context fields are sent on **every message** (not just session start) because the user may change project/team filters mid-conversation via the UI dropdowns.

### Request Body

```json
{
  "appName": "oip_assistant",
  "userId": "shamlankm",
  "sessionId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "newMessage": {
    "role": "user",
    "parts": [
      { "text": "How many open tickets do I have for ANB?" }
    ]
  },
  "streaming": true,
  "username": "shamlankm",
  "userRole": "Supervisor",
  "userRoleCode": "SUP",
  "projectNames": ["ANB"],
  "teamNames": ["Maintenance"],
  "regionNames": null
}
```

### Field Reference

#### Mandatory Fields

| Field | Type | Description | Example Values |
|-------|------|-------------|----------------|
| `appName` | `string` | Application identifier. Always pass `"oip_assistant"`. | `"oip_assistant"` |
| `userId` | `string` | User ID for ADK session management. Use the same value as `username`. | `"shamlankm"`, `"areeb"` |
| `sessionId` | `string` | Session UUID returned from `/chat/session/start`. | `"a1b2c3d4-e5f6-7890-abcd-ef1234567890"` |
| `newMessage` | `object` | The user's message. Must contain `role` and `parts`. | See below |
| `newMessage.role` | `string` | Always `"user"`. | `"user"` |
| `newMessage.parts` | `array` | Array with one object containing the message text. | `[{ "text": "What are my tickets?" }]` |
| `newMessage.parts[].text` | `string` | The actual message text the user typed. | `"Show SLA breaches for ANB this month"` |
| `streaming` | `boolean` | `true` for SSE streaming (recommended), `false` for plain JSON. | `true` |
| `username` | `string` | **The logged-in user's short username.** This is non-negotiable. It is passed to the stored procedure as `@Username`. | `"shamlankm"`, `"fieldengineer"`, `"ahmad"` |

#### Optional Fields

| Field | Type | Default | Description | Example Values |
|-------|------|---------|-------------|----------------|
| `userRole` | `string` | `null` | Display name of the user's role. | `"Field Engineer"`, `"Supervisor"`, `"Administrator"` |
| `userRoleCode` | `string` | `null` | Short code for the role. | `"ENG"`, `"SUP"`, `"ADM"` |
| `projectNames` | `string[]` | `null` | Active project filter from UI dropdown. `null` means "All Projects". | `["ANB"]`, `["ANB", "Barclays"]`, `null` |
| `teamNames` | `string[]` | `null` | Active team filter from UI dropdown. `null` means "All Teams". | `["Maintenance"]`, `["Development"]`, `null` |
| `regionNames` | `string[]` | `null` | Active region filter from UI dropdown. `null` means "All Regions". | `["Riyadh"]`, `["Eastern", "South"]`, `null` |

#### Legacy Fields (Backward Compatibility, Deprecated)

These are still accepted but the array versions above are preferred.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `projectCode` | `string` | Single project code. | `"ANB"` |
| `team` | `string` | Single team name. | `"Maintenance"` |
| `region` | `string` | Single region name. | `"Riyadh"` |

### Full Example: Supervisor Querying Tickets

```json
{
  "appName": "oip_assistant",
  "userId": "shamlankm",
  "sessionId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "newMessage": {
    "role": "user",
    "parts": [
      { "text": "How many breached tickets do I have this month?" }
    ]
  },
  "streaming": true,
  "username": "shamlankm",
  "userRole": "Supervisor",
  "userRoleCode": "SUP",
  "projectNames": ["ANB", "Barclays"],
  "teamNames": ["Maintenance"],
  "regionNames": null
}
```

### Full Example: Admin Asking About OIP Documentation

```json
{
  "appName": "oip_assistant",
  "userId": "areeb",
  "sessionId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "newMessage": {
    "role": "user",
    "parts": [
      { "text": "How does the SLA delay calculation work?" }
    ]
  },
  "streaming": true,
  "username": "areeb",
  "userRole": "Administrator",
  "userRoleCode": "ADM",
  "projectNames": null,
  "teamNames": null,
  "regionNames": null
}
```

### Full Example: Engineer Asking for a Chart

```json
{
  "appName": "oip_assistant",
  "userId": "fieldengineer",
  "sessionId": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "newMessage": {
    "role": "user",
    "parts": [
      { "text": "Plot a chart showing ticket status for ANB vs Barclays" }
    ]
  },
  "streaming": true,
  "username": "fieldengineer",
  "userRole": "Field Engineer",
  "userRoleCode": "ENG",
  "projectNames": ["ANB", "Barclays"],
  "teamNames": null,
  "regionNames": ["Riyadh"]
}
```

### Full Example: Minimal Request (Only Mandatory Fields)

```json
{
  "appName": "oip_assistant",
  "userId": "ahmad",
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "newMessage": {
    "role": "user",
    "parts": [
      { "text": "What are my tickets?" }
    ]
  },
  "streaming": true,
  "username": "ahmad"
}
```

> This is the **bare minimum** valid request. All optional fields default to `null`, meaning the agent queries across all projects, teams, and regions for the user `ahmad`.

---

### SSE Response Format

**Content-Type:** `text/event-stream`

The response is a stream of `data:` prefixed lines. Each line contains a JSON object. There are three event types:

#### Event 1: Status Update

Sent as the agent processes the request. The frontend shows these as a loading indicator (e.g., "Fetching your tickets...").

```
data: {"status": "Analyzing your request..."}
data: {"status": "Checking ticket data..."}
data: {"status": "Fetching your tickets..."}
```

#### Event 2: Text Response

The final agent response. Content is **HTML**, not Markdown.

```
data: {"text": "<p><strong>Ticket Summary for ANB</strong></p><ul><li><span style='color:#3b82f6'>Open: 12</span></li><li><span style='color:#22c55e'>Completed: 5</span></li></ul>"}
```

#### Event 3: Stream Complete

Signals the end of the response.

```
data: [DONE]
```

#### Full SSE Stream Example

```
data: {"status": "Analyzing your request..."}

data: {"status": "Checking ticket data..."}

data: {"status": "Fetching your tickets..."}

data: {"text": "<p><strong>Ticket Summary for ANB - January 2026</strong></p><p>User: <strong>shamlankm</strong> (Supervisor)</p><ul><li><span style='color:#3b82f6'>Open: 12</span></li><li><span style='color:#22c55e'>Completed: 5</span></li><li><span style='color:#f59e0b'>Suspended: 1</span></li><li><span style='color:#dc2626'>SLA Breached: 2</span></li></ul><p>Completion Rate: <strong>26.3%</strong></p>"}

data: [DONE]
```

#### Status Messages Reference

| When | Status Message |
|------|---------------|
| Request received | `"Analyzing your request..."` |
| Routed to `oip_expert` | `"Consulting OIP documentation..."` |
| Routed to `ticket_analytics` | `"Checking ticket data..."` |
| Routed to `greeter` | `"Preparing response..."` |
| Calling `search_oip_documents` | `"Searching documentation..."` |
| Calling `get_ticket_summary` | `"Fetching your tickets..."` |
| Calling `create_chart` | `"Creating chart..."` |
| Calling `create_ticket_status_chart` | `"Building status chart..."` |
| Calling `create_completion_rate_gauge` | `"Creating completion gauge..."` |
| Calling `create_tickets_over_time_chart` | `"Plotting trend chart..."` |
| Calling `create_project_comparison_chart` | `"Building comparison chart..."` |

### Non-Streaming Response (`streaming: false`)

If `streaming` is set to `false`, the response is a plain JSON object:

```json
{
  "response": "<p>Your ticket summary...</p>",
  "sessionId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "userId": "shamlankm"
}
```

---

## 3. Get Session Details

```
GET /chat/session/{id}
```

Retrieves session metadata, current state, and conversation history.

### Path Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `id` | `string` | **MANDATORY** | Session UUID | `"a1b2c3d4-e5f6-7890-abcd-ef1234567890"` |

### Response `200 OK`

```json
{
  "sessionId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "userId": "shamlankm",
  "state": {
    "username": "shamlankm",
    "userRole": "Supervisor",
    "userRoleCode": "SUP",
    "projectCode": "ANB,Barclays",
    "team": "Maintenance",
    "region": "",
    "last_ticket_data": {
      "TotalTickets": 19,
      "OpenTickets": 12,
      "CompletedTickets": 5,
      "SuspendedTickets": 1,
      "PendingApproval": 1,
      "SLABreached": 2,
      "CompletionRate": 26.3
    },
    "last_query_type": "ticket_summary"
  },
  "messages": [
    {
      "role": "user",
      "parts": [{ "text": "What are my open tickets for ANB?" }]
    },
    {
      "role": "model",
      "parts": [{ "text": "<p>You have 12 open tickets for ANB...</p>" }]
    }
  ]
}
```

### Session State Fields

| Key | Type | Description | Example |
|-----|------|-------------|---------|
| `username` | `string` | Logged-in username | `"shamlankm"` |
| `userRole` | `string` | User's role name | `"Supervisor"` |
| `userRoleCode` | `string` | User's role code | `"SUP"` |
| `projectCode` | `string` | Comma-separated project names | `"ANB,Barclays"` or `""` for all |
| `team` | `string` | Comma-separated team names | `"Maintenance"` or `""` for all |
| `region` | `string` | Comma-separated region names | `"Riyadh,Eastern"` or `""` for all |
| `last_ticket_data` | `object` | Last ticket query result (used for "chart the above" follow-ups) | See stored procedure response below |
| `last_query_type` | `string` | Type of last query | `"ticket_summary"` |

---

## 4. Delete Session

```
DELETE /chat/session/{id}
```

Deletes a chat session and its full conversation history.

### Path Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `id` | `string` | **MANDATORY** | Session UUID to delete | `"a1b2c3d4-e5f6-7890-abcd-ef1234567890"` |

### Response `200 OK`

```json
{
  "status": "deleted",
  "sessionId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

---

## 5. Health Check

```
GET /health
```

Returns service health status for load balancers and monitoring.

### Response `200 OK`

```json
{
  "status": "healthy"
}
```

---

## How Filters Work

The UI has **Project** and **Team** dropdowns. When the user selects a filter, it is sent on every `/chat/message` request as `projectNames` and `teamNames`.

### What Gets Passed to the Database

The arrays are converted to comma-separated strings and stored in the ADK session state:

| UI Selection | Sent as | Stored in Session State as |
|---|---|---|
| Project dropdown: "ANB" selected | `"projectNames": ["ANB"]` | `"projectCode": "ANB"` |
| Project dropdown: "ANB" + "Barclays" selected | `"projectNames": ["ANB", "Barclays"]` | `"projectCode": "ANB,Barclays"` |
| Project dropdown: "All Projects" | `"projectNames": null` | `"projectCode": ""` |
| Team dropdown: "Maintenance" selected | `"teamNames": ["Maintenance"]` | `"team": "Maintenance"` |
| Team dropdown: "All Teams" | `"teamNames": null` | `"team": ""` |

### Filter Injection Into Messages

When filters are active, the backend **prepends** the filter context to the user's message text so the agent always knows the active filters:

```
Original message: "What are my tickets?"
Injected message: "[ACTIVE_PROJECT_FILTER: ANB] [ACTIVE_TEAM_FILTER: Maintenance] What are my tickets?"
```

This is transparent to the user. The agent strips these tags and uses them for query scoping.

---

## Database Integration

The `ticket_analytics` agent calls the SQL Server stored procedure. Here is exactly what is passed:

```sql
EXEC usp_Chatbot_GetTicketSummary
    @Username      = 'shamlankm',       -- From: username field (MANDATORY)
    @ProjectNames  = 'ANB,Barclays',    -- From: projectNames array, joined as CSV
    @TeamNames     = 'Maintenance',     -- From: teamNames array, joined as CSV
    @Month         = 1,                 -- Extracted from user's natural language query
    @Year          = 2026,              -- Extracted from user's natural language query
    @DateFrom      = '2026-01-01',      -- Extracted from user's natural language query
    @DateTo        = '2026-01-31'       -- Extracted from user's natural language query
```

> **Important:** `@Username` always comes from the `username` field in the API request. `@ProjectNames` and `@TeamNames` come from `projectNames` / `teamNames` arrays. `@Month`, `@Year`, `@DateFrom`, `@DateTo` are extracted by the AI agent from the user's natural language (e.g., "this month", "last week", "Q4 2025").

### Stored Procedure Response

| Field | Type | Description |
|-------|------|-------------|
| `TotalTickets` | `int` | Total count of tickets |
| `OpenTickets` | `int` | Number of open tickets |
| `SuspendedTickets` | `int` | Number of suspended tickets |
| `CompletedTickets` | `int` | Number of completed tickets |
| `PendingApproval` | `int` | Tickets awaiting approval |
| `SLABreached` | `int` | Tickets that breached SLA |
| `CompletionRate` | `float` | Percentage of completed tickets (e.g., `26.3`) |
| `Username` | `string` | The queried username (e.g., `"shamlankm"`) |
| `UserRole` | `string` | User's role (e.g., `"Supervisor"`) |
| `ProjectFilter` | `string` | Applied project filter (e.g., `"ANB,Barclays"`) |
| `TeamFilter` | `string` | Applied team filter (e.g., `"Maintenance"`) |
| `DateRange` | `string` | Applied date range (e.g., `"2026-01-01 to 2026-01-31"`) |
| `Message` | `string` | Status message (e.g., `"Success"`) |

---

## Response Formatting

All agent responses are **HTML** (not Markdown). The frontend renders this directly using `dangerouslySetInnerHTML`.

### Color Codes

| Color | Hex | Used For |
|-------|-----|----------|
| Blue | `#3b82f6` | Open / In Progress tickets |
| Green | `#22c55e` | Completed / Success |
| Orange | `#f59e0b` | Suspended / Warning |
| Red | `#dc2626` | SLA Breached / Error |

### Chart Responses

When the agent returns a chart, the HTML includes an embedded Recharts JSON configuration:

```html
<div class="recharts-container" data-chart='{"type":"pie","data":[{"name":"Open","value":12},{"name":"Completed","value":5}],"config":{"colors":["#3b82f6","#22c55e"]}}'></div>
```

The frontend `DynamicChart` component parses the `data-chart` attribute and renders an interactive Recharts visualization.

---

## Agent Routing

The root agent (`oip_assistant`) automatically routes to sub-agents based on intent:

| User Intent | Example Messages | Routed To |
|---|---|---|
| Greetings | "Hi", "Hello", "Marhaba" | `greeter` |
| Ticket queries, workload, SLA | "What are my tickets?", "Show SLA breaches", "How many open tickets for ANB?" | `ticket_analytics` |
| OIP platform documentation | "How does ticket closure work?", "What is the BTR tracker?" | `oip_expert` |
| Chart requests | "Plot a chart of ticket status", "Chart the above" | `ticket_analytics` |

---

## Frontend SSE Client Example (TypeScript)

```typescript
async function sendMessage(
  sessionId: string,
  message: string,
  username: string,
  projectNames?: string[],
  teamNames?: string[]
) {
  const response = await fetch('http://localhost:8080/chat/message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      appName: 'oip_assistant',
      userId: username,
      sessionId: sessionId,
      newMessage: {
        role: 'user',
        parts: [{ text: message }],
      },
      streaming: true,
      username: username,
      projectNames: projectNames || null,
      teamNames: teamNames || null,
    }),
  });

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const data = line.slice(6).trim();

      if (data === '[DONE]') {
        console.log('Stream complete');
        return;
      }

      const parsed = JSON.parse(data);

      if (parsed.text) {
        // Final agent response (HTML string)
        document.getElementById('response')!.innerHTML = parsed.text;
      } else if (parsed.status) {
        // Loading status (e.g., "Fetching your tickets...")
        document.getElementById('status')!.textContent = parsed.status;
      }
    }
  }
}

// Usage
sendMessage(
  'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  'How many open tickets for ANB?',
  'shamlankm',
  ['ANB'],
  ['Maintenance']
);
```

---

## Error Handling

| HTTP Code | Meaning | Example Cause |
|-----------|---------|---------------|
| `200` | Success | - |
| `400` | Bad request | Missing `username` or `sessionId` |
| `404` | Not found | Invalid session ID |
| `422` | Validation error | Wrong field type (e.g., string instead of array for `projectNames`) |
| `500` | Server error | Database unreachable, agent failure |

Error response format:

```json
{
  "detail": "Field required: username"
}
```

```json
{
  "detail": [
    {
      "loc": ["body", "username"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

---

## CORS

Development:

```python
allow_origins=["*"]
allow_methods=["*"]
allow_headers=["*"]
```

Production should restrict `allow_origins` to the OIP application domain (e.g., `https://oip.ebttikar.com`).

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | Yes | - | Gemini API key for agent models |
| `OPENROUTER_API_KEY` | Yes | - | For embeddings (RAG) and LLM calls |
| `SQL_SERVER_HOST` | Yes | `LAPTOP-3BGTAL2E\SQLEXPRESS` | SQL Server host |
| `SQL_SERVER_DATABASE` | Yes | `TickTraq` | Database name |
| `SQL_SERVER_USER` | No | - | DB username (not needed with Windows auth) |
| `SQL_SERVER_PASSWORD` | No | - | DB password (not needed with Windows auth) |
| `SQL_SERVER_DRIVER` | No | `ODBC Driver 17 for SQL Server` | ODBC driver name |
| `TAVILY_API_KEY` | No | - | Optional web search capability |
