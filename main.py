# main.py - FastAPI server for ADK agent
# Run with: uvicorn main:app --host 0.0.0.0 --port 8080
# Or: python main.py

import asyncio
import json
import logging
import os
import re
import uuid
from typing import Any, Optional, List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.events import Event
from google.adk.plugins import ReflectAndRetryToolPlugin
from google.genai import types

logger = logging.getLogger("oip_chat_agent")


def _md_to_html(text: str) -> str:
    """Convert common markdown patterns to HTML so the frontend always gets clean HTML."""
    if not text:
        return text

    # Protect <!--CHART_START-->...<!--CHART_END--> blocks from markdown transforms
    # (the italic regex would corrupt * inside JSON strings like "14*10GE")
    _CHART_PH = "\x00__CHART__\x00"
    chart_block = ""
    if "<!--CHART_START-->" in text and "<!--CHART_END-->" in text:
        s = text.index("<!--CHART_START-->")
        e = text.index("<!--CHART_END-->") + len("<!--CHART_END-->")
        chart_block = text[s:e]
        text = text[:s] + _CHART_PH + text[e:]

    # Strip any leaked filter tags from responses
    text = re.sub(r'\[ACTIVE_(?:TEAM|PROJECT|REGION)_FILTER:\s*[^\]]*\]', '', text)
    # Remove markdown headers (## Heading → <strong>Heading</strong>)
    text = re.sub(r'^#{1,4}\s+(.+)$', r'<p><strong>\1</strong></p>', text, flags=re.MULTILINE)
    # Bold: **text** or __text__ → <strong>text</strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    # Italic: *text* or _text_ → <em>text</em>  (but not inside HTML tags)
    text = re.sub(r'(?<![<\w])[\*](.+?)[\*](?![>])', r'<em>\1</em>', text)

    # Restore chart block
    if chart_block:
        text = text.replace(_CHART_PH, chart_block)

    return text.strip()


# Regex for chart JSON pattern (imported from guardrails but kept local for speed)
_CHART_JSON_RE = re.compile(
    r'\{\s*"type"\s*:\s*"(?:bar|pie|donut|line|area|stackedBar|groupedBar|gauge|radialBar)"'
)


def _strip_chart_json_from_text(text: str) -> str:
    """Remove chart JSON (complete or truncated) from LLM response text.

    When a chart tool stores its JSON in session state, the LLM's attempt
    to reproduce the JSON is redundant (and often truncated for large charts).
    This strips it so the post-processor can inject the authoritative copy.
    """
    if not text:
        return text

    # First remove any complete chart blocks with delimiters
    text = re.sub(r'<!--CHART_START-->.*?<!--CHART_END-->', '', text, flags=re.DOTALL)

    # Then remove orphaned chart JSON (complete or truncated)
    match = _CHART_JSON_RE.search(text)
    if not match:
        return text.strip()

    start_idx = match.start()

    # Try to find the closing brace (complete JSON)
    depth = 0
    in_str = False
    esc = False
    for i in range(start_idx, len(text)):
        c = text[i]
        if esc:
            esc = False
            continue
        if c == '\\' and in_str:
            esc = True
            continue
        if c == '"' and not esc:
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                # Complete JSON found — remove it
                return (text[:start_idx] + text[i + 1:]).strip()

    # Truncated JSON (unbalanced braces) — remove from start to end
    return text[:start_idx].strip()


async def _generate_session_title(session_id: str, user_msg: str, assistant_msg: str):
    """Generate a concise AI title for a chat session (runs as background task)."""
    try:
        import litellm
        from my_agent.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, Models

        response = await litellm.acompletion(
            model=f"openrouter/{Models.GPT4O_MINI}",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate a concise 3-6 word title summarizing this conversation. "
                        "Return ONLY the title text, no quotes, no punctuation at the end."
                    ),
                },
                {
                    "role": "user",
                    "content": f"User: {user_msg[:200]}\nAssistant: {assistant_msg[:300]}",
                },
            ],
            api_key=OPENROUTER_API_KEY,
            api_base=OPENROUTER_BASE_URL,
            max_tokens=20,
            temperature=0.5,
        )

        title = response.choices[0].message.content.strip().strip('"\'')
        if title:
            update_session_title(session_id, title[:100])
            logger.debug("[TITLE] Generated title for session %s: %s", session_id, title)
    except Exception as e:
        logger.warning("[TITLE] Failed to generate title for session %s: %s", session_id, e)


async def _load_history_into_session(session, session_id: str, session_service):
    """Load conversation history from DB into ADK session if it has no events.

    This ensures the agent has context of previous messages even after server restart.
    """
    if session.events:
        return  # Already has in-memory history

    db_messages = get_session_messages(session_id)
    if not db_messages:
        return

    for i, msg in enumerate(db_messages):
        role = msg.get("Role", "user")
        content_text = msg.get("Content", "")
        if not content_text:
            continue

        # Map DB role to ADK Content role
        adk_role = "user" if role == "user" else "model"
        author = "user" if role == "user" else "oip_assistant"

        event = Event(
            author=author,
            invocation_id=f"history_{i}",
            content=types.Content(
                role=adk_role,
                parts=[types.Part.from_text(text=content_text)],
            ),
            partial=False,
        )
        await session_service.append_event(session, event)

    logger.debug("[HISTORY] Loaded %d messages into session %s", len(db_messages), session_id)


from my_agent import root_agent
from my_agent.tools.chart_guardrails import (
    ensure_chart_delimiters,
    validate_chart_output,
    contains_chart_json,
    CHART_TOOL_NAMES,
)
from my_agent.tools.suggestions import generate_suggestions
from my_agent.tools.chat_history import (
    get_user_id_by_username,
    ensure_session,
    save_message,
    update_session_title,
    get_sessions,
    get_session_messages,
    delete_session,
    delete_messages_from,
)

# Initialize FastAPI app
app = FastAPI(title="OIP Chat Agent API", version="1.0.0")

# CORS — restrict to known frontend origins
ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://eco.onasi.care,https://eco.onasi.care",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session service to manage conversation state
session_service = InMemorySessionService()


# =============================================================================
# ADK PLUGINS — Error Handling & Tool Retry (Google ADK Best Practice)
# =============================================================================
class OIPToolRetryPlugin(ReflectAndRetryToolPlugin):
    """Custom retry plugin with Pydantic-powered validation.

    Two types of validation:
    1. DB tools: detect {"status": "error"} pattern → retry with error feedback
    2. Chart tools: Pydantic validation of chart JSON structure → retry with
       descriptive feedback so the LLM can fix its parameters

    On error detection, ADK feeds the error back to the LLM with guidance
    to reflect and retry — this is the agentic feedback loop.
    """

    async def extract_error_from_result(self, *, tool, tool_args, tool_context, result):
        """Validate tool output — returns error dict to trigger retry, None if valid."""
        # DB tools return dicts with status field
        if isinstance(result, dict):
            if result.get("status") == "error":
                error_msg = result.get("Message", result.get("error_message", "Unknown error"))
                logger.warning("[RETRY] Tool '%s' error: %s", tool.name, error_msg)
                return result

        # Chart tools return HTML strings — validate with Pydantic
        if isinstance(result, str) and tool.name in CHART_TOOL_NAMES:
            is_valid, error_feedback = validate_chart_output(result)
            if not is_valid:
                logger.warning("[RETRY] Chart validation failed for '%s': %s", tool.name, error_feedback)
                return {"error": error_feedback}

        return None  # Tool output is valid


# Runner to execute the agent with retry plugin
runner = Runner(
    agent=root_agent,
    app_name="oip_assistant",
    session_service=session_service,
    plugins=[OIPToolRetryPlugin(max_retries=2)],
)


class ChatResponse(BaseModel):
    response: str
    session_id: str


# ADK-style request models (matching adk web format)
class MessagePart(BaseModel):
    text: str | None = None


class NewMessage(BaseModel):
    role: str = "user"
    parts: list[MessagePart]


class RunSSERequest(BaseModel):
    appName: str = Field(alias="appName")
    userId: str = Field(alias="userId")
    sessionId: str = Field(alias="sessionId")
    newMessage: NewMessage = Field(alias="newMessage")
    streaming: bool = False
    # User context fields for OIP integration
    username: str = Field(..., description="Required: logged-in user's username")
    userRole: Optional[str] = Field(default=None, alias="userRole")
    userRoleCode: Optional[str] = Field(default=None, alias="userRoleCode")
    # Support multiple projects/teams/regions as arrays or comma-separated strings
    projectNames: Optional[List[str]] = Field(default=None, alias="projectNames")
    projectCode: Optional[str] = Field(default=None, alias="projectCode")  # Legacy single project
    teamNames: Optional[List[str]] = Field(default=None, alias="teamNames")
    team: Optional[str] = Field(default=None)  # Legacy single team
    regionNames: Optional[List[str]] = Field(default=None, alias="regionNames")
    region: Optional[str] = Field(default=None)  # Legacy single region

    class Config:
        populate_by_name = True


@app.get("/health")
def health_check():
    """Health check endpoint for load balancers"""
    return {"status": "healthy"}


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    # User context fields for ticket queries
    username: str = Field(..., description="Required: logged-in user's username")
    # Support multiple projects/teams
    project_names: Optional[List[str]] = Field(default=None, description="Filter by project(s)")
    team_names: Optional[List[str]] = Field(default=None, description="Filter by team(s)")


def _list_to_csv(items: Optional[List[str]]) -> Optional[str]:
    """Convert list to comma-separated string for session state."""
    if items and len(items) > 0:
        return ",".join(items)
    return None


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to the OIP Assistant and get a response"""
    # Create or reuse session
    session_id = request.session_id or str(uuid.uuid4())
    user_id = request.username

    # Convert lists to comma-separated strings for session state
    project_names_csv = _list_to_csv(request.project_names)
    team_names_csv = _list_to_csv(request.team_names)

    # Build user context state
    # Use empty string instead of None to ensure ADK state properly clears old values
    user_state = {
        "username": request.username,
        "projectCode": project_names_csv if project_names_csv else "",
        "team": team_names_csv if team_names_csv else "",
        "user:username": request.username,  # Persist across sessions
    }

    # Get or create session (async methods)
    session = await session_service.get_session(
        app_name="oip_assistant",
        user_id=user_id,
        session_id=session_id,
    )
    if session is None:
        # Create session with user context in state
        session = await session_service.create_session(
            app_name="oip_assistant",
            user_id=user_id,
            session_id=session_id,
            state=user_state,
        )
    else:
        # Update existing session state with current project/team selection
        session.state.update(user_state)

    # Create user message content
    user_content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=request.message)],
    )

    # Run the agent and collect only FINAL response (not thinking/routing)
    response_text = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_content,
    ):
        # Only collect text from FINAL responses (filters out thinking process)
        if event.is_final_response():
            if event.content and event.content.parts:
                for part in event.content.parts:
                    # Skip thinking/reasoning parts (Gemini built-in thinking)
                    if getattr(part, 'thought', False):
                        continue
                    if hasattr(part, "text") and part.text:
                        response_text = part.text  # Use last final response

    return ChatResponse(response=_md_to_html(response_text), session_id=session_id)


@app.post("/session/new")
async def new_session():
    """Create a new chat session"""
    session_id = str(uuid.uuid4())
    user_id = "default_user"
    await session_service.create_session(
        app_name="oip_assistant",
        user_id=user_id,
        session_id=session_id,
    )
    return {"session_id": session_id}


# ---------------------------------------------------------------------------
# Chat history endpoints (SQL Server persistence)
# ---------------------------------------------------------------------------

@app.get("/sessions")
async def list_sessions(userId: int):
    """Return the user's chat sessions for the sidebar."""
    rows = get_sessions(user_id=userId)
    return {"sessions": rows}


@app.get("/sessions/{session_id}/messages")
async def load_session_messages(session_id: str):
    """Return all messages for a given session."""
    msgs = get_session_messages(session_id)
    return {"messages": msgs}


@app.delete("/sessions/{session_id}")
async def remove_session(session_id: str):
    """Soft-delete a chat session."""
    ok = delete_session(session_id)
    if ok:
        return {"success": True}
    return {"success": False, "error": "Session not found or already deleted"}


class TitleUpdate(BaseModel):
    title: str


@app.delete("/sessions/{session_id}/messages/from/{message_id}")
async def remove_messages_from(session_id: str, message_id: int):
    """Delete a message and all messages after it in a session."""
    deleted = delete_messages_from(session_id, message_id)
    if deleted >= 0:
        return {"success": True, "deleted": deleted}
    return {"success": False, "error": "Failed to delete messages"}


@app.patch("/sessions/{session_id}/title")
async def rename_session(session_id: str, body: TitleUpdate):
    """Rename a chat session."""
    ok = update_session_title(session_id, body.title)
    return {"success": ok}


@app.post("/run_sse")
async def run_sse(request: RunSSERequest):
    """ADK-compatible endpoint for running agent (matches adk web format)"""
    logger.debug("[RAW REQUEST] %s", request.model_dump())

    user_id = request.userId
    session_id = request.sessionId
    username = request.username

    # Handle multiple projects - prefer projectNames array, fallback to projectCode
    project_names_csv = None
    if request.projectNames and len(request.projectNames) > 0:
        project_names_csv = ",".join(request.projectNames)
    elif request.projectCode:
        project_names_csv = request.projectCode

    # Handle multiple teams - prefer teamNames array, fallback to team
    team_names_csv = None
    if request.teamNames and len(request.teamNames) > 0:
        team_names_csv = ",".join(request.teamNames)
    elif request.team:
        team_names_csv = request.team

    # Handle multiple regions - prefer regionNames array, fallback to region
    region_names_csv = None
    if request.regionNames and len(request.regionNames) > 0:
        region_names_csv = ",".join(request.regionNames)
    elif request.region:
        region_names_csv = request.region

    logger.debug("[USER CONTEXT] username=%s, role=%s, projects=%s, teams=%s, regions=%s",
                 username, request.userRole, project_names_csv, team_names_csv, region_names_csv)

    # Build user context state
    # Use empty string instead of None to ensure ADK state properly clears old values
    user_state = {
        "username": username,
        "userRole": request.userRole,
        "userRoleCode": request.userRoleCode,
        "projectCode": project_names_csv if project_names_csv else "",
        "team": team_names_csv if team_names_csv else "",
        "region": region_names_csv if region_names_csv else "",
        "user:username": username,  # Persist across sessions
    }

    # Get or create session (async methods)
    session = await session_service.get_session(
        app_name="oip_assistant",
        user_id=user_id,
        session_id=session_id,
    )
    if session is None:
        # Create session with user context in state for ticket queries
        session = await session_service.create_session(
            app_name="oip_assistant",
            user_id=user_id,
            session_id=session_id,
            state=user_state,
        )
    else:
        # Update existing session state with current project/team selection
        # This allows users to change filters mid-session
        logger.debug("[SESSION UPDATE] Updating session %s", session_id)
        session.state.update(user_state)

    # Load conversation history from DB into ADK session (e.g. after server restart)
    await _load_history_into_session(session, session_id, session_service)

    # Extract text from message parts
    message_text = ""
    for part in request.newMessage.parts:
        if part.text:
            message_text += part.text

    # Inject current filter context into the message so agent always knows the active filters
    # This ensures dropdown selections are respected regardless of session state timing issues
    filter_context = ""
    if team_names_csv:
        filter_context += f"[ACTIVE_TEAM_FILTER: {team_names_csv}] "
    if project_names_csv:
        filter_context += f"[ACTIVE_PROJECT_FILTER: {project_names_csv}] "
    if region_names_csv:
        filter_context += f"[ACTIVE_REGION_FILTER: {region_names_csv}] "

    if filter_context:
        message_text = f"{filter_context}{message_text}"
        logger.debug("[FILTER INJECTION] %s", filter_context.strip())

    # Create user message content
    user_content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=message_text)],
    )

    # ── Persist: ensure session + save user message (raw text, no filter tags) ──
    raw_user_text = ""
    for part in request.newMessage.parts:
        if part.text:
            raw_user_text += part.text

    db_user_id = get_user_id_by_username(username)
    if db_user_id is not None:
        ensure_session(session_id, db_user_id, title=raw_user_text[:100])
        save_message(session_id, "user", raw_user_text)
    else:
        logger.warning("[CHAT HISTORY] Could not resolve DB userId for username=%s, skipping persistence", username)

    if request.streaming:
        # SSE streaming response with token-level streaming
        stream_mode = StreamingMode.SSE if request.streaming else StreamingMode.NONE

        async def event_generator():
            # Send initial status
            yield f"data: {json.dumps({'status': 'Analyzing your request...'})}\n\n"

            last_agent = None
            last_tool = None
            chart_tool_called = False  # When True, buffer text instead of streaming
            captured_chart_html = ""  # Chart tool output captured from function_response
            streamed_text = ""       # text already sent to client via partial chunks
            final_response_text = "" # complete text from the final event (for DB)

            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_content,
                run_config=RunConfig(streaming_mode=stream_mode),
            ):
                # ── DIAGNOSTIC: log every event's structure ──
                _diag_parts = []
                if hasattr(event, 'content') and event.content and getattr(event.content, 'parts', None):
                    for _dp in event.content.parts:
                        if hasattr(_dp, 'function_call') and _dp.function_call:
                            _diag_parts.append(f"fn_call:{getattr(_dp.function_call, 'name', '?')}")
                        elif hasattr(_dp, 'function_response') and _dp.function_response:
                            _diag_parts.append(f"fn_resp:{getattr(_dp.function_response, 'name', '?')}")
                        elif getattr(_dp, 'thought', False):
                            _diag_parts.append("thought")
                        elif hasattr(_dp, 'text') and _dp.text:
                            _diag_parts.append(f"text({len(_dp.text)})")
                        else:
                            _diag_parts.append(type(_dp).__name__)
                print(f"[EVENT] author={getattr(event, 'author', '?')} partial={getattr(event, 'partial', False)} final={event.is_final_response() if hasattr(event, 'is_final_response') else '?'} parts=[{', '.join(_diag_parts) if _diag_parts else 'none'}]")

                # Track agent transfers for status updates
                if hasattr(event, 'author') and event.author:
                    agent_name = event.author
                    if agent_name != last_agent:
                        last_agent = agent_name
                        status_map = {
                            "oip_assistant": "Processing your request...",
                            "oip_expert": "Consulting OIP documentation...",
                            "ticket_analytics": "Checking ticket data...",
                            "greeter": "Preparing response...",
                        }
                        status = status_map.get(agent_name, "Working on it...")
                        yield f"data: {json.dumps({'status': status})}\n\n"

                # Track tool calls for status updates
                if hasattr(event, 'content') and event.content:
                    for part in event.content.parts if event.content.parts else []:
                        if hasattr(part, 'function_call') and part.function_call:
                            tool_name = part.function_call.name
                            if tool_name != last_tool:
                                last_tool = tool_name
                                # Detect chart tool calls — switch to buffered mode
                                if tool_name in CHART_TOOL_NAMES:
                                    chart_tool_called = True
                                    print(f"[STREAM] Chart tool '{tool_name}' detected via function_call — buffering response")
                                tool_status_map = {
                                    "search_oip_documents": "Searching documentation...",
                                    "get_ticket_summary": "Fetching your tickets...",
                                    "get_ticket_timeline": "Fetching ticket timeline...",
                                    "get_pm_checklist_data": "Loading PM checklist data...",
                                    "get_current_date": "Getting date info...",
                                    "get_lookups": "Loading reference data...",
                                    "get_engineer_performance": "Fetching engineer data...",
                                    "get_certification_status": "Checking certifications...",
                                    "get_inventory_consumption": "Fetching inventory data...",
                                    "create_chart_from_session": "Generating visualization...",
                                    "create_chart": "Creating chart...",
                                    "create_ticket_status_chart": "Building status chart...",
                                    "create_completion_rate_gauge": "Creating completion gauge...",
                                    "create_tickets_over_time_chart": "Plotting trend chart...",
                                    "create_project_comparison_chart": "Building comparison chart...",
                                    "create_breakdown_chart": "Building breakdown chart...",
                                    "create_pm_chart": "Creating PM chart...",
                                    "create_engineer_chart": "Creating engineer chart...",
                                    "create_inventory_chart": "Creating inventory chart...",
                                }
                                status = tool_status_map.get(tool_name, "Processing...")
                                logger.debug("[TOOL CALL] %s -> %s", tool_name, status)
                                yield f"data: {json.dumps({'status': status})}\n\n"

                        # ── Capture chart tool output from function_response ──
                        if hasattr(part, 'function_response') and part.function_response:
                            resp_name = getattr(part.function_response, 'name', '')
                            if resp_name in CHART_TOOL_NAMES:
                                resp_data = getattr(part.function_response, 'response', None)
                                # ADK wraps string returns as {"result": str}
                                resp_text = ""
                                if isinstance(resp_data, dict):
                                    # Check 'result' key (ADK's wrapping for string returns)
                                    for key in ('result', 'output', 'response'):
                                        val = resp_data.get(key, '')
                                        if isinstance(val, str) and '<!--CHART_START-->' in val:
                                            resp_text = val
                                            break
                                    # If not found in known keys, check all string values
                                    if not resp_text:
                                        for val in resp_data.values():
                                            if isinstance(val, str) and '<!--CHART_START-->' in val:
                                                resp_text = val
                                                break
                                elif isinstance(resp_data, str):
                                    resp_text = resp_data
                                if "<!--CHART_START-->" in resp_text:
                                    captured_chart_html = resp_text
                                    chart_tool_called = True  # Ensure buffering is active
                                    print(f"[STREAM] Captured chart HTML from function_response of '{resp_name}' (len={len(captured_chart_html)})")

                # ── Stream partial text chunks as they arrive ──
                if getattr(event, 'partial', False):
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            # Skip thinking/reasoning parts (Gemini built-in thinking)
                            if getattr(part, 'thought', False):
                                continue
                            if hasattr(part, "text") and part.text:
                                streamed_text += part.text
                                if not chart_tool_called:
                                    # Detect chart JSON in the accumulated text.
                                    # Once detected, stop streaming raw text — the
                                    # final 'html' event will deliver the processed
                                    # response with proper chart delimiters.
                                    if contains_chart_json(streamed_text):
                                        chart_tool_called = True
                                        print("[STREAM] Chart JSON detected in text — buffering remainder")
                                    else:
                                        yield f"data: {json.dumps({'text': part.text})}\n\n"

                # ── Final response: only send if we haven't streamed partials ──
                elif event.is_final_response():
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            # Skip thinking/reasoning parts
                            if getattr(part, 'thought', False):
                                continue
                            if hasattr(part, "text") and part.text:
                                final_response_text = part.text
                                # Only send to client if no partial chunks were streamed
                                # (avoids duplicate text)
                                if not streamed_text:
                                    # Skip raw text event if it contains chart JSON —
                                    # the post-processed 'html' event will handle it
                                    if contains_chart_json(part.text):
                                        print("[STREAM] Chart JSON in final response — sending only via html event")
                                    else:
                                        yield f"data: {json.dumps({'text': part.text})}\n\n"

            # ── Post-process: convert markdown to HTML, inject chart from session ──
            raw_text = final_response_text or streamed_text
            print(f"[POST-PROC] chart_tool_called={chart_tool_called}, captured_chart_html={len(captured_chart_html)}chars, streamed={len(streamed_text)}chars, final={len(final_response_text)}chars")

            # Fetch session state ONCE — used for chart injection and suggestions
            try:
                current_session = await session_service.get_session(
                    app_name="oip_assistant",
                    user_id=user_id,
                    session_id=session_id,
                )
                s_state = dict(current_session.state) if current_session and current_session.state else {}
            except Exception:
                s_state = {}

            # ── Chart injection: extract chart JSON separately ──
            # Chart config is sent as a separate SSE field ("chartConfig")
            # so the frontend never needs to parse it from innerHTML
            chart_config_str = ""  # Compact JSON string for the chart

            if captured_chart_html and chart_tool_called:
                # Primary: captured from function_response event stream
                print(f"[CHART INJECT] Using captured function_response chart (len={len(captured_chart_html)})")
                _cm = re.search(r'<!--CHART_START-->\s*(.*?)\s*<!--CHART_END-->', captured_chart_html, re.DOTALL)
                if _cm:
                    try:
                        _chart_obj = json.loads(_cm.group(1))
                        chart_config_str = json.dumps(_chart_obj, separators=(',', ':'))
                    except Exception:
                        chart_config_str = _cm.group(1).replace('\n', ' ')
                    print(f"[CHART INJECT] Extracted chart config ({len(chart_config_str)} chars)")
                if raw_text:
                    before_len = len(raw_text)
                    raw_text = _strip_chart_json_from_text(raw_text)
                    print(f"[STRIP] raw_text {before_len} -> {len(raw_text)} chars")
            elif chart_tool_called:
                # Fallback: try session state
                stored_chart_json = s_state.get("last_chart_output")
                if stored_chart_json:
                    print(f"[CHART INJECT] Fallback: session state (len={len(stored_chart_json)})")
                    try:
                        _chart_obj = json.loads(stored_chart_json)
                        chart_config_str = json.dumps(_chart_obj, separators=(',', ':'))
                    except Exception:
                        chart_config_str = stored_chart_json.replace('\n', ' ')
                    print(f"[CHART INJECT] Extracted chart config ({len(chart_config_str)} chars)")
                    if raw_text:
                        raw_text = _strip_chart_json_from_text(raw_text)

            if raw_text:
                # If no chart was extracted, try wrapping orphaned chart JSON
                # BEFORE _md_to_html() — HTML conversion corrupts * in JSON
                if not chart_config_str:
                    raw_text = ensure_chart_delimiters(raw_text)
                clean_text = _md_to_html(raw_text)
            else:
                clean_text = ""

            # Send HTML + chartConfig as separate fields in the SSE event
            # chartConfig bypasses innerHTML entirely — no parsing needed
            if clean_text or chart_config_str:
                event_data = {}
                if clean_text:
                    event_data['html'] = clean_text
                if chart_config_str:
                    event_data['chartConfig'] = chart_config_str
                print(f"[SSE EVENT] html={len(clean_text)}chars, chartConfig={len(chart_config_str)}chars")
                yield f"data: {json.dumps(event_data)}\n\n"

            # ── Persist the clean assistant response ──
            # For DB, embed chart with delimiters so old sessions can still render
            db_content = clean_text
            if chart_config_str:
                db_content += f"<!--CHART_START-->{chart_config_str}<!--CHART_END-->"
            if db_content and db_user_id is not None:
                save_message(session_id, "assistant", db_content)
                # Update session title based on latest exchange (background)
                asyncio.create_task(
                    _generate_session_title(session_id, raw_user_text, clean_text)
                )

            # ── Generate follow-up suggestions (non-blocking) ──
            try:
                suggestions = await generate_suggestions(
                    user_message=raw_user_text,
                    agent_response=raw_text or "",
                    agent_name=last_agent or "oip_assistant",
                    session_state=s_state,
                )
                if suggestions:
                    yield f"data: {json.dumps({'suggestions': suggestions})}\n\n"
            except Exception as e:
                logger.debug("[SUGGESTIONS] Skipped: %s", e)

            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
    else:
        # Non-streaming response
        response_text = ""
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_content,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        # Skip thinking/reasoning parts
                        if getattr(part, 'thought', False):
                            continue
                        if hasattr(part, "text") and part.text:
                            response_text = part.text

        # ── Post-process: convert markdown to HTML and strip filter tags ──
        response_text = _md_to_html(response_text)
        # Layer 2 chart guardrail: re-wrap orphaned chart JSON with delimiters
        response_text = ensure_chart_delimiters(response_text)

        # ── Persist assistant response ──
        if response_text and db_user_id is not None:
            save_message(session_id, "assistant", response_text)
            # Update session title based on latest exchange (background)
            asyncio.create_task(
                _generate_session_title(session_id, raw_user_text, response_text)
            )

        # ── Generate follow-up suggestions ──
        suggestions = []
        try:
            current_session = await session_service.get_session(
                app_name="oip_assistant",
                user_id=user_id,
                session_id=session_id,
            )
            s_state = dict(current_session.state) if current_session and current_session.state else {}
            suggestions = await generate_suggestions(
                user_message=raw_user_text,
                agent_response=response_text or "",
                agent_name="oip_assistant",
                session_state=s_state,
            )
        except Exception as e:
            logger.debug("[SUGGESTIONS] Skipped (non-streaming): %s", e)

        result = {
            "response": response_text,
            "sessionId": session_id,
            "userId": user_id,
        }
        if suggestions:
            result["suggestions"] = suggestions

        return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
    # uvicorn.run(app, host="0.0.0.0", port=8060) - Runs in the server.
