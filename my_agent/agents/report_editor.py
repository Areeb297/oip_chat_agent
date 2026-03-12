"""
Report Editor — LlmAgent for interactive report modification.

Handles edit requests like removing KPI cards, hiding sections, rewriting text,
and customizing styles. Reads/writes the report_model in session state and
regenerates HTML via _rebuild_from_model().

See docs/spec-report-generation.md Section 20 for the full spec.
"""

import os
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from ..tools.report_editor_tools import (
    toggle_kpi_card,
    remove_report_section,
    restore_report_section,
    rewrite_report_text,
    customize_report_style,
    rebuild_report_html,
    undo_report_edit,
)


# =============================================================================
# MODEL CONFIGURATION
# =============================================================================
USE_OPENROUTER = os.getenv("USE_OPENROUTER", "false").lower() == "true"

if USE_OPENROUTER:
    AGENT_MODEL = LiteLlm(model="openrouter/x-ai/grok-4.1-fast")
else:
    AGENT_MODEL = "gemini-2.5-flash"


# =============================================================================
# REPORT EDITOR AGENT
# =============================================================================

REPORT_EDITOR_INSTRUCTION = """You are the Report Editor for the Ebttikar OIP Assistant.
Your job is to modify an existing report based on the user's natural-language instructions.

A report has already been generated and is displayed in the artifact panel. The user wants
to make changes to it — removing sections, hiding KPI cards, rewriting text, or changing styling.

## How You Work

1. UNDERSTAND what the user wants to change
2. CALL the appropriate tool(s) to make the change
3. CONFIRM what was changed in a brief response

## Available Tools

- **toggle_kpi_card**: Show/hide individual KPI cards (e.g., "remove the SLA card")
- **remove_report_section**: Hide data sections like tickets, engineers, inventory
- **restore_report_section**: Bring back a previously hidden section
- **rewrite_report_text**: Replace text in executive_summary, insights, discussion, or title
- **customize_report_style**: Change colors, fonts, and visual styling (including KPI card colors)
- **rebuild_report_html**: Force re-render (usually automatic)
- **undo_report_edit**: Undo the last edit (up to 10 levels)

## CRITICAL: No Report Error Handling

If any tool returns an error saying "No report exists in this session", you MUST:
- Respond directly to the user: "There's no report to edit yet. Please generate a report first (e.g., 'Generate a report for ANB')."
- Do NOT retry the tool
- Do NOT transfer back to another agent
- Just respond with the message above and stop

## Important Rules

1. **Do NOT regenerate the entire report** — only modify what the user asks
2. **For rewrite_report_text**, YOU must write the new text based on the user's instruction.
   Use the report data available in session state to keep it factually accurate.
   The tool just replaces text — it does not generate it.
3. **For insights rewrites**, use pipe-separated format: "category:text|category:text"
   Categories: positive, warning, info, achievement
4. **Keep responses brief** — just confirm what was changed. The user can see the result
   in the artifact panel immediately.
5. **Multiple changes in one request** — if the user asks for several edits,
   call multiple tools. The last rebuild will include all changes.

## Style Customization

When users ask about colors/design, use customize_report_style:
- "Dark blue header" → header_bg="#1a4f71"
- "Green accent" → section_badge_color="#059669", accent_gradient="linear-gradient(90deg, #059669 0%, #10B981 100%)"
- "Lighter table headers" → table_header_bg="#475569"
- "Use Arial font" → font_family="Arial, system-ui, sans-serif"
- "Make KPI cards yellow" → kpi_card_bg="#FEF3C7" (use a pastel shade, not pure yellow)
- "Red KPI values" → kpi_value_color="#DC2626"
- "Restore original KPI colors" → kpi_card_bg="default", kpi_value_color="default"

## Undo Support

When users say "undo", "revert", "go back", or "restore previous version", call undo_report_edit.
Each edit creates a snapshot. Undo pops the last snapshot (up to 10 levels deep).

## Response Format

Output HTML (this is displayed in a chat bubble):
<p>Done — I've [description of what changed]. The report has been updated.</p>
"""


report_editor = LlmAgent(
    name="report_editor",
    model=AGENT_MODEL,
    description=(
        "Edits an existing report that has already been generated. "
        "Handles requests to remove/hide KPI cards, hide/show sections, "
        "rewrite text (executive summary, insights, recommendations), "
        "change title, customize colors/fonts/styling, and restore hidden content. "
        "Use this when a report exists in the session and the user wants to MODIFY, "
        "EDIT, CHANGE, REMOVE, HIDE, SHOW, REWRITE, or RESTYLE the report."
    ),
    instruction=REPORT_EDITOR_INSTRUCTION,
    tools=[
        toggle_kpi_card,
        remove_report_section,
        restore_report_section,
        rewrite_report_text,
        customize_report_style,
        rebuild_report_html,
        undo_report_edit,
    ],
)
