# main.py - FastAPI server for ADK agent
# Run with: uvicorn main:app --host 0.0.0.0 --port 8080
# Or: python main.py

import json
import uuid
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from my_agent import root_agent

# Initialize FastAPI app
app = FastAPI(title="OIP Chat Agent API", version="1.0.0")

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session service to manage conversation state
session_service = InMemorySessionService()

# Runner to execute the agent
runner = Runner(
    agent=root_agent,
    app_name="oip_assistant",
    session_service=session_service,
)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


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

    class Config:
        populate_by_name = True


@app.get("/health")
def health_check():
    """Health check endpoint for load balancers"""
    return {"status": "healthy"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to the OIP Assistant and get a response"""
    # Create or reuse session
    session_id = request.session_id or str(uuid.uuid4())
    user_id = "default_user"

    # Get or create session (async methods)
    session = await session_service.get_session(
        app_name="oip_assistant",
        user_id=user_id,
        session_id=session_id,
    )
    if session is None:
        session = await session_service.create_session(
            app_name="oip_assistant",
            user_id=user_id,
            session_id=session_id,
        )

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


@app.post("/run_sse")
async def run_sse(request: RunSSERequest):
    """ADK-compatible endpoint for running agent (matches adk web format)"""
    user_id = request.userId
    session_id = request.sessionId

    # Get or create session (async methods)
    session = await session_service.get_session(
        app_name="oip_assistant",
        user_id=user_id,
        session_id=session_id,
    )
    if session is None:
        session = await session_service.create_session(
            app_name="oip_assistant",
            user_id=user_id,
            session_id=session_id,
        )

    # Extract text from message parts
    message_text = ""
    for part in request.newMessage.parts:
        if part.text:
            message_text += part.text

    # Create user message content
    user_content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=message_text)],
    )

    if request.streaming:
        # SSE streaming response
        async def event_generator():
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_content,
            ):
                if event.is_final_response():
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, "text") and part.text:
                                data = {"text": part.text}
                                yield f"data: {json.dumps(data)}\n\n"
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

        return {
            "response": response_text,
            "sessionId": session_id,
            "userId": user_id,
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
