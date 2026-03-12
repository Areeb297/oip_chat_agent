"""Follow-up suggestion generation for the OIP chatbot.

Produces 3-4 contextual follow-up questions after each agent response.
Uses a hybrid approach: rule-based defaults with optional LLM boost.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("oip_chat_agent")

# ---------------------------------------------------------------------------
# Rule-based suggestion maps
# ---------------------------------------------------------------------------

_GREETER_SUGGESTIONS = [
    "What are my open tickets?",
    "Show me my SLA status",
    "What is the OIP platform?",
    "How do I create a ticket?",
]

_TICKET_SUMMARY_SUGGESTIONS = [
    "Chart the above data",
    "Compare to last month",
    "Show breakdown by project",
    "Any SLA breaches?",
]

_TICKET_CHART_SUGGESTIONS = [
    "Show a different chart type",
    "Break down by team",
    "How does this compare to last month?",
    "What are my SLA breaches?",
]

_TICKET_SLA_SUGGESTIONS = [
    "Which projects breach the most?",
    "Show SLA trend over time",
    "What is the overall completion rate?",
    "Chart the SLA data",
]

_TICKET_BREAKDOWN_SUGGESTIONS = [
    "Chart this breakdown",
    "Show a pie chart",
    "Compare across all projects",
    "What are my SLA breaches?",
]

_TICKET_DEFAULT_SUGGESTIONS = [
    "Show me a chart",
    "What are my SLA breaches?",
    "Compare my projects",
    "Show ticket trend over time",
]

_OIP_EXPERT_SUGGESTIONS = [
    "How does ticket approval work?",
    "What are the OIP modules?",
    "How is SLA calculated?",
    "What are my open tickets?",
]

_ENGINEER_SUGGESTIONS = [
    "Chart daily activity logs",
    "Show work hours by engineer",
    "Which certifications are expiring?",
    "Show engineer performance by team",
]

_ENGINEER_CHART_SUGGESTIONS = [
    "Show a different metric",
    "Compare engineers by completion rate",
    "Show daily logs breakdown",
    "Which certifications are expiring?",
]

_ENGINEER_ACTIVITY_SUGGESTIONS = [
    "Chart the daily activity logs",
    "Show total hours per engineer",
    "Distance travelled by engineers",
    "Show ticket performance too",
]

_INVENTORY_SUGGESTIONS = [
    "Chart consumption by site",
    "Which parts consumed the most?",
    "Show consumption by category",
    "Parts returned this month",
]

_INVENTORY_CHART_SUGGESTIONS = [
    "Show a pie chart instead",
    "Break down by category",
    "Show consumption by project",
    "Compare to last month",
]

_REPORT_SUGGESTIONS = [
    "Remove a KPI card from the report",
    "Rewrite the executive summary",
    "Hide the inventory section",
    "Change report colors or styling",
]

_GENERIC_SUGGESTIONS = [
    "What are my open tickets?",
    "Show engineer daily logs",
    "What is the OIP platform?",
    "Check spare parts consumption",
]


def _get_rule_based_suggestions(
    agent_name: str,
    agent_response: str,
    session_state: Optional[Dict],
) -> List[str]:
    """Build rule-based suggestions from agent type and session context."""

    # Report-specific: if a report was just generated, suggest editing actions
    state = session_state or {}
    has_report = bool(state.get("last_report_html"))
    if has_report and (
        agent_name in ("report_generator", "report_editor")
        or "report" in (agent_response or "").lower()[:200]
        or "<!--REPORT_START-->" in (agent_response or "")
    ):
        return list(_REPORT_SUGGESTIONS)

    if agent_name == "greeter":
        return list(_GREETER_SUGGESTIONS)

    if agent_name == "oip_expert":
        return list(_OIP_EXPERT_SUGGESTIONS)

    if agent_name == "ticket_analytics":
        state = session_state or {}
        last_query = state.get("last_query_type", "")
        last_data = state.get("last_ticket_data") or {}
        has_chart = "<!--CHART_START-->" in (agent_response or "")

        # Post-chart suggestions
        if has_chart:
            suggestions = list(_TICKET_CHART_SUGGESTIONS)
        elif last_query == "ticket_summary":
            suggestions = list(_TICKET_SUMMARY_SUGGESTIONS)
        else:
            suggestions = list(_TICKET_DEFAULT_SUGGESTIONS)

        # Dynamic: inject SLA question if breaches exist
        sla_breached = last_data.get("SLABreached", 0)
        if sla_breached and sla_breached > 0:
            # Replace a generic item with an SLA-specific one if not already present
            sla_q = f"Which tickets breached SLA? ({sla_breached} found)"
            if len(sla_q) > 60:
                sla_q = "Show me SLA-breached tickets"
            if not any("sla" in s.lower() or "SLA" in s for s in suggestions):
                suggestions[-1] = sla_q

        # Dynamic: if multiple projects, suggest comparison
        projects_csv = state.get("projectCode", "")
        if projects_csv and "," in projects_csv:
            compare_q = "Compare my projects side by side"
            if not any("compare" in s.lower() for s in suggestions):
                suggestions[2] = compare_q

        return suggestions[:4]

    if agent_name == "engineer_analytics":
        has_chart = "<!--CHART_START-->" in (agent_response or "")
        has_activity = "activity" in (agent_response or "").lower() or "daily log" in (agent_response or "").lower()

        if has_chart:
            return list(_ENGINEER_CHART_SUGGESTIONS)
        elif has_activity:
            return list(_ENGINEER_ACTIVITY_SUGGESTIONS)
        else:
            return list(_ENGINEER_SUGGESTIONS)

    if agent_name == "inventory_analytics":
        has_chart = "<!--CHART_START-->" in (agent_response or "")
        if has_chart:
            return list(_INVENTORY_CHART_SUGGESTIONS)
        return list(_INVENTORY_SUGGESTIONS)

    return list(_GENERIC_SUGGESTIONS)


async def _generate_suggestions_llm(
    user_message: str,
    agent_response: str,
    agent_name: str,
    session_state: Optional[Dict],
) -> Optional[List[str]]:
    """Try to generate suggestions via LLM with a timeout. Returns None on failure."""
    try:
        import litellm
        from ..config import (
            OPENROUTER_API_KEY,
            OPENROUTER_BASE_URL,
            SuggestionsConfig,
        )
        from ..prompts.templates import Prompts

        if not SuggestionsConfig.USE_LLM:
            return None

        # Agent scope descriptions for context
        agent_scope = {
            "greeter": "Greets users. Can direct to ticket queries, engineer data, inventory, or OIP docs.",
            "ticket_analytics": "Ticket status, SLA, workload, completion rates, breakdowns by project/team/region, PM checklists, charts.",
            "engineer_analytics": "Engineer performance, daily activity logs (hours, distance, activity types), certifications, engineer charts.",
            "inventory_analytics": "Spare parts consumption, parts per site/category/project, inventory charts.",
            "oip_expert": "OIP platform documentation, how-to guides, system modules, workflows.",
            "report_generator": "Generated a report. User can edit sections, remove KPI cards, rewrite text, hide sections, or download as Word.",
            "report_editor": "Editing a report. User can make further edits, undo changes, or download.",
        }

        # Build user context snippet
        context_parts = [f"Agent: {agent_name}"]
        scope = agent_scope.get(agent_name, "General OIP assistant")
        context_parts.append(f"Scope: {scope}")
        if session_state:
            projects = session_state.get("projectCode", "")
            if projects:
                context_parts.append(f"Projects: {projects}")
            teams = session_state.get("team", "")
            if teams:
                context_parts.append(f"Teams: {teams}")
        context_line = " | ".join(context_parts)

        user_prompt = (
            f"User question: {user_message[:300]}\n"
            f"Assistant response (excerpt): {agent_response[:500]}\n"
            f"Context: {context_line}"
        )

        response = await asyncio.wait_for(
            litellm.acompletion(
                model=f"openrouter/{SuggestionsConfig.LLM_MODEL}",
                messages=[
                    {"role": "system", "content": Prompts.suggestions_prompt()},
                    {"role": "user", "content": user_prompt},
                ],
                api_key=OPENROUTER_API_KEY,
                api_base=OPENROUTER_BASE_URL,
                max_tokens=SuggestionsConfig.LLM_MAX_TOKENS,
                temperature=SuggestionsConfig.LLM_TEMPERATURE,
            ),
            timeout=SuggestionsConfig.LLM_TIMEOUT,
        )

        raw = response.choices[0].message.content.strip()
        # Handle cases where LLM wraps JSON in markdown code block
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        suggestions = json.loads(raw)

        if isinstance(suggestions, list) and len(suggestions) >= 3:
            # Enforce max length per suggestion and max count
            return [
                s[:80] for s in suggestions[:SuggestionsConfig.MAX_SUGGESTIONS]
                if isinstance(s, str) and s.strip()
            ]

        logger.debug("[SUGGESTIONS] LLM returned invalid format: %s", raw[:200])
        return None

    except asyncio.TimeoutError:
        logger.debug("[SUGGESTIONS] LLM timed out, falling back to rule-based")
        return None
    except Exception as e:
        logger.debug("[SUGGESTIONS] LLM failed: %s", e)
        return None


async def generate_suggestions(
    user_message: str,
    agent_response: str,
    agent_name: str,
    session_state: Optional[Dict] = None,
) -> List[str]:
    """Generate 3-4 follow-up suggestions (main entry point).

    Always builds rule-based first, then tries LLM boost with timeout.
    Returns rule-based on any LLM failure.
    """
    from ..config import SuggestionsConfig

    if not SuggestionsConfig.ENABLED:
        return []

    # Always have rule-based ready as fallback
    rule_based = _get_rule_based_suggestions(agent_name, agent_response, session_state)

    # Try LLM for more contextual suggestions
    llm_result = await _generate_suggestions_llm(
        user_message, agent_response, agent_name, session_state
    )

    if llm_result and len(llm_result) >= 3:
        logger.debug("[SUGGESTIONS] Using LLM result: %s", llm_result)
        return llm_result

    logger.debug("[SUGGESTIONS] Using rule-based for agent=%s", agent_name)
    return rule_based
