"""
Report editing tools for the OIP Assistant.

Used by the report_editor LlmAgent to modify an existing report in-place.
All tools read/write the report_model in session state, then call
_rebuild_from_model() to regenerate HTML without re-querying the database.
"""

import copy
import json
import logging
from datetime import datetime
from typing import Optional

from google.adk.tools import ToolContext

from .report_tools import _rebuild_from_model

# Lazy-loaded LLM for AI regeneration
_litellm = None

logger = logging.getLogger("oip_chat_agent")


# =============================================================================
# Helper: get model from session or return error
# =============================================================================

def _get_model(tool_context: ToolContext) -> dict | None:
    """Retrieve report_model from session state."""
    return tool_context.state.get("report_model")


def _save_and_rebuild(model: dict, tool_context: ToolContext, action: str, target: str) -> dict:
    """Snapshot current state (for undo), increment version, log edit, rebuild HTML, save to session."""
    # Save snapshot for undo (deep copy before mutation)
    undo_stack = tool_context.state.get("report_undo_stack", [])
    # Serialize current model as JSON string to keep session state lightweight
    try:
        snapshot = json.dumps(tool_context.state.get("report_model", {}), default=str)
        undo_stack.append(snapshot)
        # Keep last 10 snapshots max
        if len(undo_stack) > 10:
            undo_stack = undo_stack[-10:]
        tool_context.state["report_undo_stack"] = undo_stack
    except Exception:
        pass  # Non-critical — undo just won't work for this edit

    model["version"] = model.get("version", 1) + 1
    model["edit_history"].append({
        "version": model["version"],
        "action": action,
        "target": target,
        "timestamp": datetime.now().isoformat(),
    })

    html = _rebuild_from_model(model)
    tool_context.state["report_model"] = model
    tool_context.state["last_report_html"] = html

    logger.info(f"[REPORT EDIT] v{model['version']}: {action} → {target} ({len(html)} chars)")
    return {
        "status": "success",
        "version": model["version"],
        "html_size": len(html),
    }


# =============================================================================
# TOOL 1: toggle_kpi_card
# =============================================================================

def toggle_kpi_card(
    card_label: str,
    visible: bool = None,
    tool_context: ToolContext = None,
) -> dict:
    """Show or hide a KPI card in the report header row.

    Args:
        card_label: Label of the KPI card to toggle. Valid labels:
            "Total Tickets", "Open Tickets", "Completed", "SLA Breached",
            "PM Tickets", "TR Calls", "Engineers", "Parts Consumed".
            Case-insensitive partial match is supported (e.g., "SLA" matches "SLA Breached").
        visible: True to show the card, False to hide it.
            If not provided, toggles the current state.
    """
    model = _get_model(tool_context)
    if not model:
        return {"status": "no_report", "error_message": "No report exists in this session. Generate a report first."}

    hidden = set(model.get("hidden_kpi_labels", []))

    # Find matching label (case-insensitive partial match)
    all_labels = ["Total Tickets", "Open Tickets", "Completed", "SLA Breached",
                  "PM Tickets", "TR Calls", "Engineers", "Parts Consumed"]
    matched = None
    for label in all_labels:
        if card_label.lower() in label.lower() or label.lower() in card_label.lower():
            matched = label
            break

    if not matched:
        return {
            "status": "error",
            "error_message": f"No KPI card matching '{card_label}'. Available: {', '.join(all_labels)}",
        }

    # Toggle logic
    if visible is None:
        visible = matched in hidden  # If hidden, make visible; if visible, hide

    if visible:
        hidden.discard(matched)
        action_desc = "show_kpi"
    else:
        hidden.add(matched)
        action_desc = "hide_kpi"

    model["hidden_kpi_labels"] = list(hidden)

    result = _save_and_rebuild(model, tool_context, action_desc, matched)
    result["card"] = matched
    result["visible"] = visible
    return result


# =============================================================================
# TOOL 2: remove_report_section
# =============================================================================

# Valid section IDs and their display names
_SECTION_MAP = {
    "tickets": "Ticket Status Overview",
    "ticket_types": "Task Type Breakdown",
    "engineers": "Engineer Performance",
    "certifications": "Certifications",
    "inventory": "Inventory Consumption",
}


def remove_report_section(
    section_id: str,
    tool_context: ToolContext = None,
) -> dict:
    """Remove (hide) a data section from the report. The section can be restored later.

    Note: Executive Summary, Key Insights, and Discussion/Recommendations are text
    sections controlled by rewrite_report_text, not this tool.

    Args:
        section_id: Which section to hide. Valid IDs:
            "tickets" — Ticket Status Overview table
            "ticket_types" — Task Type Breakdown (PM/TR/Other)
            "engineers" — Engineer Performance section
            "certifications" — Certification status section
            "inventory" — Inventory/Spare Parts Consumption section
    """
    model = _get_model(tool_context)
    if not model:
        return {"status": "no_report", "error_message": "No report exists in this session. Generate a report first."}

    # Normalize section_id
    section_id = section_id.lower().strip()

    # Fuzzy match: "inventory consumption" → "inventory", "engineer" → "engineers"
    if section_id not in _SECTION_MAP:
        for sid, name in _SECTION_MAP.items():
            if section_id in sid or section_id in name.lower():
                section_id = sid
                break

    if section_id not in _SECTION_MAP:
        valid = ", ".join(f'"{k}" ({v})' for k, v in _SECTION_MAP.items())
        return {"status": "error", "error_message": f"Unknown section '{section_id}'. Valid sections: {valid}"}

    visible = model.get("visible_sections", [])
    if section_id not in visible:
        return {"status": "success", "message": f"Section '{section_id}' is already hidden.", "version": model.get("version", 1)}

    visible.remove(section_id)
    model["visible_sections"] = visible

    result = _save_and_rebuild(model, tool_context, "hide_section", _SECTION_MAP[section_id])
    result["section_removed"] = section_id
    return result


# =============================================================================
# TOOL 3: restore_report_section
# =============================================================================

def restore_report_section(
    section_id: str,
    tool_context: ToolContext = None,
) -> dict:
    """Restore a previously hidden section back to the report.

    Args:
        section_id: Which section to restore. Same IDs as remove_report_section:
            "tickets", "ticket_types", "engineers", "certifications", "inventory".
    """
    model = _get_model(tool_context)
    if not model:
        return {"status": "no_report", "error_message": "No report exists in this session. Generate a report first."}

    section_id = section_id.lower().strip()
    if section_id not in _SECTION_MAP:
        for sid in _SECTION_MAP:
            if section_id in sid:
                section_id = sid
                break

    if section_id not in _SECTION_MAP:
        valid = ", ".join(_SECTION_MAP.keys())
        return {"status": "error", "error_message": f"Unknown section '{section_id}'. Valid: {valid}"}

    visible = model.get("visible_sections", [])
    if section_id in visible:
        return {"status": "success", "message": f"Section '{section_id}' is already visible.", "version": model.get("version", 1)}

    visible.append(section_id)
    model["visible_sections"] = visible

    result = _save_and_rebuild(model, tool_context, "show_section", _SECTION_MAP[section_id])
    result["section_restored"] = section_id
    return result


# =============================================================================
# TOOL 4: rewrite_report_text
# =============================================================================

def rewrite_report_text(
    section_id: str,
    new_text: str,
    tool_context: ToolContext = None,
) -> dict:
    """Replace the text content of a text-based section in the report.

    The report_editor LLM should generate the new text itself based on the user's
    instruction and the report data, then pass it here. This tool does NOT call
    an LLM — it simply replaces the text and rebuilds.

    Args:
        section_id: Which text section to update. Valid IDs:
            "executive_summary" — The executive summary narrative at the top
            "insights" — Key insights bullets (use pipe-separated format:
                "category:text|category:text" where category is positive/warning/info/achievement)
            "discussion" — Recommendations / discussion section
            "title" — The report title
        new_text: The new text content for the section.
    """
    model = _get_model(tool_context)
    if not model:
        return {"status": "no_report", "error_message": "No report exists in this session. Generate a report first."}

    section_id = section_id.lower().strip()
    valid_text_sections = {"executive_summary", "insights", "discussion", "title"}

    if section_id not in valid_text_sections:
        return {
            "status": "error",
            "error_message": f"Cannot rewrite '{section_id}'. Valid text sections: {', '.join(sorted(valid_text_sections))}",
        }

    old_text = model.get(section_id, "")
    model[section_id] = new_text

    result = _save_and_rebuild(model, tool_context, "rewrite", section_id)
    result["section"] = section_id
    result["old_length"] = len(old_text)
    result["new_length"] = len(new_text)
    return result


# =============================================================================
# TOOL 5: customize_report_style
# =============================================================================

def customize_report_style(
    header_bg: str = None,
    header_border: str = None,
    accent_gradient: str = None,
    section_badge_color: str = None,
    table_header_bg: str = None,
    table_header_text: str = None,
    font_family: str = None,
    title_font: str = None,
    kpi_card_bg: str = None,
    kpi_value_color: str = None,
    tool_context: ToolContext = None,
) -> dict:
    """Customize the visual styling/colors of the current report.

    All parameters are optional — only provided values are changed.
    Colors should be valid CSS values (hex like "#1a4f71" or named colors).

    Args:
        header_bg: Background color of the report header band (default: "#EEF2FF")
        header_border: Bottom border color of the header (default: "#2746E3")
        accent_gradient: CSS gradient for the accent bar under header
            (default: "linear-gradient(90deg, #1D4ED8 0%, #7C3AED 50%, #06B6D4 100%)")
        section_badge_color: Background color of numbered section badges (default: "#2746E3")
        table_header_bg: Background color of table header rows (default: "#0F172A")
        table_header_text: Text color in table headers (default: "#94A3B8")
        font_family: Body font family (default: "'Inter', system-ui, sans-serif")
        title_font: Title/heading font family (default: "'Playfair Display', Georgia, serif")
        kpi_card_bg: Uniform background color for ALL KPI cards (overrides individual card colors).
            Use this when the user says "make KPI cards yellow/blue/etc".
            Set to "default" to restore individual card colors.
        kpi_value_color: Uniform text color for ALL KPI card values (overrides individual colors).
            Set to "default" to restore individual value colors.
    """
    model = _get_model(tool_context)
    if not model:
        return {"status": "no_report", "error_message": "No report exists in this session. Generate a report first."}

    overrides = model.get("style_overrides", {})
    changes = {}

    # Apply only non-None values
    param_map = {
        "header_bg": header_bg,
        "header_border": header_border,
        "accent_gradient": accent_gradient,
        "section_badge_color": section_badge_color,
        "table_header_bg": table_header_bg,
        "table_header_text": table_header_text,
        "font_family": font_family,
        "title_font": title_font,
        "kpi_card_bg": kpi_card_bg,
        "kpi_value_color": kpi_value_color,
    }

    for key, value in param_map.items():
        if value is not None:
            if value.lower() == "default":
                overrides.pop(key, None)
                changes[key] = "(restored to default)"
            else:
                overrides[key] = value
                changes[key] = value

    if not changes:
        return {"status": "error", "error_message": "No style changes provided. Pass at least one parameter."}

    model["style_overrides"] = overrides

    result = _save_and_rebuild(model, tool_context, "style_change", str(changes))
    result["changes"] = changes
    return result


# =============================================================================
# TOOL 6: rebuild_report_html (explicit re-render)
# =============================================================================

def rebuild_report_html(
    tool_context: ToolContext = None,
) -> dict:
    """Force re-render the report HTML from the current report_model.

    Usually called automatically by other edit tools. Can be called explicitly
    to refresh the report after manual session state changes.
    """
    model = _get_model(tool_context)
    if not model:
        return {"status": "no_report", "error_message": "No report exists in this session. Generate a report first."}

    html = _rebuild_from_model(model)
    tool_context.state["last_report_html"] = html

    return {
        "status": "success",
        "version": model.get("version", 1),
        "html_size": len(html),
        "message": "Report re-rendered from current model.",
    }


# =============================================================================
# TOOL 7: undo_report_edit
# =============================================================================

def undo_report_edit(
    tool_context: ToolContext = None,
) -> dict:
    """Undo the last edit to the report, restoring the previous version.

    Each edit (style change, section removal, text rewrite, etc.) saves a snapshot.
    This tool restores the most recent snapshot, effectively undoing the last change.
    Can be called multiple times to undo multiple edits (up to 10 levels).
    """
    model = _get_model(tool_context)
    if not model:
        return {"status": "no_report", "error_message": "No report exists in this session. Generate a report first."}

    undo_stack = tool_context.state.get("report_undo_stack", [])
    if not undo_stack:
        return {
            "status": "no_report",
            "error_message": "Nothing to undo — no previous edits found. The report is at its original version.",
        }

    # Pop the last snapshot and restore it
    snapshot_json = undo_stack.pop()
    tool_context.state["report_undo_stack"] = undo_stack

    try:
        restored_model = json.loads(snapshot_json)
    except (json.JSONDecodeError, Exception):
        return {"status": "no_report", "error_message": "Failed to restore previous version — snapshot corrupted."}

    # Rebuild HTML from restored model
    html = _rebuild_from_model(restored_model)
    tool_context.state["report_model"] = restored_model
    tool_context.state["last_report_html"] = html

    restored_version = restored_model.get("version", 1)
    logger.info(f"[REPORT UNDO] Restored to v{restored_version} ({len(html)} chars)")

    return {
        "status": "success",
        "version": restored_version,
        "html_size": len(html),
        "message": f"Undone! Report restored to version {restored_version}.",
        "remaining_undo_levels": len(undo_stack),
    }


# =============================================================================
# TOOL 8: regenerate_section (AI-powered rewrite)
# =============================================================================

# Section ID → which model key holds the raw data for context
_SECTION_DATA_MAP = {
    "executive_summary": "executive_summary",
    "insights": "insights",
    "discussion": "discussion",
    "title": "title",
    "tickets": "report_data.ticket_totals",
    "ticket_types": "report_data.ticket_types",
    "engineers": "report_data.engineers",
    "certifications": "report_data.certifications",
    "inventory": "report_data.inventory",
}


def _get_section_context(model: dict, section_id: str) -> str:
    """Extract relevant data context for a section to feed to the LLM.

    report_data keys from collect_report_data():
      ticket_totals (dict), ticket_summary (list), ticket_breakdown (list),
      ticket_types (list of dicts), engineers (list), engineer_summary (dict),
      inventory (list), inventory_summary (dict), certifications (list),
      cert_summary (dict), timeline (list)
    """
    rd = model.get("report_data", {})
    ticket_totals = rd.get("ticket_totals", {})
    ticket_types = rd.get("ticket_types", [])
    inv_summary = rd.get("inventory_summary", {})

    if section_id == "executive_summary":
        return json.dumps({
            "current_text": model.get("executive_summary", ""),
            "ticket_totals": ticket_totals,
            "ticket_types": ticket_types,
            "title": model.get("title", ""),
        }, default=str, indent=2)

    elif section_id == "insights":
        return json.dumps({
            "current_insights": model.get("insights", ""),
            "ticket_totals": ticket_totals,
            "engineers": rd.get("engineers", [])[:5],
            "inventory_summary": inv_summary,
        }, default=str, indent=2)

    elif section_id == "discussion":
        return json.dumps({
            "current_text": model.get("discussion", ""),
            "ticket_totals": ticket_totals,
            "engineers": rd.get("engineers", [])[:5],
        }, default=str, indent=2)

    elif section_id == "title":
        return json.dumps({
            "current_title": model.get("title", ""),
            "project_names": rd.get("project_names", ""),
            "team_names": rd.get("team_names", ""),
            "region_names": rd.get("region_names", ""),
        }, default=str, indent=2)

    elif section_id in ("tickets", "ticket_types", "engineers", "certifications", "inventory"):
        key_map = {
            "tickets": "ticket_totals",
            "ticket_types": "ticket_types",
            "engineers": "engineers",
            "certifications": "certifications",
            "inventory": "inventory",
        }
        data = rd.get(key_map[section_id], {})
        # Truncate lists for LLM context
        if isinstance(data, list) and len(data) > 10:
            data = data[:10]
        return json.dumps({
            "section_data": data,
            "current_executive_summary": model.get("executive_summary", ""),
        }, default=str, indent=2)

    return "{}"


async def regenerate_section(
    section_id: str,
    prompt: str,
    tool_context=None,
) -> dict:
    """Use AI to regenerate/rewrite a report section based on a user prompt.

    The LLM reads the section's current content and underlying data, then
    rewrites it according to the user's instruction.

    Args:
        section_id: Which section to regenerate. Text sections get their content
            rewritten directly. Data sections get their narrative portion updated.
            Valid IDs: "executive_summary", "insights", "discussion", "title",
            "tickets", "ticket_types", "engineers", "certifications", "inventory".
        prompt: The user's instruction for how to regenerate the section.
            Examples: "Make it more concise", "Add more detail about SLA",
            "Rewrite in a more formal tone", "Focus on the negative trends".
    """
    global _litellm
    model = _get_model(tool_context)
    if not model:
        return {"status": "no_report", "error_message": "No report exists in this session. Generate a report first."}

    section_id = section_id.lower().strip()

    # Text sections can be directly rewritten
    text_sections = {"executive_summary", "insights", "discussion", "title"}
    # Data sections — we rewrite the executive_summary portion about them
    data_sections = {"tickets", "ticket_types", "engineers", "certifications", "inventory"}
    all_valid = text_sections | data_sections

    if section_id not in all_valid:
        return {
            "status": "error",
            "error_message": f"Cannot regenerate '{section_id}'. Valid sections: {', '.join(sorted(all_valid))}",
        }

    # Get context data for the LLM
    context_data = _get_section_context(model, section_id)

    # Build the system prompt based on section type
    if section_id == "title":
        system_prompt = (
            "You are a report title editor. Given the current title and context, "
            "generate a new title based on the user's instruction. "
            "Return ONLY the new title text, nothing else. Keep it under 80 characters."
        )
    elif section_id == "insights":
        system_prompt = (
            "You are a report insights editor for an operations/ticketing system report. "
            "Given the current insights and report data, regenerate the insights based on the user's instruction. "
            "Return insights in pipe-separated format: category:text|category:text "
            "where category is one of: positive, warning, info, achievement. "
            "Generate 4-8 insight bullets. Return ONLY the pipe-separated string, nothing else."
        )
    elif section_id in data_sections:
        system_prompt = (
            "You are an executive report writer for an operations/ticketing system. "
            "The user wants to regenerate the executive summary with more focus on the given data section. "
            "Based on the section data and user instruction, write a concise executive summary (3-5 sentences) "
            "covering overall performance with emphasis on this section. "
            "Write in professional, analytical tone. Return ONLY the paragraph text, no HTML tags."
        )
    else:
        system_prompt = (
            "You are an executive report writer for an operations/ticketing system. "
            "Given the current section content and report data, rewrite the section based on the user's instruction. "
            "Write in a professional, analytical tone. "
            "Return ONLY the new text content (plain text, no HTML tags). "
            "For executive summaries, write 3-5 sentences. For discussions, write 2-4 paragraphs."
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"## Current section: {section_id}\n\n"
                f"## Report data context:\n```json\n{context_data}\n```\n\n"
                f"## User instruction:\n{prompt}"
            ),
        },
    ]

    # Call LLM via litellm (same pattern as _generate_session_title)
    try:
        if _litellm is None:
            import litellm
            _litellm = litellm
    except ImportError:
        return {"status": "error", "error_message": "litellm not installed — cannot use AI regeneration."}

    try:
        from my_agent.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, Models

        response = await _litellm.acompletion(
            model=f"openrouter/{Models.GPT4O_MINI}",
            messages=messages,
            api_key=OPENROUTER_API_KEY,
            api_base=OPENROUTER_BASE_URL,
            max_tokens=500,
            temperature=0.7,
        )

        new_text = response.choices[0].message.content.strip()
        if not new_text:
            return {"status": "error", "error_message": "AI returned empty response. Try a different prompt."}

    except Exception as e:
        logger.error(f"[REPORT REGENERATE] LLM call failed: {e}", exc_info=True)
        return {"status": "error", "error_message": f"AI regeneration failed: {str(e)}"}

    # Apply the rewrite
    if section_id in text_sections:
        old_text = model.get(section_id, "")
        model[section_id] = new_text
        result = _save_and_rebuild(model, tool_context, "ai_regenerate", section_id)
        result["section"] = section_id
        result["old_length"] = len(old_text)
        result["new_length"] = len(new_text)
        result["new_text"] = new_text
        return result
    else:
        # For data sections (engineers, tickets, etc.), rewrite the executive summary
        # to include more detail about this specific section's data
        model["executive_summary"] = new_text

        result = _save_and_rebuild(model, tool_context, "ai_regenerate", f"executive_summary (from {section_id})")
        result["section"] = "executive_summary"
        result["new_text"] = new_text
        return result
