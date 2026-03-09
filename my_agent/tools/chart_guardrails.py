"""Chart output guardrails for OIP Assistant.

Ensures chart JSON is always properly structured and wrapped in
<!--CHART_START--> / <!--CHART_END--> delimiters.

Three validation layers:
  1. Pydantic validation on chart tool output (via OIPToolRetryPlugin)
     — validates structure, triggers ADK reflect-and-retry with feedback
  2. ADK after_model_callback on each chart-capable agent (Layer 1)
     — re-wraps delimiters if LLM strips them
  3. Post-processor in main.py as a safety net (Layer 2)
     — catches anything the first two layers miss
"""

import json
import logging
import re
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, field_validator

logger = logging.getLogger("oip_chat_agent")

# Known chart types that our chart tools produce
KNOWN_CHART_TYPES = {
    "bar", "pie", "donut", "line", "area",
    "stackedBar", "groupedBar", "gauge", "radialBar",
    "bubble", "scatter",
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

    Handles multiple orphaned chart JSON blocks in a single text.
    Returns the text unchanged if all chart blocks already have delimiters.
    """
    if not text:
        return text

    # Find all chart JSON patterns (some may already have delimiters)
    modified = False
    search_start = 0

    while search_start < len(text):
        match = _CHART_TYPE_PATTERN.search(text, search_start)
        if not match:
            break

        start_idx = match.start()

        # Check if this match is already inside delimiters
        preceding = text[:start_idx]
        # Count delimiters before this position — if there's an unclosed CHART_START, skip
        starts_before = preceding.count("<!--CHART_START-->")
        ends_before = preceding.count("<!--CHART_END-->")
        if starts_before > ends_before:
            # Inside an existing delimited block — skip past the next CHART_END
            next_end = text.find("<!--CHART_END-->", start_idx)
            search_start = (next_end + len("<!--CHART_END-->")) if next_end != -1 else len(text)
            continue

        # Found an orphaned chart JSON — extract the complete JSON object
        chart_json = _extract_json_object(text, start_idx)
        if not chart_json:
            search_start = start_idx + 1
            continue

        # Validate it's actual chart data
        try:
            parsed = json.loads(chart_json)
            if "data" not in parsed and "value" not in parsed:
                search_start = start_idx + len(chart_json)
                continue
        except json.JSONDecodeError:
            search_start = start_idx + 1
            continue

        # Re-wrap with delimiters
        end_idx = start_idx + len(chart_json)
        wrapped = f"<!--CHART_START-->\n{chart_json}\n<!--CHART_END-->"
        text = text[:start_idx] + wrapped + text[end_idx:]
        modified = True

        logger.info(
            "[CHART GUARDRAIL] Re-wrapped orphaned chart JSON with delimiters (type=%s)",
            parsed.get("type"),
        )

        # Move past the wrapped block
        search_start = start_idx + len(wrapped)

    return text


# ---------------------------------------------------------------------------
# Chart tool names — used by retry plugin and streaming buffer
# ---------------------------------------------------------------------------
CHART_TOOL_NAMES = {
    "create_chart",
    "create_chart_from_session",
    "create_breakdown_chart",
    "create_pm_chart",
    "create_ticket_status_chart",
    "create_completion_rate_gauge",
    "create_tickets_over_time_chart",
    "create_project_comparison_chart",
    "create_engineer_chart",
    "create_inventory_chart",
}


# ---------------------------------------------------------------------------
# Pydantic Chart Validation
# ---------------------------------------------------------------------------
class ChartOutput(BaseModel):
    """Pydantic model to validate chart JSON from chart tools.

    Validates type is a known chart type and data/value is present.
    Extra fields (title, description, config, etc.) are allowed.
    """

    type: str
    data: Optional[List[Dict]] = None
    value: Optional[float] = None  # For gauge charts

    model_config = {"extra": "allow"}

    @field_validator("type")
    @classmethod
    def validate_chart_type(cls, v: str) -> str:
        if v not in KNOWN_CHART_TYPES:
            raise ValueError(
                f"Invalid chart type '{v}'. "
                f"Must be one of: {', '.join(sorted(KNOWN_CHART_TYPES))}"
            )
        return v

    @field_validator("data")
    @classmethod
    def validate_data_not_empty(cls, v, info):
        chart_type = info.data.get("type", "")
        if chart_type == "gauge":
            return v  # Gauge uses 'value' instead of 'data'
        if not v or len(v) == 0:
            raise ValueError(
                "Chart 'data' array is empty — no data points to visualize. "
                "Ensure the data source has valid entries before charting."
            )
        return v


def contains_chart_json(text: str) -> bool:
    """Quick check whether text contains a chart JSON pattern."""
    if not text:
        return False
    return bool(_CHART_TYPE_PATTERN.search(text))


def validate_chart_output(raw_output: str) -> Tuple[bool, str]:
    """Validate a chart tool's output using Pydantic.

    Returns:
        (is_valid, error_feedback)
        - is_valid: True if chart output is properly structured
        - error_feedback: Descriptive error for LLM retry (empty if valid)
    """
    if not raw_output or not isinstance(raw_output, str):
        return False, "Chart tool returned empty output. Call the chart tool again."

    # Must have delimiters
    if "<!--CHART_START-->" not in raw_output:
        return False, (
            "Chart output is missing <!--CHART_START--> / <!--CHART_END--> delimiters. "
            "The chart JSON MUST be wrapped in these HTML comment delimiters."
        )

    # Extract JSON between delimiters
    match = re.search(
        r"<!--CHART_START-->\s*(\{.*?\})\s*<!--CHART_END-->",
        raw_output,
        re.DOTALL,
    )
    if not match:
        return False, (
            "Could not extract valid JSON between <!--CHART_START--> and "
            "<!--CHART_END--> delimiters. Ensure the JSON is complete and properly enclosed."
        )

    json_str = match.group(1)

    # Parse JSON
    try:
        chart_dict = json.loads(json_str)
    except json.JSONDecodeError as e:
        return False, f"Chart JSON is malformed: {e}. Fix the JSON syntax and retry."

    # Validate with Pydantic
    try:
        ChartOutput(**chart_dict)
    except Exception as e:
        return False, f"Chart validation failed: {e}"

    logger.debug("[CHART VALIDATE] Pydantic validation passed (type=%s, points=%d)",
                 chart_dict.get("type"), len(chart_dict.get("data", [])))
    return True, ""


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
