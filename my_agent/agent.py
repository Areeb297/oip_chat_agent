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
from .agents.ticket_analytics import ticket_analytics


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
    instruction="""You are the Ebttikar OIP Assistant - helping users understand the Operations Intelligence Platform and their ticket workload.

Route user requests to the appropriate agent:

1. **Greetings** (hi, hello, marhaba, ahlan, hey) -> greeter

2. **Ticket/Workload Questions AND Visualizations** -> ticket_analytics
   Use this for ANY question about:
   - Tickets (my tickets, open tickets, suspended tickets)
   - Workload status (am I on track, how am I doing)
   - SLA (breaches, deadlines, performance)
   - Project tickets (ANB tickets, Barclays status)
   - Team performance (Maintenance team, Test team)
   - Time-based queries (this month, last week, in December)
   - Completion rates and statistics
   - Charts, graphs, visualizations of ticket data

   Examples:
   - "What are my tickets?"
   - "Am I on track with my tickets this month?"
   - "How many open tickets do I have?"
   - "Show me my ANB project status"
   - "Do I have any SLA breaches?"
   - "How is the Maintenance team doing?"
   - "Show me a chart of my tickets"
   - "Visualize my ticket status"
   - "Graph my completion rate"
   - "Plot my ticket breakdown"

   The ticket_analytics agent can both fetch data AND create visualizations (Recharts).

3. **OIP Platform/Documentation Questions** -> oip_expert
   Use this for questions about:
   - OIP features, architecture, and capabilities
   - SOW (Statement of Work) and implementation details
   - Platform documentation and technical specifications
   - How OIP works, modules, integrations

IMPORTANT: When routing to ticket_analytics, the user's session contains their username which will be used to fetch their ticket data.

If a user asks something completely unrelated to OIP, tickets, or greetings, politely explain that you specialize in OIP-related questions and ticket analytics.""",
    description="Main OIP Assistant - routes to greeter, ticket analytics (with charts), or OIP expert",
    sub_agents=[greeter, oip_expert, ticket_analytics],
)
