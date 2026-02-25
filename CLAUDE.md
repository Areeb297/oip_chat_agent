# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important: Task Tracking

**DO NOT update `current_tasks.md` in the alpha-1-prototype project.** That file is for a separate project. This Ticketing Chatbot project does not have a task tracking file.

## Important: Backend Only

**The frontend for this chatbot is embedded in a separate .NET/Angular application (TickTraq webapp).** Claude should focus exclusively on the Python backend (FastAPI + Google ADK). Do NOT modify or create frontend files in the `frontend/` directory — that code is legacy and no longer used. All frontend changes happen in the TickTraq webapp, outside this repo.

**Database access**: Claude has access to SQL Server via the `sqlserver` MCP tool. Use it to verify tables, test queries, and inspect data directly.

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

This is the **Ebttikar OIP Assistant** - a multi-agent chatbot for the Operations Intelligence Platform (OIP) and TickTraq ticket management system. Built with:
- **Backend**: Google ADK + FastAPI with streaming SSE
- **Frontend**: TickTraq .NET/Angular webapp (separate repo)
- **Vector Store**: FAISS with OpenRouter embeddings
- **Database**: SQL Server (TickTraq)

**Architecture diagrams**: See [`docs/architecture.md`](docs/architecture.md) for full Mermaid diagrams covering agent hierarchy, request flow, tool ecosystem, session state, and data pipelines.

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
```

## System Architecture

> Full interactive Mermaid diagrams: [`docs/architecture.md`](docs/architecture.md)

```
TickTraq Webapp (.NET/Angular)
        │
        │  POST /run_sse (SSE Stream)
        ▼
┌─────────────────────────────────────────────────────┐
│  FastAPI Server (port 8080)                         │
│  - Filter injection (project/team/region tags)      │
│  - Session state management (username, role)        │
│  - SSE streaming with status updates                │
│  - Markdown→HTML conversion, filter tag cleanup     │
│  - Chat persistence (ChatbotMessages DB)            │
└─────────────────────────────────────────────────────┘
        │
        │  ADK Runner
        ▼
┌─────────────────────────────────────────────────────┐
│  root_agent (Coordinator/Dispatcher)                │
│  Pattern: LLM-driven delegation via transfer        │
│  Model: gemini-2.5-flash                            │
│                                                     │
│  ┌─────────┐  ┌──────────────────┐  ┌───────────┐  │
│  │ greeter │  │ ticket_analytics │  │ oip_expert│  │
│  │ (no     │  │ (10 tools)       │  │ (1 tool)  │  │
│  │  tools) │  │ ReAct reasoning  │  │ CoT + RAG │  │
│  └─────────┘  └──────────────────┘  └───────────┘  │
│                    │          │           │          │
│              SQL Server  Chart Engine  FAISS Index   │
│              (TickTraq)  (Recharts)   (Vector DB)   │
└─────────────────────────────────────────────────────┘
```

### Design Pattern Used: Coordinator/Dispatcher
This project follows the **Coordinator/Dispatcher** multi-agent pattern from Google ADK. The root agent is an LLM agent that analyzes user intent and delegates to specialist sub-agents via `transfer_to_agent()`. Sub-agent `description` fields are critical — the coordinator LLM uses them to make routing decisions.

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
**Tools** (10 total):

**Database Tools:**
- `get_ticket_summary()` - Fetch ticket statistics from SQL Server (role-based filtering)
- `get_current_date()` - Get date context for time-based queries
- `get_lookups()` - Reference data (projects, teams, regions, statuses)

**Session-Aware Chart Tools:**
- `create_chart_from_session()` - Flexible metric selection from session data (preferred for "chart the above")
- `create_breakdown_chart()` - Simplified breakdown by project/region/team

**Direct Chart Tools:**
- `create_chart()` - General purpose chart (auto-selects type)
- `create_ticket_status_chart()` - Pie chart of ticket statuses
- `create_completion_rate_gauge()` - Gauge chart for completion rate
- `create_tickets_over_time_chart()` - Line chart trends
- `create_project_comparison_chart()` - Bar chart comparison

**Reasoning Pattern**: ReAct (THOUGHT → ACTION → OBSERVATION → RESPONSE)
**Key Features**:
- Session state for "chart the above" queries (avoids re-querying DB)
- Natural language time expressions (this month, last week, Q4 2025)
- Dynamic date context (current month, last month auto-calculated)
- Derived metrics: within_sla, non_suspended, remaining, completion_rate

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

## Frontend (External — TickTraq Webapp)

The frontend is embedded in the **TickTraq .NET/Angular webapp** (separate repository). The `frontend/` directory in this repo is legacy and no longer used. The TickTraq frontend:
- Calls `POST /run_sse` for streaming chat
- Parses `<!--CHART_START-->` / `<!--CHART_END-->` delimiters for chart rendering
- Sends filter selections (project, team, region) in the request body
- Renders HTML responses directly (agents output HTML, not markdown)

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

**ADK Session State** (set in `main.py`, used by tools):
```python
{
    # Identity (persisted, required for DB queries)
    "username": str,              # Injected from request, used by get_ticket_summary()
    "userRole": str,              # For role-based logic (Engineer/Supervisor/Admin)
    "userRoleCode": str,          # Legacy/API compatibility
    "user:username": str,         # Persists across sessions (ADK user: prefix)

    # Filter context (deprecated — superseded by message tag injection)
    "projectCode": str,           # No longer used for filtering
    "team": str,                  # No longer used for filtering
    "region": str,                # No longer used for filtering

    # Tool state (ephemeral, set by tools during conversation)
    "last_ticket_data": dict,     # Stored by get_ticket_summary() for "chart the above"
    "last_query_context": str,    # Query context for follow-up requests
}
```

**Filter Injection Pattern** (replaces session state for filters):
```
Frontend sends: projectFilter="ANB,Barclays", teamFilter="Maintenance"
    ↓
main.py injects into message: "[ACTIVE_PROJECT_FILTER: ANB,Barclays]\n[ACTIVE_TEAM_FILTER: Maintenance]"
    ↓
Agent reads tags → passes to tool parameters
    ↓
main.py strips tags from response before returning to frontend
```

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

## ADK Agent Design Best Practices

> Based on Google ADK official documentation, "Building Agents" course material, and project experience.

### Agent Design Principles

1. **Single Responsibility**: Each agent has ONE well-defined purpose. Don't combine unrelated capabilities.
   - `greeter` = greetings only
   - `oip_expert` = documentation Q&A only
   - `ticket_analytics` = ticket data + visualizations

2. **Clear Description Fields**: Sub-agent `description` is the most important field for routing. The coordinator LLM reads descriptions to decide delegation. Write them as clear API docs.
   ```python
   Agent(
       name="ticket_analytics",
       description="Handles ticket queries, workload analysis, SLA tracking, "
                   "and chart visualizations. Use for any question about tickets, "
                   "team performance, project status, or data visualization."
   )
   ```

3. **Coordinator Should Not Have Tools**: The root agent should only route — not execute. Keep tools on specialist sub-agents. This prevents the coordinator from trying to answer questions itself.

4. **Prefer LLM-Driven Delegation**: Use ADK's `transfer_to_agent()` pattern (AutoFlow) where the LLM decides routing, rather than hardcoded if/else logic. This handles edge cases and ambiguous queries better.

### Tool Design Rules

1. **Return Dictionaries with Status Keys**: Every tool must return `{"status": "success"|"error", ...}`. This gives the LLM clear signals for error handling.
   ```python
   def my_tool(query: str) -> dict:
       try:
           result = do_work(query)
           return {"status": "success", "data": result}
       except Exception as e:
           return {"status": "error", "error_message": str(e)}
   ```

2. **Docstrings Are Critical**: The function docstring IS the tool description sent to the LLM. Write comprehensive docstrings explaining purpose, parameters, and return values. The LLM uses this to decide WHEN and HOW to call the tool.

3. **Never Document `tool_context` in Docstrings**: ADK injects `ToolContext` automatically. Including it in docstrings confuses the LLM into thinking it needs to provide it.
   ```python
   # CORRECT
   def get_ticket_summary(project_names: str = None, tool_context: ToolContext = None) -> dict:
       """Fetch ticket statistics from the database.

       Args:
           project_names: Comma-separated project names (e.g., "ANB,Barclays")
       """

   # WRONG - don't document tool_context
   def get_ticket_summary(project_names: str = None, tool_context: ToolContext = None) -> dict:
       """Args:
           tool_context: ADK session state object  <-- DON'T DO THIS
       """
   ```

4. **Minimize Parameters**: Fewer parameters = fewer chances for the LLM to make errors. Use simple types (str, int, bool). Avoid `*args`, `**kwargs` (ADK ignores them).

5. **Tools Do Computation, Not LLMs**: Put calculations, derived metrics, and data transformations in tool code. Don't ask the LLM to calculate percentages or aggregates — it will get them wrong.
   ```python
   # CORRECT - tool calculates derived metric
   result["within_sla"] = result["total"] - result["breached"]

   # WRONG - asking LLM to calculate in prompt
   # "Calculate within_sla by subtracting breached from total"
   ```

### Session State Best Practices

1. **State Prefix Convention** (ADK standard):
   | Prefix | Scope | Use Case |
   |--------|-------|----------|
   | (none) | Current session | `last_ticket_data`, `last_query_type` |
   | `user:` | Persists across sessions | `user:username`, `user:preferences` |
   | `app:` | Global, all users | `app:system_config` |
   | `temp:` | Current invocation only | `temp:intermediate_calc` |

2. **Never Modify `session.state` Directly**: Always update state through `ToolContext.state` or `EventActions.state_delta`. Direct modification bypasses event tracking and breaks persistence.

3. **Filter Injection > Session State for Request-Scoped Data**: This project injects filter context (project, team, region) directly into the message text via `[ACTIVE_*_FILTER]` tags rather than relying on session state. This avoids ADK session state timing issues where state updates from one turn aren't visible in the same turn.

### Prompt Engineering Patterns

1. **ReAct for Complex Tools** (used by `ticket_analytics`):
   ```
   THOUGHT: Analyze what the user is asking
   ACTION: Call the appropriate tool with correct parameters
   OBSERVATION: Process the tool's response
   RESPONSE: Generate formatted HTML answer
   ```

2. **Chain-of-Thought for RAG** (used by `oip_expert`):
   ```
   UNDERSTAND → RETRIEVE → VALIDATE → SYNTHESIZE → FORMAT
   ```

3. **Structured Instruction Template**:
   - **Role/Persona**: Who the agent is
   - **Capabilities**: What tools are available and when to use each
   - **Routing Rules**: When to delegate (for coordinators)
   - **Output Format**: HTML structure, color codes, response patterns
   - **Constraints/Guardrails**: What NOT to do (never expose DB columns, etc.)
   - **Examples**: Concrete input/output pairs for common scenarios

4. **Dynamic State Injection**: Use `{state_key}` placeholders in instructions to inject session state at runtime:
   ```python
   instruction="You are helping {username} who has the role {userRole}."
   ```

5. **Guardrails in Every Agent Prompt**:
   - Never expose internal terms (ACTIVE_*_FILTER, DB columns, stored procedure names)
   - Never hallucinate data — only use tool results
   - Always use HTML output (never markdown)
   - Color-code status values consistently

### Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | Do Instead |
|-------------|-------------|------------|
| Monolithic agent with many tools | LLM gets confused choosing between 20+ tools | Split into focused sub-agents |
| Hardcoded routing logic | Brittle, can't handle edge cases | Use LLM-driven delegation |
| LLM doing math/aggregation | LLMs make arithmetic errors | Put calculations in tool code |
| Overly long prompts (500+ lines) | Dilutes important instructions | Break into sections, use examples sparingly |
| Exposing raw DB errors to users | Confusing UX, security risk | Catch errors, return friendly messages |
| Storing request-scoped data in session | Timing issues with ADK state | Use filter injection in message text |
| Synchronous tools with I/O | Blocks parallel tool execution | Use `async def` for I/O-bound tools |
| Generic tool names (`do_stuff()`) | LLM can't figure out when to use it | Descriptive names: `get_ticket_summary()` |

### Chart Output Contract

All chart tools return this format for frontend parsing:
```
<!--CHART_START-->
{
  "type": "bar|pie|line|gauge|donut|area",
  "data": [...],
  "config": {...}
}
<!--CHART_END-->
<p>Text summary with insights</p>
```

**Intelligent Chart Type Selection**:
- Time-series data → LINE/AREA
- Proportions/distribution → PIE/DONUT
- Comparisons → BAR
- Single metric percentage → GAUGE

**Color Palette** (consistent across all charts):
| Status | Color | Hex |
|--------|-------|-----|
| Open/In Progress | Blue | `#3b82f6` |
| Completed/Success | Green | `#22c55e` |
| Suspended/Warning | Orange | `#f59e0b` |
| Pending Approval | Purple | `#8b5cf6` |
| SLA Breached/Error | Red | `#ef4444` |

### Testing Agents

```bash
# Quick smoke test — verify agent imports
python -c "from my_agent import root_agent; print(root_agent)"

# Interactive testing via ADK web UI
adk web my_agent

# Test specific tool
python -c "from my_agent.tools.db_tools import get_ticket_summary; print(get_ticket_summary.__doc__)"

# Run the full server
python main.py
```

For regression testing, consider ADK's `.test.json` format:
```json
{
  "name": "ticket_query_test",
  "turns": [
    {
      "query": "How many open tickets do I have?",
      "expected_tool_use": ["get_ticket_summary"],
      "reference": "HTML response with ticket counts"
    }
  ]
}
```

## Dependencies

**Backend (Python)**:
- `google-adk` — Agent orchestration (core framework)
- `fastapi`, `uvicorn` — REST API + SSE streaming
- `faiss-cpu` — Vector similarity search
- `pyodbc` — SQL Server connectivity (ODBC Driver 17)
- `PyMuPDF`, `python-docx` — Document parsing for RAG ingestion
- `pydantic` — Data validation and models
- `litellm` — OpenRouter integration for embeddings + fallback LLMs

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
