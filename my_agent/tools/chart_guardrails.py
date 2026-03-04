"""Chart output guardrails for OIP Assistant.

Ensures chart JSON is always wrapped in <!--CHART_START--> / <!--CHART_END-->
delimiters, even when the LLM strips them from tool output.

Two layers:
  1. ADK after_model_callback on each chart-capable agent (Layer 1)
  2. Post-processor in main.py as a safety net (Layer 2)
"""

import json
import logging
import re
from typing import Optional

logger = logging.getLogger("oip_chat_agent")

# Known chart types that our chart tools produce
KNOWN_CHART_TYPES = {
    "bar", "pie", "donut", "line", "area",
    "stackedBar", "groupedBar", "gauge", "radialBar",
}

# Regex to find JSON starting with {"type": "<chart_type>"
_CHART_TYPE_PATTERN = re.compile(
    r'\{\s*"type"\s*:\s*"(' + "|".join(KNOWN_CHART_TYPES) + r')"'
)


def _extract_json_object(text: str, start_idx: int) -> Optional[str]:
    """Extract a complete JSON object from text starting at start_idx using brace counting."""
    if start_idx >= len(text) or text[start_idx] != "{":
        return None

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start_idx, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == "\\" and in_string:
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start_idx : i + 1]

    return None  # Unbalanced braces


def ensure_chart_delimiters(text: str) -> str:
    """Scan text for chart JSON missing <!--CHART_START--> delimiters and re-wrap.

    Returns the text unchanged if delimiters are already present,
    or with orphaned chart JSON re-wrapped.
    """
    if not text:
        return text

    # If delimiters already present, no action needed
    if "<!--CHART_START-->" in text:
        return text

    # Search for chart JSON patterns
    match = _CHART_TYPE_PATTERN.search(text)
    if not match:
        return text  # No chart JSON found

    # Found a potential chart JSON — extract the complete JSON object
    start_idx = match.start()
    chart_json = _extract_json_object(text, start_idx)

    if not chart_json:
        return text  # Could not extract valid JSON

    # Validate it's actual chart data
    try:
        parsed = json.loads(chart_json)
        if "data" not in parsed and "value" not in parsed:
            return text  # Not a real chart object
    except json.JSONDecodeError:
        return text  # Not valid JSON

    # Re-wrap with delimiters
    end_idx = start_idx + len(chart_json)
    wrapped = f"<!--CHART_START-->\n{chart_json}\n<!--CHART_END-->"

    fixed_text = text[:start_idx] + wrapped + text[end_idx:]

    logger.info(
        "[CHART GUARDRAIL] Re-wrapped orphaned chart JSON with delimiters (type=%s)",
        parsed.get("type"),
    )

    return fixed_text


def fix_chart_output(callback_context, llm_response):
    """ADK after_model_callback that ensures chart delimiters are present.

    Registered on LlmAgent instances that have chart tools.
    Intercepts LLM responses before they leave the agent.

    Args:
        callback_context: ADK CallbackContext (unused but required by signature).
        llm_response: The LLM response to inspect/fix.

    Returns:
        Modified llm_response if chart JSON was re-wrapped, None otherwise.
    """
    if llm_response is None:
        return None

    content = getattr(llm_response, "content", None)
    if content is None:
        return None

    parts = getattr(content, "parts", None)
    if not parts:
        return None

    modified = False
    for part in parts:
        text = getattr(part, "text", None)
        if not text:
            continue

        fixed = ensure_chart_delimiters(text)
        if fixed != text:
            part.text = fixed
            modified = True

    return llm_response if modified else None
