# main.py - FastAPI server for ADK agent
# Run with: uvicorn main:app --host 0.0.0.0 --port 8080
# Or: python main.py

import json
import logging
import os
import uuid
from typing import Any, Optional, List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

logger = logging.getLogger("oip_chat_agent")

from my_agent import root_agent
from my_agent.tools.chat_history import (
    get_user_id_by_username,
    ensure_session,
    save_message,
    update_session_title,
    get_sessions,
    get_session_messages,
    delete_session,
)

# Initialize FastAPI app
app = FastAPI(title="OIP Chat Agent API", version="1.0.0")

# CORS — restrict to known frontend origins
ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,https://eco.onasi.care",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "GET", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Session service to manage conversation state
session_service = InMemorySessionService()

# Runner to execute the agent
runner = Runner(
    agent=root_agent,
    app_name="oip_assistant",
    session_service=session_service,
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
                    if hasattr(part, "text") and part.text:
                        response_text = part.text  # Use last final response

    return ChatResponse(response=response_text, session_id=session_id)


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
        # SSE streaming response with status updates
        async def event_generator():
            # Send initial status
            yield f"data: {json.dumps({'status': 'Analyzing your request...'})}\n\n"

            last_agent = None
            last_tool = None
            final_response_text = ""

            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_content,
            ):
                # Track agent transfers for status updates
                if hasattr(event, 'author') and event.author:
                    agent_name = event.author
                    if agent_name != last_agent:
                        last_agent = agent_name
                        # Map agent names to friendly status messages
                        status_map = {
                            "oip_assistant": "Processing your request...",
                            "oip_expert": "Consulting OIP documentation...",
                            "ticket_analytics": "Checking ticket data...",
                            "greeter": "Preparing response...",
                        }
                        status = status_map.get(agent_name, f"Working on it...")
                        yield f"data: {json.dumps({'status': status})}\n\n"

                # Track tool calls for status updates
                if hasattr(event, 'content') and event.content:
                    for part in event.content.parts if event.content.parts else []:
                        if hasattr(part, 'function_call') and part.function_call:
                            tool_name = part.function_call.name
                            if tool_name != last_tool:
                                last_tool = tool_name
                                tool_status_map = {
                                    "search_oip_documents": "Searching documentation...",
                                    "get_ticket_summary": "Fetching your tickets...",
                                    "get_current_date": "Getting date info...",
                                    # Chart tools
                                    "create_chart_from_session": "Generating visualization...",
                                    "create_chart": "Creating chart...",
                                    "create_ticket_status_chart": "Building status chart...",
                                    "create_completion_rate_gauge": "Creating completion gauge...",
                                    "create_tickets_over_time_chart": "Plotting trend chart...",
                                    "create_project_comparison_chart": "Building comparison chart...",
                                }
                                status = tool_status_map.get(tool_name, "Processing...")
                                logger.debug("[TOOL CALL] %s -> %s", tool_name, status)
                                yield f"data: {json.dumps({'status': status})}\n\n"

                # Send final response
                if event.is_final_response():
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, "text") and part.text:
                                final_response_text = part.text
                                data = {"text": part.text}
                                yield f"data: {json.dumps(data)}\n\n"

            # ── Persist assistant response ──
            if final_response_text and db_user_id is not None:
                save_message(session_id, "assistant", final_response_text)

            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
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
                        if hasattr(part, "text") and part.text:
                            response_text = part.text

        # ── Persist assistant response ──
        if response_text and db_user_id is not None:
            save_message(session_id, "assistant", response_text)

        return {
            "response": response_text,
            "sessionId": session_id,
            "userId": user_id,
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
