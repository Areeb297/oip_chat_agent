# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important: Task Tracking

**DO NOT update `current_tasks.md` in the alpha-1-prototype project.** That file is for a separate project. This Ticketing Chatbot project does not have a task tracking file.

## Claude's Expertise

Claude is an expert in **Google Agent Development Kit (ADK)** - the SDK used to build this chatbot. This includes:
- Agent creation and orchestration using `google.adk.agents.Agent`
- Multi-agent architectures with sub-agents and tool delegation
- ADK tool definitions and function annotations
- Session management and conversation flows
- Integration with Gemini models via ADK
- ADK CLI commands (`adk web`, `adk run`, etc.)
- ToolContext for session state management

Refer to ADK documentation and patterns when extending or debugging this project.

## Project Overview

This is the **Ebttikar OIP Assistant** - a full-stack multi-agent chatbot for the Operations Intelligence Platform (OIP) and TickTraq ticket management system. Built with:
- **Backend**: Google ADK + FastAPI with streaming SSE
- **Frontend**: Next.js 16 + React 19 + Recharts
- **Vector Store**: FAISS with OpenRouter embeddings
- **Database**: SQL Server (TickTraq)

## Common Commands

```bash
# Activate virtual environment (Windows)
venv\Scripts\activate

# Activate virtual environment (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Ingest documents into FAISS vector store (required before first run)
python scripts/ingest_documents.py

# Run the FastAPI backend server (port 8080)
python main.py

# Run the ADK web interface (for testing agents directly)
adk web my_agent

# Test agent import
python -c "from my_agent import root_agent; print(root_agent)"

# Frontend commands (from frontend/ directory)
cd frontend
npm install
npm run dev    # Development server on port 3000
npm run build  # Production build
```

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Frontend (Next.js 16 + React 19)              │
│      Pages: Login, Home, Full Chat + Floating Widget            │
│      Components: ChatFullScreen, ChatMessage, DynamicChart      │
└─────────────────────────────────────────────────────────────────┘
                              │
                    HTTP/Streaming REST API (SSE)
                              │
┌─────────────────────────────────────────────────────────────────┐
│                 Backend (FastAPI + Google ADK)                  │
│                        port 8080                                │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │         root_agent (Coordinator) - Gemini-2.5-flash       │  │
│  │   Routes: Greetings → greeter                             │  │
│  │           Ticket queries → ticket_analytics               │  │
│  │           OIP questions → oip_expert                      │  │
│  └───────────────────────────────────────────────────────────┘  │
│         │                    │                    │              │
│         ▼                    ▼                    ▼              │
│  ┌────────────┐    ┌─────────────────┐    ┌──────────────┐     │
│  │  greeter   │    │ ticket_analytics│    │  oip_expert  │     │
│  │(Greetings) │    │  (DB + Charts)  │    │   (RAG Q&A)  │     │
│  └────────────┘    └─────────────────┘    └──────────────┘     │
│                           │                       │             │
│                    ┌──────┴──────┐          ┌─────┴─────┐       │
│                    ▼             ▼          ▼           │       │
│              SQL Server     Chart Tools   FAISS Index   │       │
│             (TickTraq)      (Recharts)   (Vector DB)    │       │
│                                                 │       │       │
│                                          OpenRouter     │       │
│                                         (Embeddings)    │       │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Architecture

**Total: 1 Root Agent + 3 Active Sub-Agents**

```
root_agent (oip_assistant)
    ├── greeter          → Greetings (English/Arabic)
    ├── oip_expert       → OIP documentation (RAG)
    └── ticket_analytics → Ticket data + Charts (DB + Recharts)
```

### 1. Root Agent (Orchestrator)
**Name**: `oip_assistant`
**File**: `my_agent/agent.py`
**Model**: gemini-2.5-flash (or OpenRouter x-ai/grok-4.1-fast)
**Role**: Routes queries to appropriate sub-agents based on intent

**Routing Logic**:
- Greeting patterns (hi, hello, marhaba) → `greeter`
- Ticket/workload/SLA queries → `ticket_analytics`
- OIP platform/documentation questions → `oip_expert`

### 2. Greeter Sub-Agent
**Name**: `greeter`
**File**: `my_agent/agent.py`
**Purpose**: Handle greetings in English/Arabic
**Tools**: None

### 3. OIP Expert Sub-Agent
**Name**: `oip_expert`
**File**: `my_agent/agent.py`
**Purpose**: Answer OIP platform questions using RAG
**Tools**: `search_oip_documents()`

**Prompting Pattern**:
- Chain of Thought: UNDERSTAND → RETRIEVE → VALIDATE → SYNTHESIZE → FORMAT
- HTML output formatting
- Strict adherence to retrieved documents (no hallucination)

### 4. Ticket Analytics Sub-Agent
**Name**: `ticket_analytics`
**File**: `my_agent/agents/ticket_analytics.py`
**Purpose**: Ticket queries, workload analysis, SLA tracking, visualizations
**Tools** (8 total):
- `get_ticket_summary()` - Fetch ticket statistics from SQL Server
- `get_current_date()` - Get date context for time-based queries
- `create_chart_from_session()` - Create charts from session data (preferred for "chart the above")
- `create_chart()` - General purpose chart (auto-selects type)
- `create_ticket_status_chart()` - Pie chart of ticket statuses
- `create_completion_rate_gauge()` - Gauge chart for completion rate
- `create_tickets_over_time_chart()` - Line chart trends
- `create_project_comparison_chart()` - Bar chart comparison

**Features**:
- ReAct-style reasoning (THOUGHT → ACTION → OBSERVATION → RESPONSE)
- Session state for "chart the above" queries
- Natural language time expressions (this month, last week, Q4 2025)
- Dynamic date context (current month, last month auto-calculated)

### Unused Agent (Not Integrated)
**Name**: `data_visualization`
**File**: `my_agent/agents/data_visualization.py`
**Status**: Defined but NOT registered as a sub-agent
**Note**: Chart functionality was merged into `ticket_analytics` instead

## Tools Reference

### RAG Tool
**File**: `my_agent/tools/rag_tool.py`

```python
search_oip_documents(query: str, top_k: int = 5) -> dict
```
Returns: `{status, query, results[], context, message}`

### Database Tools
**File**: `my_agent/tools/db_tools.py`

```python
get_ticket_summary(
    project_names: str = None,   # Single or comma-separated
    team_names: str = None,      # Single or comma-separated
    month: int = None,           # 1-12
    year: int = None,            # 2020-2030
    date_from: str = None,       # YYYY-MM-DD
    date_to: str = None,         # YYYY-MM-DD
    tool_context: ToolContext    # ADK session state
) -> dict
```
Returns: `{TotalTickets, OpenTickets, SuspendedTickets, CompletedTickets, PendingApproval, SLABreached, CompletionRate, ...}`

### Chart Tools
**File**: `my_agent/tools/chart_tools.py`

All chart tools return HTML strings with embedded Recharts JSON configuration for frontend rendering.

## Backend API Endpoints

**File**: `main.py` (FastAPI on port 8080)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/chat` | POST | Simple non-streaming chat |
| `/session/new` | POST | Create new chat session |
| `/run_sse` | POST | **Main endpoint** - Streaming SSE with status updates |

### Request Format (run_sse)
```json
{
  "app_name": "my_agent",
  "user_id": "user123",
  "session_id": "uuid",
  "new_message": {
    "role": "user",
    "parts": [{"text": "What are my open tickets?"}]
  },
  "streaming": true
}
```

## Frontend Architecture

**Stack**: Next.js 16, React 19, TypeScript, Tailwind CSS, Recharts, Radix UI

### Directory Structure
```
frontend/src/
├── app/
│   ├── page.tsx           # Home page with hero + chat widget
│   ├── login/page.tsx     # Login form
│   ├── chat/page.tsx      # Full-page chat interface
│   └── layout.tsx         # Root layout with UserProvider
├── components/
│   ├── chatbot/
│   │   ├── ChatFullScreen.tsx   # Main chat UI
│   │   ├── ChatSidebar.tsx      # Session history
│   │   ├── ChatMessage.tsx      # Message renderer (HTML + charts)
│   │   ├── ChatInput.tsx        # Input bar
│   │   ├── DynamicChart.tsx     # Recharts renderer
│   │   └── TypingIndicator.tsx
│   └── ui/                # Shadcn UI components
├── contexts/
│   └── UserContext.tsx    # User login state
├── hooks/
│   ├── useChat.ts         # Message & streaming management
│   └── useChatHistory.ts  # Persistent chat history
├── lib/
│   ├── api.ts             # API client (REST + SSE)
│   └── constants.ts       # User database
└── config/
    └── api.config.ts      # API base URL, defaults
```

### Key Frontend Hooks

**useChat** - Main chat logic
```typescript
const { messages, isLoading, loadingStatus, error, sessionId, sendMessage, clearMessages, newChat, loadSession } = useChat()
```

**useChatHistory** - Session persistence
```typescript
const { saveSession, getSession, deleteSession, sessions } = useChatHistory()
```

## Database Integration

**Database**: SQL Server (TickTraq)
**Connection**: ODBC Driver 17
**Host**: `LAPTOP-3BGTAL2E\SQLEXPRESS`

**Stored Procedure**: `usp_Chatbot_GetTicketSummary`
```sql
EXEC usp_Chatbot_GetTicketSummary
    @Username = 'john.doe',
    @ProjectNames = 'ANB,Barclays',
    @TeamNames = 'Development',
    @Month = 1,
    @Year = 2026,
    @DateFrom = '2026-01-01',
    @DateTo = '2026-01-31'
```

## Session State Management

**ADK Session State** (backend):
```python
{
    "username": str,
    "userRole": str,
    "userRoleCode": str,
    "projectCode": str,         # comma-separated
    "team": str,                # comma-separated
    "last_ticket_data": dict,   # for "chart the above"
    "last_query_type": str
}
```

**Frontend Storage**:
- `localStorage`: User context, chat history
- URL params: Session ID (`/chat?session=<uuid>`)

## Response Formatting

All agents use HTML output format (not markdown):
```html
<p><strong>Total:</strong> 19 tickets</p>
<ul>
  <li><span style='color:#3b82f6'>Open: 12</span></li>
  <li><span style='color:#22c55e'>Completed: 5</span></li>
  <li><span style='color:#dc2626'>SLA Breached: 2</span></li>
</ul>
```

**Color Codes**:
- Blue (#3b82f6): Open/In Progress
- Green (#22c55e): Completed/Success
- Orange (#f59e0b): Suspended/Warning
- Red (#dc2626): SLA Breached/Error

## Key Files Reference

| File | Purpose |
|------|---------|
| `main.py` | FastAPI server with SSE streaming |
| `my_agent/agent.py` | Root agent + greeter + oip_expert |
| `my_agent/agents/ticket_analytics.py` | Ticket analytics sub-agent |
| `my_agent/tools/db_tools.py` | SQL Server tools |
| `my_agent/tools/chart_tools.py` | Recharts visualization tools |
| `my_agent/tools/rag_tool.py` | FAISS search tool |
| `my_agent/rag/vector_store.py` | FAISSVectorStore class |
| `my_agent/prompts/templates.py` | All prompt templates |
| `my_agent/models.py` | Pydantic models (Ticket, Document, API) |
| `my_agent/config.py` | Configuration (paths, models, RAG settings) |
| `scripts/ingest_documents.py` | Document ingestion CLI |

## Configuration Reference

**File**: `my_agent/config.py`

```python
# RAG Settings
RAGConfig.CHUNK_SIZE = 500
RAGConfig.CHUNK_OVERLAP = 50
RAGConfig.DEFAULT_TOP_K = 5
RAGConfig.SIMILARITY_THRESHOLD = 0.3

# Models
Models.DEFAULT_AGENT_MODEL = "gemini-2.5-flash"
Models.DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-ada-002"
```

## Environment Variables

Required in `.env`:
```bash
GOOGLE_API_KEY=...         # For Gemini agent models
OPENROUTER_API_KEY=...     # For embeddings and LLM calls
TAVILY_API_KEY=...         # Optional - web search

# Database (SQL Server)
DB_SERVER=LAPTOP-3BGTAL2E\SQLEXPRESS
DB_NAME=TickTraq
DB_USERNAME=...            # Optional if using Windows auth
DB_PASSWORD=...            # Optional if using Windows auth
```

## Adding New Features

### Adding a New Sub-Agent
1. Create agent in `my_agent/agents/new_agent.py`
2. Import and add to `sub_agents=[]` in `my_agent/agent.py`
3. Update root_agent instructions to include routing rules

### Adding New Tools
1. Create function in `my_agent/tools/new_tool.py`
2. Export from `my_agent/tools/__init__.py`
3. Add to agent's `tools=[]` list

### Adding New Documents (RAG)
1. Add PDF/DOCX files to `docs/` folder
2. Re-run: `python scripts/ingest_documents.py`

## Dependencies

**Backend (Python)**:
- google-adk (Agent orchestration)
- fastapi, uvicorn (REST API)
- faiss-cpu (Vector search)
- pyodbc (SQL Server)
- PyMuPDF, python-docx (Document parsing)
- pydantic (Data validation)
- litellm (OpenRouter integration)

**Frontend (JavaScript/TypeScript)**:
- next, react, react-dom
- typescript, tailwindcss
- recharts (Visualizations)
- lucide-react (Icons)
- @radix-ui/* (UI primitives)

## Data Flow Examples

### Ticket Query with Chart
```
User: "What are my ANB tickets? Show me a chart"
    ↓
root_agent → routes to ticket_analytics
    ↓
ticket_analytics → calls get_ticket_summary(project_names="ANB")
    ↓
Data stored in session state (last_ticket_data)
    ↓
Agent → calls create_ticket_status_chart()
    ↓
Returns HTML with Recharts JSON config
    ↓
Frontend → DynamicChart parses and renders interactive chart
```

### OIP Documentation Query
```
User: "How do I create a ticket in OIP?"
    ↓
root_agent → routes to oip_expert
    ↓
oip_expert → calls search_oip_documents("ticket creation")
    ↓
FAISS returns top 5 matching chunks
    ↓
LLM generates answer from retrieved context
    ↓
Frontend → ChatMessage renders HTML response
```
