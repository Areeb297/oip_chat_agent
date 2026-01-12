"""
Ebttikar OIP Assistant Agent

A focused agent system for the Operations Intelligence Platform (OIP).
Uses Google ADK with RAG capabilities for document-based Q&A.

Supports two model backends:
1. Google Gemini (default) - uses GOOGLE_API_KEY
2. OpenRouter (via LiteLLM) - uses OPENROUTER_API_KEY, no quota limits

Set USE_OPENROUTER=true in .env to use OpenRouter instead of Google.
"""
import os
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from .prompts.templates import Prompts
from .tools.rag_tool import search_oip_documents


# =============================================================================
# MODEL CONFIGURATION
# =============================================================================

# Check if user wants to use OpenRouter instead of Google
USE_OPENROUTER = os.getenv("USE_OPENROUTER", "false").lower() == "true"

if USE_OPENROUTER:
    # Use OpenRouter via LiteLLM (no quota limits, pay-per-use)
    # Available models: x-ai/grok-4.1-fast, google/gemini-2.5-flash-preview-09-2025
    AGENT_MODEL = LiteLlm(model="openrouter/x-ai/grok-4.1-fast")
    print("Using OpenRouter backend (x-ai/grok-4.1-fast)")
else:
    # Use Google Gemini directly (free tier: 20 requests/day)
    AGENT_MODEL = "gemini-2.5-flash"
    print("Using Google Gemini backend (gemini-2.5-flash)")


# =============================================================================
# SUB-AGENTS
# =============================================================================

greeter = LlmAgent(
    name="greeter",
    model=AGENT_MODEL,
    instruction="""You are a friendly assistant for Ebttikar's OIP platform.
Greet users warmly in Arabic or English based on their language.
- Arabic greetings: Marhaba, Ahlan wa sahlan
- English greetings: Hello, Welcome

After greeting, briefly mention you can help with OIP platform questions.""",
    description="Handles greetings and welcomes users to OIP Assistant",
)

oip_expert = LlmAgent(
    name="oip_expert",
    model=AGENT_MODEL,
    instruction=Prompts.oip_assistant_system(),
    description="Expert on Ebttikar OIP platform - answers questions using document search",
    tools=[search_oip_documents],
)


# =============================================================================
# ROOT AGENT
# =============================================================================

root_agent = LlmAgent(
    name="oip_assistant",
    model=AGENT_MODEL,
    instruction="""You are the Ebttikar OIP Assistant - helping users understand the Operations Intelligence Platform.

Route user requests to the appropriate agent:

- Greetings (hi, hello, marhaba, ahlan, hey) -> greeter
- ALL questions about OIP, platform features, SOW, implementation, technical details -> oip_expert

The oip_expert agent has access to internal OIP documentation and will search for relevant information.

If a user asks something completely unrelated to OIP or greetings, politely explain that you specialize in OIP-related questions.""",
    description="Main OIP Assistant - routes to greeter or OIP expert",
    sub_agents=[greeter, oip_expert],
)
