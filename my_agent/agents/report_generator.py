"""
Report Generator — 3-Agent SequentialAgent Pipeline.

Architecture:
    report_planner → report_data_collector → report_builder

Each agent has a specialized prompt. Data flows via output_key → session state
→ template injection ({output_key} in the next agent's instruction).

See docs/spec-report-generation.md for the full spec.
"""

import os
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm

from ..tools.db_tools import get_current_date, get_lookups
from ..tools.report_tools import collect_report_data, build_html_report


# =============================================================================
# MODEL CONFIGURATION (same pattern as other agents)
# =============================================================================
USE_OPENROUTER = os.getenv("USE_OPENROUTER", "false").lower() == "true"

if USE_OPENROUTER:
    AGENT_MODEL = LiteLlm(model="openrouter/x-ai/grok-4.1-fast")
else:
    AGENT_MODEL = "gemini-2.5-flash"


# =============================================================================
# AGENT 1: Report Planner
# =============================================================================

report_planner = LlmAgent(
    name="report_planner",
    model=AGENT_MODEL,
    output_key="report_plan",
    tools=[get_current_date, get_lookups],
    instruction="""You are the Report Planner. Your job is to analyze the user's report request
and produce a structured plan that tells the Data Collector what to fetch.

STEPS:
1. Call get_current_date() to know today's date.
2. Call get_lookups(lookup_type="Projects") to get the list of available projects.
3. **CRITICAL — Parse filter tags from the user's message.** The message may contain
   system-injected filter tags that MUST be used as report filters:
   - `[ACTIVE_PROJECT_FILTER: ProjectName]` → use as project_names
   - `[ACTIVE_TEAM_FILTER: TeamName]` → use as team_names
   - `[ACTIVE_REGION_FILTER: RegionName]` → use as region_names
   These tags represent the user's active UI filter selections and take PRIORITY.
   ALWAYS extract and apply them. NEVER ignore these tags.
4. Parse the user's request text and MATCH any mentioned project name/abbreviation
   against the actual project names from step 2.
   - Example: user says "ANB" → match to "Arab National Bank" from the lookup list.
   - Example: user says "Barclays" → match to the full project name from the lookup list.
   - ALWAYS use the EXACT project name as returned by get_lookups, never abbreviations.
   - If a filter tag already provides a project/team/region, use THAT value.
     The filter tag value should be matched against lookups for the exact name.
5. Determine:
   - report_type: "project" | "engineer" | "inventory" | "custom"
   - project_names: the EXACT full project name(s) from the lookup (or from filter tag)
   - team_names, region_names, employee_names: any filters (including from filter tags)
   - month, year, date_from, date_to: time period
   - sections: which data sections to include
6. Output a JSON plan.

FILTER TAG EXAMPLES:
- Message: `[ACTIVE_PROJECT_FILTER: Saudi Awwal Bank] Generate a project report`
  → project_names = "Saudi Awwal Bank", title = "Saudi Awwal Bank Project Report"
- Message: `[ACTIVE_TEAM_FILTER: Central] [ACTIVE_PROJECT_FILTER: ANB] Generate report`
  → project_names = match "ANB" to full name from lookups, team_names = "Central"
- Message: `[ACTIVE_REGION_FILTER: Riyadh] Generate report`
  → region_names = "Riyadh"

DEFAULTS:
- If no date/period specified, use ALL TIME (leave month, year, date_from, date_to as null). Do NOT default to current month.
- Only set month/year if the user EXPLICITLY mentions a specific month or period (e.g., "for February", "this month", "last quarter").
- If no project specified AND no [ACTIVE_PROJECT_FILTER] tag, leave project_names empty (all projects).
- If report type is unclear, default to "project".

SECTION OPTIONS:
- tickets: Overall ticket summary with breakdowns
- ticket_types: PM/TR/Other breakdown
- timeline: Monthly trend data
- engineers: Per-engineer performance ranking
- certifications: Certification expiry status
- inventory: Spare parts consumption

DEFAULT SECTIONS BY TYPE:
- project: tickets, ticket_types, timeline, engineers, inventory
- engineer: engineers, certifications
- inventory: inventory
- custom: only what the user asked for

OUTPUT FORMAT — Output ONLY a JSON block like this (no other text):
```json
{
    "report_type": "project",
    "title": "Arab National Bank Project Report",
    "project_names": "Arab National Bank",
    "team_names": null,
    "region_names": null,
    "employee_names": null,
    "month": 2,
    "year": 2026,
    "date_from": null,
    "date_to": null,
    "sections": "tickets,ticket_types,timeline,engineers,inventory",
    "emphasis": "User mentioned SLA concerns"
}
```

RULES:
- Always output valid JSON inside a code block.
- sections must be a comma-separated string.
- Use null for unspecified filters, not empty string.
- title should be the project/report name ONLY (e.g., "Arab National Bank Project Report"). Do NOT include the period, date, or "All Time" in the title — those are shown separately in the report subtitle.""",
    description="Analyzes report requests and creates a structured plan",
)


# =============================================================================
# AGENT 2: Report Data Collector
# =============================================================================

report_data_collector = LlmAgent(
    name="report_data_collector",
    model=AGENT_MODEL,
    output_key="collected_data",
    tools=[collect_report_data],
    instruction="""You are the Report Data Collector. The planner has created this plan:

{report_plan}

YOUR TASK:
1. Parse the plan above to extract the parameters.
2. Call collect_report_data() with the correct parameters from the plan.
3. Summarize what data was collected (counts, key metrics).

PARAMETER MAPPING from plan to tool:
- report_type → report_type
- project_names → project_names (pass null/None values as omitted, not as string "null")
- team_names → team_names
- region_names → region_names
- employee_names → employee_names
- month → month
- year → year
- date_from → date_from
- date_to → date_to
- sections → sections

IMPORTANT:
- Do NOT pass "null" as a string. If a value is null in the plan, omit that parameter.
- Call the tool exactly ONCE with all parameters.
- After the tool returns, summarize the results briefly.
- Include the title and emphasis from the plan in your summary.""",
    description="Fetches data from database using the planner's instructions",
)


# =============================================================================
# AGENT 3: Report Builder
# =============================================================================

report_builder = LlmAgent(
    name="report_builder",
    model=AGENT_MODEL,
    output_key="final_report",
    tools=[build_html_report],
    instruction="""You are the Report Builder. The planner created this plan:

{report_plan}

The collector gathered this data:

{collected_data}

YOUR TASK:
1. Extract the "title" from the plan.
2. Extract "emphasis" from the plan (if any).
3. Write an "executive_summary" — a 3-5 sentence professional narrative describing overall performance.
   Base it on the collected data metrics (ticket counts, completion rate, SLA breaches, engineers, inventory).
   Write in third person, business report style. Be specific with numbers.
4. Write "insights" — 3-5 key insight bullets as pipe-separated text.
   Format: "category:text|category:text|..."
   Categories: positive, warning, info, achievement
   Each insight should be specific and data-driven.
5. Write "discussion" — a 3-5 sentence concluding paragraph that:
   - Summarizes key findings and overall operational health
   - Identifies the most critical areas for improvement
   - Provides actionable recommendations
   - Ends with a forward-looking statement
   Write in professional consulting style.
6. Call build_html_report(title=..., executive_summary=..., insights=..., discussion=..., emphasis=...)
   to generate the HTML report.
7. After the tool returns, provide a brief conversational summary for the user.

EXECUTIVE SUMMARY EXAMPLE (adapt to actual data):
"The Arab National Bank project processed 156 tickets in February 2026, achieving a 62.8% completion rate.
SLA compliance remains an area of focus with 12 breaches representing 7.7% of total volume.
Preventive maintenance activities accounted for 87 tickets, while 14 trouble reports were addressed.
The team of 8 active engineers maintained consistent output, led by Ahmed Al-Rashid with 18 completions.
Inventory consumption totaled 234 spare parts across 12 unique items."

INSIGHTS EXAMPLE (adapt to actual data):
"positive:Completion rate at 62.8% remains above the 60% operational target|warning:SLA breach rate at 7.7% with 12 tickets — requires attention|achievement:Top engineer Ahmed completed 18 tickets with an 85% success rate|info:PM tickets (87) outnumber TR calls (14) by 6:1 ratio|positive:234 spare parts consumed efficiently across 12 item types"

DISCUSSION EXAMPLE (adapt to actual data):
"The Arab National Bank project demonstrates consistent operational activity with room for improvement in ticket resolution efficiency. The 26.3% completion rate and 63% SLA breach rate are the primary areas of concern, suggesting a need to review team capacity and prioritization workflows. Recommendations include implementing automated SLA escalation triggers, rebalancing workload distribution across engineers, and conducting a root-cause analysis of recurring SLA breaches. With focused attention on these areas, the project is well-positioned to improve service delivery metrics in the next reporting period."

IF DATA IS EMPTY OR ZERO:
- Still generate the executive_summary noting no activity was recorded for the period
- Example: "No operational activity was recorded for the Arab National Bank project during March 2026.
  This may indicate a data access restriction or no tickets assigned during this period.
  Please verify the selected filters and date range."
- For insights: "info:No tickets recorded for the selected period|info:Verify project filters and date range are correct"
- For discussion: "No operational data is available for the selected period and filters. This report serves as a baseline confirmation. Verify the project assignment and date range parameters to ensure accurate data retrieval in subsequent reports."

YOUR CHAT SUMMARY SHOULD:
- State the report title and period.
- Mention 2-3 key highlights from the data (e.g., total tickets, completion rate, top engineer).
- Tell the user they can view the report on the right panel or download it as PDF.
- Use HTML formatting (<p>, <strong>).

EXAMPLE CHAT SUMMARY:
<p>Here's your <strong>ANB Project Report for February 2026</strong>.</p>
<ul>
<li><strong>156</strong> total tickets with a <strong>62.8%</strong> completion rate</li>
<li><strong>12</strong> tickets have breached SLA</li>
<li>Top engineer: <strong>Ahmed</strong> with 18 completed tickets</li>
</ul>
<p>You can view the full report on the right or download it as PDF.</p>

RULES:
- Always call build_html_report() with executive_summary, insights, AND discussion — do NOT skip any.
- Keep the chat summary under 6 lines.
- Use HTML tags, not markdown.
- NEVER expose internal terms (session state, tool names, database columns).
- NEVER mention ACTIVE_PROJECT_FILTER, ACTIVE_TEAM_FILTER, ACTIVE_REGION_FILTER or any internal system tags in your response.""",
    description="Generates the final HTML report and provides a summary",
)


# =============================================================================
# SEQUENTIAL AGENT: Pipeline
# =============================================================================

report_generator = SequentialAgent(
    name="report_generator",
    description=(
        "Generates professional PDF-ready reports with KPI cards, tables, and branding. "
        "Use this when the user asks to generate, create, build, download, or print a report. "
        "Supports project reports, engineer performance reports, inventory reports, and custom reports. "
        "Examples: 'Generate a report for ANB', 'Create engineer performance report', "
        "'Build an inventory report for February', 'Download a project report'."
    ),
    sub_agents=[report_planner, report_data_collector, report_builder],
)
