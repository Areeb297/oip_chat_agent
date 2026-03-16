# main.py - FastAPI server for ADK agent
# Run with: uvicorn main:app --host 0.0.0.0 --port 8080
# Or: python main.py

import asyncio
import json
import logging
import os
import re
import uuid
import warnings
from typing import Any, Optional, List

# Suppress noisy warnings from LiteLLM/Pydantic internals
warnings.filterwarnings("ignore", message=".*PydanticSerializationUnexpectedValue.*")
warnings.filterwarnings("ignore", message=".*Pydantic serializer warnings.*")
# Suppress LiteLLM "Provider List" spam
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("litellm").setLevel(logging.WARNING)
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
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

    # Protect ALL <!--CHART_START-->...<!--CHART_END--> blocks from markdown transforms
    # (the italic regex would corrupt * inside JSON strings like "14*10GE")
    # Use <!--CHARTHOLD:N--> as placeholder — HTML comments are invisible to markdown regexes
    chart_blocks = re.findall(r'<!--CHART_START-->.*?<!--CHART_END-->', text, re.DOTALL)
    for i, block in enumerate(chart_blocks):
        text = text.replace(block, f"<!--CHARTHOLD:{i}-->", 1)

    # Strip any leaked filter tags from responses
    text = re.sub(r'\[ACTIVE_(?:TEAM|PROJECT|REGION)_FILTER:\s*[^\]]*\]', '', text)
    # Remove markdown headers (## Heading → <strong>Heading</strong>)
    text = re.sub(r'^#{1,4}\s+(.+)$', r'<p><strong>\1</strong></p>', text, flags=re.MULTILINE)
    # Bold: **text** or __text__ → <strong>text</strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    # Italic: *text* or _text_ → <em>text</em>  (but not inside HTML tags)
    text = re.sub(r'(?<![<\w])[\*](.+?)[\*](?![>])', r'<em>\1</em>', text)

    # Restore all chart blocks
    for i, block in enumerate(chart_blocks):
        text = text.replace(f"<!--CHARTHOLD:{i}-->", block)

    return text.strip()


# Regex for chart JSON pattern (imported from guardrails but kept local for speed)
_CHART_JSON_RE = re.compile(
    r'\{\s*"type"\s*:\s*"(?:bar|pie|donut|line|area|stackedBar|groupedBar|gauge|radialBar|bubble|scatter)"'
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

    # Restore report state from DB if a previous report exists in this session
    # Scan messages (newest first) for report data in dedicated columns
    for msg in reversed(db_messages):
        report_html = msg.get("ReportHtml") or ""
        report_model_str = msg.get("ReportModelJson") or ""

        # Fallback: check Content field for legacy delimiter-embedded reports
        if not report_html:
            content_text = msg.get("Content", "")
            if content_text and "<!--REPORT_START-->" in content_text:
                _rm = re.search(r'<!--REPORT_START-->(.*?)<!--REPORT_END-->', content_text, re.DOTALL)
                if _rm:
                    report_html = _rm.group(1).strip()
                if not report_model_str:
                    _mm = re.search(r'<!--REPORT_MODEL_START-->(.*?)<!--REPORT_MODEL_END-->', content_text, re.DOTALL)
                    if _mm:
                        report_model_str = _mm.group(1).strip()

        if not report_html:
            continue

        # Found a report — restore into session state
        session.state["last_report_html"] = report_html

        if report_model_str:
            try:
                session.state["report_model"] = json.loads(report_model_str)
                logger.info("[HISTORY] Restored report_model + HTML (%d chars) from DB columns in session %s", len(report_html), session_id)
            except (json.JSONDecodeError, Exception):
                logger.warning("[HISTORY] Failed to parse ReportModelJson, using minimal model")
                report_model_str = ""  # Fall through to minimal model

        # Fallback: build a minimal model (for old sessions without persisted model)
        if not report_model_str and "report_model" not in session.state:
            session.state["report_model"] = {
                "title": "Report",
                "subtitle_line": "",
                "executive_summary": "",
                "insights": "",
                "discussion": "",
                "emphasis": "",
                "report_data": {},
                "gen_date": "",
                "visible_sections": ["tickets", "ticket_types", "engineers", "certifications", "inventory"],
                "kpi_visible": True,
                "hidden_kpi_labels": [],
                "style_overrides": {},
                "version": 1,
                "edit_history": [],
                "_restored_from_db": True,
            }
            logger.info("[HISTORY] Restored report HTML (%d chars) + minimal model into session %s", len(report_html), session_id)
        break


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
    update_report_in_message,
    get_report_model_from_db,
    get_sessions,
    get_session_messages,
    delete_session,
    delete_messages_from,
)

# Initialize FastAPI app
app = FastAPI(title="OIP Chat Agent API", version="1.0.0")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return clear JSON errors for Pydantic validation failures (instead of 422 HTML)."""
    logger.warning(f"[VALIDATION ERROR] {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"status": "error", "message": "Invalid request", "details": exc.errors()},
    )


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
    # Normalize keys for frontend: ReportHtml → reportHtml, ReportModelJson → reportModelJson
    for msg in msgs:
        rh = msg.pop("ReportHtml", None)
        rm = msg.pop("ReportModelJson", None)
        if rh:
            msg["reportHtml"] = rh
        if rm:
            msg["reportModelJson"] = rm
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


# ---------------------------------------------------------------------------
# Inline report editing endpoint (bypasses chat agent for fast edits)
# ---------------------------------------------------------------------------

class ReportEditRequest(BaseModel):
    session_id: str = Field(alias="sessionId")
    user_id: str = Field(default="", alias="userId")
    section_id: Optional[str] = Field(None, alias="sectionId")
    action: str  # manual_update | regenerate | hide | restore | style_change | undo
    new_text: Optional[str] = Field(None, alias="newText")
    prompt: Optional[str] = None
    style_key: Optional[str] = Field(None, alias="styleKey")
    style_value: Optional[str] = Field(None, alias="styleValue")

    class Config:
        populate_by_name = True


class _InlineToolContext:
    """Lightweight ToolContext substitute for inline edits (no ADK agent involved)."""

    def __init__(self, state: dict):
        self.state = state


@app.post("/report/edit")
async def edit_report_inline(request: ReportEditRequest):
    """Direct report editing endpoint — bypasses chat agent for fast inline edits.

    The frontend calls this when the user interacts with hover toolbars on the
    rendered report (edit text, hide sections, change colors, etc.).
    Returns the full updated report HTML for iframe replacement.
    """
    from my_agent.tools.report_editor_tools import (
        toggle_kpi_card as _toggle_kpi,
        remove_report_section as _remove_section,
        restore_report_section as _restore_section,
        rewrite_report_text as _rewrite_text,
        customize_report_style as _customize_style,
        undo_report_edit as _undo_edit,
        rebuild_report_html as _rebuild,
        regenerate_section as _regenerate_section,
    )

    session_id = request.session_id
    user_id = request.user_id
    action = request.action
    logger.info(f"[REPORT EDIT] action={action} section={request.section_id} user={user_id} session={session_id} prompt={request.prompt!r}")

    # Always load report state from DB — this is the source of truth after inline edits.
    # In-memory ADK session state mutations (via _InlineToolContext) are NOT reliably
    # persisted across HTTP calls (direct dict mutation bypasses ADK event tracking).
    # Each edit saves to DB; each edit call must reload from DB to see previous changes.
    db_model, db_html = get_report_model_from_db(session_id)

    if db_model:
        # Extract undo stack that was embedded in the model for DB persistence
        undo_stack = db_model.pop("_undo_stack", [])
        state: dict = {
            "report_model": db_model,
            "last_report_html": db_html,
            "report_undo_stack": undo_stack,
        }
        logger.info(f"[REPORT EDIT] Loaded from DB (undo_levels={len(undo_stack)}) session={session_id}")
    else:
        # DB has no report — fall back to in-memory session (e.g. brand-new report not yet persisted)
        session = None
        if user_id:
            session = await session_service.get_session(
                app_name="oip_assistant",
                user_id=user_id,
                session_id=session_id,
            )
        if session is None and hasattr(session_service, 'sessions'):
            app_sessions = session_service.sessions.get("oip_assistant", {})
            for uid, user_sessions in app_sessions.items():
                if session_id in user_sessions:
                    session = user_sessions[session_id]
                    break
        if session is None or "report_model" not in session.state:
            return JSONResponse(status_code=404, content={
                "status": "no_report",
                "message": "No report found. Please generate a new report.",
            })
        state = session.state

    # Create lightweight tool context wrapping the edit state
    ctx = _InlineToolContext(state)

    # Dispatch action
    result = None
    try:
        if action == "manual_update":
            if not request.section_id or not request.new_text:
                return JSONResponse(status_code=400, content={
                    "status": "error", "message": "section_id and new_text are required for manual_update"
                })
            result = _rewrite_text(
                section_id=request.section_id,
                new_text=request.new_text,
                tool_context=ctx,
            )

        elif action == "hide":
            sid = request.section_id
            if sid.startswith("kpi:"):
                card_label = sid[4:]  # Strip "kpi:" prefix
                result = _toggle_kpi(card_label=card_label, visible=False, tool_context=ctx)
            else:
                result = _remove_section(section_id=sid, tool_context=ctx)

        elif action == "restore":
            sid = request.section_id
            if sid.startswith("kpi:"):
                card_label = sid[4:]
                result = _toggle_kpi(card_label=card_label, visible=True, tool_context=ctx)
            else:
                result = _restore_section(section_id=sid, tool_context=ctx)

        elif action == "style_change":
            if not request.style_key or not request.style_value:
                return JSONResponse(status_code=400, content={
                    "status": "error", "message": "style_key and style_value are required for style_change"
                })
            result = _customize_style(
                **{request.style_key: request.style_value},
                tool_context=ctx,
            )

        elif action == "undo":
            result = _undo_edit(tool_context=ctx)

        elif action == "regenerate":
            if not request.section_id:
                return JSONResponse(status_code=400, content={
                    "status": "error", "message": "section_id is required for regenerate"
                })
            # Default prompt if none provided
            prompt = request.prompt or "Improve this section — make it more detailed, analytical, and professional."
            result = await _regenerate_section(
                section_id=request.section_id,
                prompt=prompt,
                tool_context=ctx,
            )

        else:
            return JSONResponse(status_code=400, content={
                "status": "error", "message": f"Unknown action: {action}",
            })

    except Exception as e:
        logger.error(f"[REPORT EDIT] Error in inline edit: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={
            "status": "error", "message": f"Edit failed: {str(e)}",
        })

    # Check result status
    if not result or result.get("status") in ("error", "no_report"):
        status_code = 404 if result and result.get("status") == "no_report" else 400
        return JSONResponse(status_code=status_code, content=result or {"status": "error", "message": "Unknown error"})

    # Sync state back to ADK session (ctx.state is the same dict reference)
    # The editor tools already updated ctx.state["report_model"] and ctx.state["last_report_html"]

    # Persist updated report to DB — embed undo stack in model JSON so it survives across calls
    report_html = ctx.state.get("last_report_html", "")
    report_model = ctx.state.get("report_model")
    if report_html and report_model:
        try:
            # Embed undo stack inside model so next call can restore it from DB
            model_to_save = {**report_model, "_undo_stack": ctx.state.get("report_undo_stack", [])}
            model_json = json.dumps(model_to_save, default=str)
            update_report_in_message(session_id, report_html, model_json)
        except Exception as e:
            logger.warning(f"[REPORT EDIT] Failed to persist to DB: {e}")

    return {
        "status": "success",
        "version": result.get("version", 1),
        "reportHtml": report_html,
    }


# ---------------------------------------------------------------------------
# Report PDF download endpoint (server-side HTML → A4 PDF via WeasyPrint)
# ---------------------------------------------------------------------------

class ReportPdfRequest(BaseModel):
    session_id: str = Field(alias="sessionId")
    user_id: str = Field(default="", alias="userId")

    class Config:
        populate_by_name = True


@app.post("/report/pdf")
async def download_report_pdf(request: ReportPdfRequest):
    """Generate an A4 PDF from the current report HTML and return it as a downloadable file."""
    from fastapi.responses import Response

    session_id = request.session_id
    user_id = request.user_id

    # Always load from DB first — this is the most reliable source after edits,
    # since inline edits persist to DB but may use a different in-memory session.
    report_html = None

    # 1. Try DB (authoritative — always has the latest after inline edits)
    msgs = get_session_messages(session_id)
    for msg in reversed(msgs):
        rh = msg.get("ReportHtml")
        if rh:
            report_html = rh
            break

    # 2. Fallback: in-memory ADK session (for reports that haven't been persisted yet)
    if not report_html:
        if user_id:
            session = await session_service.get_session(
                app_name="oip_assistant", user_id=user_id, session_id=session_id,
            )
            if session:
                report_html = session.state.get("last_report_html")

        if not report_html and hasattr(session_service, 'sessions'):
            app_sessions = session_service.sessions.get("oip_assistant", {})
            for uid, user_sessions in app_sessions.items():
                if session_id in user_sessions:
                    report_html = user_sessions[session_id].state.get("last_report_html")
                    break

    if not report_html:
        return JSONResponse(status_code=404, content={
            "status": "error", "message": "No report found in this session."
        })

    # Generate PDF using Playwright (headless Chromium — pixel-perfect A4 output)
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            # Set viewport to A4 width (794px) so CSS renders identically to screen
            page = await browser.new_page(viewport={"width": 794, "height": 1123})
            await page.set_content(report_html, wait_until="networkidle")
            pdf_bytes = await page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "5mm", "bottom": "5mm", "left": "5mm", "right": "5mm"},
                prefer_css_page_size=True,
            )
            await browser.close()

        # Extract title from HTML for filename
        title_match = re.search(r'<h1[^>]*>(.*?)</h1>', report_html, re.DOTALL)
        filename = "Report"
        if title_match:
            filename = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            filename = re.sub(r'[^\w\s-]', '', filename).strip()[:60]
        filename = f"{filename}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except Exception as e:
        logger.error(f"[REPORT PDF] Failed to generate PDF: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={
            "status": "error", "message": f"PDF generation failed: {str(e)}",
        })


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

    print(f"[FILTERS] projects={request.projectNames} -> csv={project_names_csv} | teams={request.teamNames} -> csv={team_names_csv} | regions={request.regionNames} -> csv={region_names_csv}")

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
        print(f"[INJECTED MESSAGE] {message_text[:200]}")

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
            captured_report_html = "" # Report HTML captured from build_html_report response
            report_tool_called = False  # Track if report_generator was invoked this request
            report_editor_called = False  # Track if report_editor tools were used this request
            streamed_text = ""       # text already sent to client via partial chunks
            final_response_text = "" # complete text from the final event (for DB)

            # Clear multi-chart accumulator in session state at start of each request
            try:
                _sess = await session_service.get_session(
                    app_name="oip_assistant", user_id=user_id, session_id=session_id,
                )
                if _sess and _sess.state:
                    _sess.state["last_chart_outputs"] = []
            except Exception:
                pass

            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_content,
                run_config=RunConfig(streaming_mode=stream_mode),
            ):
                # Track agent transfers for status updates
                # Debug: log all event authors to trace SequentialAgent sub-agent events
                _evt_author = getattr(event, 'author', None)
                if _evt_author and _evt_author != last_agent:
                    print(f"[EVENT] author='{_evt_author}', content_parts={len(event.content.parts) if hasattr(event, 'content') and event.content and event.content.parts else 0}")
                if hasattr(event, 'author') and event.author:
                    agent_name = event.author
                    if agent_name != last_agent:
                        last_agent = agent_name
                        status_map = {
                            "oip_assistant": "Processing your request...",
                            "oip_expert": "Consulting OIP documentation...",
                            "ticket_analytics": "Checking ticket data...",
                            "greeter": "Preparing response...",
                            "engineer_analytics": "Analyzing engineer performance...",
                            "inventory_analytics": "Checking inventory data...",
                            "report_planner": "Step 1/3 — Analyzing your report request & resolving project details...",
                            "report_data_collector": "Step 2/3 — Querying ticket, engineer & inventory databases...",
                            "report_builder": "Step 3/3 — Crafting executive summary, insights & formatting report...",
                            "report_generator": "Initializing report pipeline...",
                            "report_editor": "Editing your report...",
                        }
                        status = status_map.get(agent_name, "Working on it...")
                        print(f"[STATUS] Agent transition: {agent_name} -> '{status}'")
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
                                # Detect report generator call
                                if tool_name == "report_generator":
                                    report_tool_called = True
                                # Detect report editor tool calls
                                EDITOR_TOOL_NAMES = {"toggle_kpi_card", "remove_report_section", "restore_report_section", "rewrite_report_text", "customize_report_style", "rebuild_report_html", "undo_report_edit"}
                                if tool_name in EDITOR_TOOL_NAMES:
                                    report_editor_called = True
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
                                    "collect_report_data": "Querying databases — tickets, engineers, inventory & timeline...",
                                    "build_html_report": "Building KPI cards, tables & formatting final document...",
                                    "report_generator": "Starting report generation pipeline...",
                                    "toggle_kpi_card": "Updating KPI cards...",
                                    "remove_report_section": "Removing section from report...",
                                    "restore_report_section": "Restoring section to report...",
                                    "rewrite_report_text": "Rewriting report text...",
                                    "customize_report_style": "Applying style changes...",
                                    "rebuild_report_html": "Rebuilding report...",
                                    "undo_report_edit": "Undoing last edit...",
                                    "transfer_to_agent": "Routing to specialist...",
                                }
                                status = tool_status_map.get(tool_name, "Processing...")
                                print(f"[STATUS] Tool call: {tool_name} -> '{status}'")
                                yield f"data: {json.dumps({'status': status})}\n\n"

                        # ── Capture tool responses for status updates and chart output ──
                        if hasattr(part, 'function_response') and part.function_response:
                            resp_name = getattr(part.function_response, 'name', '')

                            # Report tool progress messages (shown after each tool completes)
                            report_tool_status = {
                                "get_current_date": "Date context resolved — determining report period...",
                                "get_lookups": "Project & team references loaded — matching filters...",
                                "collect_report_data": "All data collected — ticket stats, engineer performance & inventory ready!",
                                "build_html_report": "Report assembled — KPI cards, tables & styling complete!",
                                "report_generator": "Report generated successfully — preparing preview...",
                                "toggle_kpi_card": "KPI card updated!",
                                "remove_report_section": "Section removed from report!",
                                "restore_report_section": "Section restored to report!",
                                "rewrite_report_text": "Text updated!",
                                "customize_report_style": "Style applied!",
                                "rebuild_report_html": "Report rebuilt!",
                                "undo_report_edit": "Edit undone — previous version restored!",
                            }
                            if resp_name in report_tool_status:
                                # Don't show success status if the tool returned an error
                                _resp_data = getattr(part.function_response, 'response', None)
                                _is_error = isinstance(_resp_data, dict) and _resp_data.get("status") in ("error", "no_report")
                                if not _is_error:
                                    print(f"[STATUS] Tool done: {resp_name} -> '{report_tool_status[resp_name]}'")
                                    yield f"data: {json.dumps({'status': report_tool_status[resp_name]})}\n\n"
                                else:
                                    print(f"[STATUS] Tool done: {resp_name} -> ERROR (suppressing success status)")
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
                                    captured_chart_html += resp_text  # Accumulate for multi-chart
                                    chart_tool_called = True  # Ensure buffering is active
                                    print(f"[STREAM] Captured chart HTML from function_response of '{resp_name}' (total accumulated={len(captured_chart_html)})")

                            # ── Capture report HTML from build_html_report ──
                            if resp_name == "build_html_report":
                                resp_data = getattr(part.function_response, 'response', None)
                                if isinstance(resp_data, dict):
                                    for key in ('result', 'report', 'output', 'response'):
                                        val = resp_data.get(key, '')
                                        if isinstance(val, str) and '<!--REPORT_START-->' in val:
                                            captured_report_html = val
                                            break
                                    if not captured_report_html:
                                        for val in resp_data.values():
                                            if isinstance(val, str) and '<!--REPORT_START-->' in val:
                                                captured_report_html = val
                                                break
                                elif isinstance(resp_data, str) and '<!--REPORT_START-->' in resp_data:
                                    captured_report_html = resp_data
                                if captured_report_html:
                                    print(f"[STREAM] Captured report HTML from build_html_report (len={len(captured_report_html)})")

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
            # Chart configs are sent as separate SSE fields so the frontend
            # never needs to parse them from innerHTML.
            # Supports multi-chart: multiple <!--CHART_START--> blocks per message.
            # For multi-chart, inline placeholders (<!--CHART_PLACEHOLDER:N-->)
            # are left in the HTML so the frontend can render chart-text-chart-text.
            chart_configs = []  # List of compact JSON strings

            # --- Extract charts from all available sources ---
            def _extract_charts_from_html(html_source: str, source_label: str) -> list:
                """Extract chart JSON configs from HTML with CHART delimiters."""
                configs = []
                matches = re.findall(
                    r'<!--CHART_START-->\s*(.*?)\s*<!--CHART_END-->',
                    html_source, re.DOTALL,
                )
                for m in matches:
                    try:
                        obj = json.loads(m)
                        configs.append(json.dumps(obj, separators=(',', ':')))
                    except Exception:
                        configs.append(m.replace('\n', ' '))
                if configs:
                    print(f"[CHART INJECT] {source_label}: extracted {len(configs)} chart(s)")
                return configs

            if chart_tool_called:
                # Source 1: function_response events (most reliable)
                if captured_chart_html:
                    chart_configs = _extract_charts_from_html(captured_chart_html, "function_response")

                # Source 2: streamed/final text contains chart JSON inline
                if not chart_configs and raw_text and contains_chart_json(raw_text):
                    # Ensure orphaned chart JSON gets wrapped with delimiters
                    raw_text = ensure_chart_delimiters(raw_text)
                    chart_configs = _extract_charts_from_html(raw_text, "streamed_text")

                # Source 3: session state accumulator (last_chart_outputs list)
                if not chart_configs:
                    stored_list = s_state.get("last_chart_outputs") or []
                    if isinstance(stored_list, str):
                        stored_list = [stored_list]
                    if stored_list:
                        print(f"[CHART INJECT] Fallback: session state last_chart_outputs ({len(stored_list)} items)")
                        for sj in stored_list:
                            try:
                                obj = json.loads(sj)
                                chart_configs.append(json.dumps(obj, separators=(',', ':')))
                            except Exception:
                                chart_configs.append(sj.replace('\n', ' '))

                # Source 4: legacy single chart in session state
                if not chart_configs:
                    stored_chart_json = s_state.get("last_chart_output")
                    if stored_chart_json:
                        print(f"[CHART INJECT] Fallback: session state last_chart_output (len={len(stored_chart_json)})")
                        try:
                            obj = json.loads(stored_chart_json)
                            chart_configs.append(json.dumps(obj, separators=(',', ':')))
                        except Exception:
                            chart_configs.append(stored_chart_json.replace('\n', ' '))

                # Now process raw_text: replace chart blocks with placeholders or strip
                if chart_configs and raw_text:
                    if len(chart_configs) > 1:
                        placeholder_idx = 0
                        while '<!--CHART_START-->' in raw_text and '<!--CHART_END-->' in raw_text:
                            s = raw_text.index('<!--CHART_START-->')
                            e = raw_text.index('<!--CHART_END-->') + len('<!--CHART_END-->')
                            raw_text = raw_text[:s] + f'<!--CHART_PLACEHOLDER:{placeholder_idx}-->' + raw_text[e:]
                            placeholder_idx += 1
                        raw_text = _strip_chart_json_from_text(raw_text)
                        print(f"[MULTI-CHART] Inserted {placeholder_idx} placeholders into HTML")
                    else:
                        before_len = len(raw_text)
                        raw_text = _strip_chart_json_from_text(raw_text)
                        print(f"[STRIP] raw_text {before_len} -> {len(raw_text)} chars")

            # ── Report HTML extraction ──
            report_html_str = ""
            if captured_report_html:
                _rm = re.search(r'<!--REPORT_START-->(.*?)<!--REPORT_END-->', captured_report_html, re.DOTALL)
                if _rm:
                    report_html_str = _rm.group(1).strip()
                    print(f"[REPORT INJECT] Extracted report HTML from function_response ({len(report_html_str)} chars)")
            # Fallback: check raw_text for report delimiters
            if not report_html_str and raw_text and '<!--REPORT_START-->' in raw_text:
                _rm = re.search(r'<!--REPORT_START-->(.*?)<!--REPORT_END-->', raw_text, re.DOTALL)
                if _rm:
                    report_html_str = _rm.group(1).strip()
                    print(f"[REPORT INJECT] Extracted report HTML from raw_text ({len(report_html_str)} chars)")
            # Fallback: read from session state (when report_generator runs as AgentTool,
            # internal tool responses aren't visible in the event stream)
            # ONLY use this fallback if report_generator was actually called this request
            if not report_html_str and (report_tool_called or report_editor_called):
                stored_report = s_state.get("last_report_html")
                if stored_report and isinstance(stored_report, str) and len(stored_report) > 100:
                    report_html_str = stored_report
                    source = "report_editor" if report_editor_called else "report_generator"
                    print(f"[REPORT INJECT] Fallback: session state last_report_html via {source} ({len(report_html_str)} chars)")
            # Strip report delimiters from raw_text so chat bubble only shows summary
            if report_html_str and raw_text:
                raw_text = re.sub(r'<!--REPORT_START-->.*?<!--REPORT_END-->', '', raw_text, flags=re.DOTALL).strip()

            if raw_text:
                # Strip [Chart rendered: ...] context notes — they're for LLM context only
                raw_text = re.sub(r'\[Chart rendered:.*?\]', '', raw_text).strip()
                # If no charts were extracted, try wrapping orphaned chart JSON
                # BEFORE _md_to_html() — HTML conversion corrupts * in JSON
                if not chart_configs:
                    raw_text = ensure_chart_delimiters(raw_text)
                clean_text = _md_to_html(raw_text)
            else:
                clean_text = ""

            # Send HTML + chartConfig(s) + reportHtml as separate fields in the SSE event
            if clean_text or chart_configs or report_html_str:
                event_data = {}
                # Validate chart configs
                validated_configs = []
                for cfg in chart_configs:
                    if cfg and len(cfg) > 10:
                        try:
                            json.loads(cfg)  # Validate it's real JSON
                            validated_configs.append(cfg)
                        except (json.JSONDecodeError, ValueError):
                            logger.warning("[CHART INJECT] Invalid chart JSON, skipping: %s", cfg[:50])

                # For multi-chart: embed chart blocks inline in HTML at placeholder
                # positions so the frontend renders chart → text → chart → text.
                # The frontend already parses <!--CHART_START-->...<!--CHART_END-->
                # blocks in HTML content, so no frontend changes needed.
                if len(validated_configs) > 1 and clean_text and '<!--CHART_PLACEHOLDER:' in clean_text:
                    for i, cfg in enumerate(validated_configs):
                        clean_text = clean_text.replace(
                            f'<!--CHART_PLACEHOLDER:{i}-->',
                            f'<!--CHART_START-->{cfg}<!--CHART_END-->',
                        )
                    event_data['html'] = clean_text
                    # Do NOT send chartConfigs separately — charts are inline in HTML.
                    # Frontend will parse <!--CHART_START--> blocks from innerHTML.
                    print(f"[MULTI-CHART] Embedded {len(validated_configs)} charts inline in HTML")
                elif clean_text:
                    event_data['html'] = clean_text
                    # Single chart: send as separate field (backward compatible)
                    if len(validated_configs) == 1:
                        event_data['chartConfig'] = validated_configs[0]
                    elif len(validated_configs) > 1:
                        event_data['chartConfigs'] = validated_configs
                # Send report HTML as separate field for artifact panel
                if report_html_str:
                    event_data['reportHtml'] = report_html_str
                logger.debug("[SSE EVENT] html=%dchars, charts=%d, reportHtml=%dchars",
                             len(clean_text), len(validated_configs), len(report_html_str))
                yield f"data: {json.dumps(event_data)}\n\n"

            # ── Persist the clean assistant response ──
            # For multi-chart, charts are already embedded inline in clean_text
            # (placeholders replaced above). For single chart, append to end.
            db_content = clean_text
            charts_already_inline = (
                len(validated_configs) > 1
                and '<!--CHART_START-->' in db_content
            )
            if not charts_already_inline:
                # Single chart or no placeholders: append chart blocks at end
                for cfg in validated_configs:
                    db_content += f"<!--CHART_START-->{cfg}<!--CHART_END-->"
            # Prepare report data for dedicated DB columns (not embedded in Content)
            db_report_html = report_html_str if report_html_str else None
            db_report_model_json = None
            if report_html_str:
                _model = s_state.get("report_model")
                if _model:
                    try:
                        db_report_model_json = json.dumps(_model, default=str)
                    except Exception:
                        pass  # Non-critical — editing will have limited functionality
            if db_content and db_user_id is not None:
                save_message(
                    session_id, "assistant", db_content,
                    report_html=db_report_html,
                    report_model_json=db_report_model_json,
                )
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

        # ── Persist assistant response (with report columns if applicable) ──
        ns_report_html = None
        ns_report_model_json = None
        try:
            ns_session = await session_service.get_session(
                app_name="oip_assistant", user_id=user_id, session_id=session_id,
            )
            if ns_session:
                ns_rhtml = ns_session.state.get("last_report_html")
                ns_model = ns_session.state.get("report_model")
                if ns_rhtml:
                    ns_report_html = ns_rhtml
                if ns_model:
                    ns_report_model_json = json.dumps(ns_model, default=str)
        except Exception:
            pass
        if response_text and db_user_id is not None:
            save_message(
                session_id, "assistant", response_text,
                report_html=ns_report_html,
                report_model_json=ns_report_model_json,
            )
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
