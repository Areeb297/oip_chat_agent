"""
Report generation tools for the OIP Assistant.

Two tools used by the report_generator SequentialAgent pipeline:
1. collect_report_data() — Calls multiple SPs, stores all data in session
2. build_html_report() — Reads session data, produces self-contained HTML report
"""

import json
import logging
import base64
import os
from typing import Optional
from datetime import datetime

from .db_tools import get_db_connection

# Configure logger
logger = logging.getLogger("oip_assistant.tools.report")

# Import ToolContext for session state access
try:
    from google.adk.tools import ToolContext
except ImportError:
    ToolContext = None


# =============================================================================
# LOGO (loads Ebttikar OIP logo from assets/)
# =============================================================================

def _get_logo_base64() -> str:
    """Load Ebttikar OIP logo as base64 data URI from assets/ebttikar_oip_logo.png."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    logo_path = os.path.join(project_root, "assets", "ebttikar_oip_logo.png")

    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"

    # Minimal fallback SVG if logo file missing
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="200" height="60" viewBox="0 0 200 60">
<text x="100" y="28" fill="white" font-family="Segoe UI,Arial,sans-serif" font-size="22" font-weight="700" text-anchor="middle">Ebttikar-OIP</text>
<text x="100" y="48" fill="rgba(255,255,255,0.7)" font-family="Segoe UI,Arial,sans-serif" font-size="11" text-anchor="middle">Operational &amp; Intelligence Platform</text>
</svg>'''
    return f"data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}"


# =============================================================================
# HELPER: Execute SP and return rows as list of dicts
# =============================================================================

def _exec_sp(cursor, sp_name: str, username: str, **kwargs) -> dict:
    """Execute a stored procedure and return result sets as dicts."""
    params = [username]
    param_markers = ['@Username=?']

    for key, value in kwargs.items():
        if value is not None:
            params.append(value)
            param_markers.append(f'@{key}=?')

    sql = f"EXEC {sp_name} {', '.join(param_markers)}"
    print(f"  [REPORT SQL] {sql}  params={params[1:]}")  # skip username for brevity
    cursor.execute(sql, params)

    result_sets = []
    while True:
        rows = cursor.fetchall()
        if rows and cursor.description:
            columns = [col[0] for col in cursor.description]
            data = []
            for row in rows:
                record = {}
                for i, col in enumerate(columns):
                    val = row[i]
                    if isinstance(val, datetime):
                        val = val.strftime("%Y-%m-%d")
                    elif hasattr(val, 'as_tuple'):  # Decimal
                        val = float(val)
                    record[col] = val
                data.append(record)
            result_sets.append(data)
        else:
            result_sets.append([])

        if not cursor.nextset():
            break

    return result_sets


# =============================================================================
# TOOL 1: collect_report_data
# =============================================================================

def collect_report_data(
    report_type: str = "project",
    project_names: Optional[str] = None,
    team_names: Optional[str] = None,
    region_names: Optional[str] = None,
    employee_names: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sections: Optional[str] = None,
    tool_context: "ToolContext" = None,
) -> dict:
    """
    Collect data from multiple stored procedures for report generation.

    Calls the appropriate SPs based on report_type and sections requested,
    stores all collected data in session state for the report builder.

    Args:
        report_type: Type of report. One of: "project", "engineer", "inventory", "custom".
        project_names: Filter by project(s). Comma-separated like "ANB,Barclays".
        team_names: Filter by team(s). Comma-separated.
        region_names: Filter by region(s). Comma-separated.
        employee_names: Filter by engineer name(s). Comma-separated.
        month: Filter by month (1-12).
        year: Filter by year (e.g., 2026).
        date_from: Start date in YYYY-MM-DD format.
        date_to: End date in YYYY-MM-DD format.
        sections: Comma-separated list of sections to include.
                  Options: "tickets,ticket_types,timeline,engineers,certifications,inventory"
                  If not specified, defaults based on report_type.

    Returns:
        dict with status, summary of what was collected, and counts.
    """
    try:
        username = None
        if tool_context is not None:
            username = tool_context.state.get("username")

        if not username:
            return {"status": "error", "Message": "No username in session. Please log in first."}

        # ── Enforce active UI filters from session state ──
        # These override whatever the LLM planner passed, ensuring reports
        # always respect the user's dropdown selections.
        active_project = tool_context.state.get("projectCode") if tool_context else None
        active_team = tool_context.state.get("team") if tool_context else None
        active_region = tool_context.state.get("region") if tool_context else None

        if active_project:
            project_names = active_project
        if active_team:
            team_names = active_team
        if active_region:
            region_names = active_region

        print(f"[REPORT COLLECT] type={report_type}, projects={project_names}, "
              f"teams={team_names}, regions={region_names}, "
              f"month={month}, year={year}, sections={sections}")

        # Determine which sections to collect
        if sections:
            section_list = [s.strip() for s in sections.split(",")]
        else:
            # Default sections per report type
            defaults = {
                "project": ["tickets", "ticket_types", "timeline", "engineers", "inventory"],
                "engineer": ["engineers", "certifications"],
                "inventory": ["inventory"],
                "custom": ["tickets"],
            }
            section_list = defaults.get(report_type, ["tickets"])

        conn = get_db_connection()
        cursor = conn.cursor()

        report_data = {
            "report_type": report_type,
            "project_names": project_names,
            "team_names": team_names,
            "region_names": region_names,
            "employee_names": employee_names,
            "month": month,
            "year": year,
            "date_from": date_from,
            "date_to": date_to,
            "sections_collected": [],
        }

        # Common filter kwargs for SPs
        common_filters = {}
        if project_names:
            common_filters["ProjectNames"] = project_names
        if team_names:
            common_filters["TeamNames"] = team_names
        if region_names:
            common_filters["RegionNames"] = region_names
        if month is not None:
            common_filters["Month"] = month
        if year is not None:
            common_filters["Year"] = year
        if date_from:
            common_filters["DateFrom"] = date_from
        if date_to:
            common_filters["DateTo"] = date_to

        # ── Ticket Summary ──
        if "tickets" in section_list:
            try:
                rs = _exec_sp(cursor, "usp_Chatbot_GetTicketSummary", username,
                              IncludeBreakdown=1, **common_filters)
                report_data["ticket_summary"] = rs[0] if len(rs) > 0 else []
                report_data["ticket_breakdown"] = rs[1] if len(rs) > 1 else []
                # Summary row is ALWAYS rs[0] (first result set from SP)
                # rs[1..3] are breakdowns by region/project/team — each row also
                # has "TotalTickets" but those are per-group subtotals, not the grand total.
                if rs[0] and any("TotalTickets" in r for r in rs[0]):
                    report_data["ticket_totals"] = rs[0][0]
                else:
                    report_data["ticket_totals"] = {}
                report_data["sections_collected"].append("tickets")
                print(f"  [REPORT] tickets: {len(report_data.get('ticket_summary', []))} rows")
            except Exception as e:
                logger.warning(f"[REPORT] ticket_summary failed: {e}")
                report_data["ticket_summary_error"] = str(e)

        # ── Ticket Types (PM/TR/Other) ──
        if "ticket_types" in section_list:
            try:
                rs_pm = _exec_sp(cursor, "usp_Chatbot_GetTicketSummary", username,
                                 TaskTypeNames="PM", **common_filters)
                rs_tr = _exec_sp(cursor, "usp_Chatbot_GetTicketSummary", username,
                                 TaskTypeNames="TR", **common_filters)
                rs_other = _exec_sp(cursor, "usp_Chatbot_GetTicketSummary", username,
                                    TaskTypeNames="Other", **common_filters)

                type_data = []
                for label, rs in [("PM", rs_pm), ("TR", rs_tr), ("Other", rs_other)]:
                    # Summary row is ALWAYS rs[0] (first result set from SP)
                    totals = rs[0][0] if rs and rs[0] and any("TotalTickets" in r for r in rs[0]) else {}
                    type_data.append({
                        "TaskType": label,
                        "TotalTickets": totals.get("TotalTickets", 0),
                        "OpenTickets": totals.get("OpenTickets", 0),
                        "CompletedTickets": totals.get("CompletedTickets", 0),
                        "SuspendedTickets": totals.get("SuspendedTickets", 0),
                    })

                report_data["ticket_types"] = type_data
                report_data["sections_collected"].append("ticket_types")
                print(f"  [REPORT] ticket_types: PM={type_data[0]['TotalTickets']}, "
                      f"TR={type_data[1]['TotalTickets']}, Other={type_data[2]['TotalTickets']}")
            except Exception as e:
                logger.warning(f"[REPORT] ticket_types failed: {e}")
                report_data["ticket_types_error"] = str(e)

        # ── Timeline ──
        if "timeline" in section_list:
            try:
                timeline_filters = {}
                if project_names:
                    timeline_filters["ProjectNames"] = project_names
                if team_names:
                    timeline_filters["TeamNames"] = team_names
                if region_names:
                    timeline_filters["RegionNames"] = region_names
                if date_from:
                    timeline_filters["DateFrom"] = date_from
                if date_to:
                    timeline_filters["DateTo"] = date_to
                if not date_from and month is not None and year is not None:
                    import calendar
                    last_day = calendar.monthrange(year, month)[1]
                    timeline_filters["DateFrom"] = f"{year}-{month:02d}-01"
                    timeline_filters["DateTo"] = f"{year}-{month:02d}-{last_day:02d}"
                elif not date_from and year is not None:
                    timeline_filters["DateFrom"] = f"{year}-01-01"
                    timeline_filters["DateTo"] = f"{year}-12-31"
                rs = _exec_sp(cursor, "usp_Chatbot_GetTicketTimeline", username,
                              Period="month", **timeline_filters)
                report_data["timeline"] = rs[0] if len(rs) > 0 else []
                report_data["sections_collected"].append("timeline")
                print(f"  [REPORT] timeline: {len(report_data['timeline'])} periods")
            except Exception as e:
                logger.warning(f"[REPORT] timeline failed: {e}")
                report_data["timeline_error"] = str(e)

        # ── Engineers ──
        if "engineers" in section_list:
            try:
                eng_filters = dict(common_filters)
                if employee_names:
                    eng_filters["EmployeeNames"] = employee_names
                # Pass RoleNames="All" for reports — we want all roles, SP now returns RoleName column
                eng_filters["RoleNames"] = "All"
                rs = _exec_sp(cursor, "usp_Chatbot_GetEngineerPerformance", username,
                              **eng_filters)
                report_data["engineers"] = rs[0] if len(rs) > 0 else []
                report_data["engineer_summary"] = rs[1][0] if len(rs) > 1 and rs[1] else {}
                report_data["sections_collected"].append("engineers")
                # Debug: show roles returned
                roles_found = set(e.get("RoleName", "N/A") for e in report_data["engineers"])
                print(f"  [REPORT] engineers: {len(report_data['engineers'])} rows, roles={roles_found}")
            except Exception as e:
                logger.warning(f"[REPORT] engineers failed: {e}")
                report_data["engineers_error"] = str(e)

        # ── Certifications ──
        if "certifications" in section_list:
            try:
                cert_filters = {}
                if project_names:
                    cert_filters["ProjectNames"] = project_names
                if employee_names:
                    cert_filters["EmployeeNames"] = employee_names
                rs = _exec_sp(cursor, "usp_Chatbot_GetCertificationStatus", username,
                              ShowAll=1, **cert_filters)
                report_data["certifications"] = rs[0] if len(rs) > 0 else []
                report_data["cert_summary"] = rs[1][0] if len(rs) > 1 and rs[1] else {}
                report_data["sections_collected"].append("certifications")
                print(f"  [REPORT] certifications: {len(report_data['certifications'])} rows")
            except Exception as e:
                logger.warning(f"[REPORT] certifications failed: {e}")
                report_data["certifications_error"] = str(e)

        # ── Inventory ──
        if "inventory" in section_list:
            try:
                inv_filters = dict(common_filters)
                rs = _exec_sp(cursor, "usp_Chatbot_GetInventoryConsumption", username,
                              **inv_filters)
                report_data["inventory"] = rs[0] if len(rs) > 0 else []
                report_data["inventory_summary"] = rs[1][0] if len(rs) > 1 and rs[1] else {}
                report_data["sections_collected"].append("inventory")
                print(f"  [REPORT] inventory: {len(report_data['inventory'])} rows")
            except Exception as e:
                logger.warning(f"[REPORT] inventory failed: {e}")
                report_data["inventory_error"] = str(e)

        cursor.close()
        conn.close()

        # Store full data in session for builder
        if tool_context is not None:
            tool_context.state["report_data"] = report_data
            logger.info(f"[REPORT] Stored report_data in session: sections={report_data['sections_collected']}")

        # Return compact summary (not the full data — that's in session)
        summary = {
            "status": "success",
            "report_type": report_type,
            "sections_collected": report_data["sections_collected"],
            "ticket_count": len(report_data.get("ticket_summary", [])),
            "engineer_count": len(report_data.get("engineers", [])),
            "inventory_count": len(report_data.get("inventory", [])),
            "certification_count": len(report_data.get("certifications", [])),
            "timeline_periods": len(report_data.get("timeline", [])),
            "Message": "Data collected successfully",
        }

        # Include ticket totals for builder context
        if "ticket_totals" in report_data:
            summary["ticket_totals"] = report_data["ticket_totals"]
        if "engineer_summary" in report_data:
            summary["engineer_summary"] = report_data["engineer_summary"]
        if "inventory_summary" in report_data:
            summary["inventory_summary"] = report_data["inventory_summary"]
        if "ticket_types" in report_data:
            summary["ticket_types"] = report_data["ticket_types"]

        print(f"[REPORT COLLECT] Done: {report_data['sections_collected']}")
        return summary

    except Exception as e:
        print(f"[REPORT ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "Message": f"Error collecting report data: {str(e)}"}


# =============================================================================
# TOOL 2: build_html_report
# =============================================================================

def build_html_report(
    title: str = "Report",
    executive_summary: Optional[str] = None,
    insights: Optional[str] = None,
    discussion: Optional[str] = None,
    emphasis: Optional[str] = None,
    tool_context: "ToolContext" = None,
) -> dict:
    """
    Build a self-contained HTML report from data stored in session.

    Reads report_data from session state (populated by collect_report_data),
    generates a professional branded HTML document with executive summary,
    KPI cards, insight bullets, data tables, charts, and a discussion section.

    Args:
        title: Report title (e.g., "ANB Project Report - February 2026").
        executive_summary: A 3-5 sentence narrative summarizing the overall performance,
            key achievements, areas of concern, and recommendations. Written in
            professional business language.
        insights: A pipe-separated list of 3-5 key insight bullets. Each insight should
            start with a category tag. Format: "category:text|category:text|..."
            Categories: "positive", "warning", "info", "achievement"
        discussion: A 3-5 sentence concluding discussion that summarizes the findings,
            identifies areas for improvement, and recommends next steps. Written in
            professional business language with actionable recommendations.
        emphasis: Optional notes about what to highlight.

    Returns:
        dict with status and the complete HTML report string.
    """
    try:
        if tool_context is None:
            return {"status": "error", "Message": "No tool context available."}

        report_data = tool_context.state.get("report_data")
        if not report_data:
            return {"status": "error", "Message": "No report data in session. Run collect_report_data first."}

        # Auto-correct title if filters are active but title says "All Projects"
        if report_data.get("project_names") and "all project" in title.lower():
            project_label = report_data["project_names"]
            title = f"{project_label} Project Report"

        print(f"[REPORT BUILD] title={title}, sections={report_data.get('sections_collected', [])}")

        logo_uri = _get_logo_base64()
        gen_date = datetime.now().strftime("%d %B %Y")

        # Build subtitle line
        subtitle_parts = []
        if report_data.get("team_names"):
            subtitle_parts.append(report_data["team_names"])
        if report_data.get("region_names"):
            subtitle_parts.append(report_data["region_names"])
        if report_data.get("month") and report_data.get("year"):
            month_name = datetime(report_data["year"], report_data["month"], 1).strftime("%B %Y")
            subtitle_parts.append(month_name)
        elif report_data.get("date_from") and report_data.get("date_to"):
            subtitle_parts.append(f"{report_data['date_from']} to {report_data['date_to']}")
        elif report_data.get("year"):
            subtitle_parts.append(str(report_data["year"]))
        subtitle_line = "Project Performance Report"
        if subtitle_parts:
            subtitle_line += " &middot; " + " &middot; ".join(subtitle_parts)

        # ── Build content sections (numbered) ──
        section_num = 1

        # LEFT COLUMN: Executive Summary, Key Insights, Ticket Status
        left_html = ""

        # Executive Summary
        if executive_summary:
            left_html += _build_executive_summary(section_num, executive_summary)
            section_num += 1

        # Key Insights
        insights_num = section_num
        if insights:
            left_html += _build_insights(section_num, insights)
            section_num += 1

        # Ticket Status Table
        totals = report_data.get("ticket_totals", {})
        has_ticket_data = totals.get("TotalTickets", 0) > 0
        if "tickets" in report_data.get("sections_collected", []) and has_ticket_data:
            left_html += _build_ticket_section(section_num, report_data)
            section_num += 1

        # Task Type Breakdown (compact, fits in left column)
        type_data = report_data.get("ticket_types", [])
        has_type_data = any(td.get("TotalTickets", 0) > 0 for td in type_data)
        if "ticket_types" in report_data.get("sections_collected", []) and has_type_data:
            left_html += _build_task_type_section(section_num, report_data)
            section_num += 1

        # Inventory (if present, add to left)
        inventory = report_data.get("inventory", [])
        has_inv_data = any(txn.get("Quantity", 0) > 0 for txn in inventory)
        if "inventory" in report_data.get("sections_collected", []) and has_inv_data:
            left_html += _build_inventory_section(section_num, report_data)
            section_num += 1

        # RIGHT COLUMN: Team Performance, Recommendations
        right_html = ""

        # Top Engineers
        engineers = report_data.get("engineers", [])
        has_eng_data = any(e.get("TotalTickets", 0) > 0 for e in engineers)
        if "engineers" in report_data.get("sections_collected", []) and has_eng_data:
            right_html += _build_engineers_section(section_num, report_data)
            section_num += 1

        # Certifications (add to right column)
        certs = report_data.get("certifications", [])
        if "certifications" in report_data.get("sections_collected", []) and certs:
            right_html += _build_certifications_section(section_num, report_data)
            section_num += 1

        # Discussion / Recommendations (right column)
        if discussion:
            right_html += _build_discussion(section_num, discussion)
            section_num += 1

        # KPI Cards row
        kpi_html = _build_kpi_cards(report_data)

        # Two-column body
        body_html = ""
        if left_html or right_html:
            body_html = f'''<div class="two-col">
    <div class="col-left">{left_html}</div>
    <div class="col-right">{right_html}</div>
</div>'''
        else:
            body_html = '''<div style="text-align:center;padding:40px 20px;color:#64748b;">
    <div style="font-size:36px;margin-bottom:8px;">&#128202;</div>
    <p>No data available for the selected filters and period.</p>
    <p style="font-size:10px;color:#94a3b8;margin-top:4px;">Try adjusting the project, date range, or team filters.</p>
</div>'''

        # Project label for footer
        proj_label = report_data.get("project_names", "All Projects")

        # ── Assemble full HTML document ──
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{_esc(title)}</title>
<style>
{_get_report_css()}
</style>
</head>
<body>
<div class="report-root">
<div class="page">
    <div class="page-header-band">
        <div class="header-left">
            <img src="{logo_uri}" alt="Ebttikar OIP" class="header-logo">
            <div class="header-title-block">
                <h1 class="report-title">{_esc(title)}</h1>
                <p class="report-subtitle">{subtitle_line}</p>
            </div>
        </div>
        <div class="header-right">
            <div class="header-meta-item">
                <span class="meta-label">Date</span>
                <span class="meta-value">{gen_date}</span>
            </div>
            <div class="header-meta-item">
                <span class="meta-label">Prepared by</span>
                <span class="meta-value">Ebttikar OIP</span>
            </div>
            <div class="header-meta-item">
                <span class="meta-label">Classification</span>
                <span class="meta-value confidential">Confidential</span>
            </div>
        </div>
    </div>
    <div class="accent-bar"></div>
    <div class="page-body">
{kpi_html}
{body_html}
    </div>
    <div class="page-footer">
        <span>{_esc(proj_label)} &mdash; Project Performance Report &middot; {gen_date} &middot; Confidential</span>
        <span>Powered by Onasi &middot; &copy; 2026 Onasi-CloudTech</span>
    </div>
</div>
</div>
</body>
</html>"""

        # Store in session
        tool_context.state["last_report_html"] = html
        tool_context.state["last_query_context"] = "report"

        print(f"[REPORT BUILD] Done: {len(html)} chars HTML")

        # Return with report delimiters for main.py to detect
        return {
            "status": "success",
            "report": f"<!--REPORT_START-->{html}<!--REPORT_END-->",
            "Message": "Report generated successfully",
            "html_size": len(html),
        }

    except Exception as e:
        print(f"[REPORT BUILD ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "Message": f"Error building report: {str(e)}"}


# =============================================================================
# CSS
# =============================================================================

def _get_report_css() -> str:
    """Return the complete CSS for the report — compact A4-like design."""
    return """@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Playfair+Display:wght@700&display=swap');

* { margin: 0; padding: 0; box-sizing: border-box; }

/* ── Root ── */
.report-root {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    background: #D1D5DB;
    padding: 0;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
}

/* ── A4 Page ── */
.page {
    width: 794px;
    background: #FFFFFF;
    box-shadow: 0 4px 32px rgba(0,0,0,0.15);
    display: flex;
    flex-direction: column;
}

/* ── Header Band ── */
.page-header-band {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 32px;
    background: #EEF2FF;
    border-bottom: 3px solid #2746E3;
}
.header-left {
    display: flex;
    align-items: center;
    gap: 14px;
}
.header-logo {
    height: 34px;
    width: auto;
}
.header-title-block {
    border-left: 2px solid #C7D2FE;
    padding-left: 14px;
}
.report-title {
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 18px;
    font-weight: 700;
    color: #1E293B;
    margin: 0;
    line-height: 1.2;
}
.report-subtitle {
    font-size: 11px;
    color: #6B7280;
    margin: 2px 0 0;
    font-weight: 400;
    letter-spacing: 0.04em;
}
.header-right {
    display: flex;
    gap: 24px;
    align-items: center;
}
.header-meta-item {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 2px;
}
.meta-label {
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #9CA3AF;
}
.meta-value {
    font-size: 11px;
    font-weight: 600;
    color: #374151;
}
.meta-value.confidential {
    color: #DC2626;
    font-weight: 700;
}

/* ── Accent Bar ── */
.accent-bar {
    height: 4px;
    background: linear-gradient(90deg, #1D4ED8 0%, #7C3AED 50%, #06B6D4 100%);
    flex-shrink: 0;
}

/* ── Page Body ── */
.page-body {
    padding: 14px 28px;
    flex: 1;
}

/* ── KPI Row ── */
.kpi-row {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 8px;
    margin-bottom: 14px;
}
.kpi-card {
    border-radius: 8px;
    padding: 10px 8px 8px;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 2px;
    border: none;
    position: relative;
    overflow: hidden;
}
.kpi-value {
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 18px;
    font-weight: 800;
    line-height: 1.1;
    letter-spacing: -0.02em;
}
.kpi-label {
    font-size: 8px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6B7280;
    margin-top: 2px;
}
.kpi-sub {
    font-size: 8px;
    color: #9CA3AF;
    line-height: 1;
    margin-top: 2px;
}

/* ── Two Column ── */
.two-col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}
.col-left, .col-right {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

/* ── Section Block ── */
.section-block {
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.section-heading {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    font-weight: 700;
    color: #0F172A;
    margin: 0;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding-bottom: 6px;
    border-bottom: 1.5px solid #E2E8F0;
}
.sec-num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border-radius: 5px;
    background: #2746E3;
    color: #FFF;
    font-size: 9px;
    font-weight: 700;
    flex-shrink: 0;
}
.body-text {
    font-size: 11px;
    line-height: 1.6;
    color: #374151;
    margin: 0;
}

/* ── Insights ── */
.insight-list {
    display: flex;
    flex-direction: column;
    gap: 5px;
}
.insight {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    font-size: 10.5px;
    color: #374151;
    line-height: 1.4;
    padding: 4px 8px;
    border-radius: 6px;
}
.insight.critical { background: #FEF2F2; }
.insight.info { background: #EFF6FF; }
.insight.positive { background: #F0FDF4; }
.insight.achievement { background: #FAF5FF; }
.ins-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
    margin-top: 4px;
}

/* ── Compact Table ── */
.compact-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
}
.compact-table thead tr {
    background: #0F172A;
}
.compact-table thead th {
    padding: 6px 8px;
    text-align: left;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #94A3B8;
}
.compact-table tbody tr {
    border-bottom: 1px solid #F1F5F9;
}
.compact-table tbody tr:nth-child(even) {
    background: #F8FAFC;
}
.compact-table tbody td {
    padding: 6px 8px;
    color: #374151;
    vertical-align: middle;
}
.compact-table td.num {
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-weight: 500;
}
.compact-table td.name {
    font-weight: 600;
    color: #1E293B;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100px;
}
.compact-table td.muted {
    color: #9CA3AF;
    font-size: 10px;
    max-width: 100px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.compact-table td.red-text {
    color: #EF4444;
    font-weight: 700;
    text-align: right;
}

/* ── Bar Cell ── */
.bar-cell {
    display: flex;
    align-items: center;
    gap: 6px;
}
.bar-wrap {
    flex: 1;
    height: 5px;
    background: #F1F5F9;
    border-radius: 99px;
    overflow: hidden;
    min-width: 40px;
}
.bar {
    height: 100%;
    border-radius: 99px;
}
.pct {
    font-size: 10px;
    font-weight: 600;
    color: #6B7280;
    white-space: nowrap;
}

/* ── Badge ── */
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 99px;
    font-size: 10px;
    font-weight: 600;
}

/* ── Alert Strip ── */
.alert-strip {
    font-size: 10.5px;
    padding: 7px 10px;
    border-radius: 6px;
    line-height: 1.5;
}
.alert-strip.red {
    background: #FEF2F2;
    border-left: 3px solid #EF4444;
    color: #7F1D1D;
}
.alert-strip.amber {
    background: #FFFBEB;
    border-left: 3px solid #F59E0B;
    color: #78350F;
}

/* ── Sub label ── */
.sub-label {
    font-size: 10px;
    font-weight: 700;
    color: #6B7280;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 0;
}

/* ── Engineer Rows ── */
.eng-row {
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin-bottom: 4px;
}
.eng-top {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
}
.eng-name {
    font-size: 11px;
    font-weight: 600;
    color: #1E293B;
}
.eng-rate {
    font-size: 11px;
    font-weight: 700;
}
.eng-bar-track {
    width: 100%;
    height: 7px;
    background: #F1F5F9;
    border-radius: 99px;
    overflow: hidden;
    position: relative;
    display: flex;
    align-items: center;
}
.eng-bar-fill {
    height: 100%;
    border-radius: 99px;
    min-width: 3px;
}
.eng-count {
    position: absolute;
    right: 0;
    font-size: 9px;
    color: #9CA3AF;
    padding-right: 4px;
    background: #F1F5F9;
    line-height: 7px;
}

/* ── Recommendations ── */
.rec-list {
    display: flex;
    flex-direction: column;
    gap: 5px;
}
.rec-item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    font-size: 10.5px;
    color: #374151;
    line-height: 1.4;
    padding: 4px 0;
    border-bottom: 1px solid #F1F5F9;
}
.rec-icon {
    font-size: 13px;
    flex-shrink: 0;
    width: 18px;
    text-align: center;
}
.rec-text { flex: 1; }

/* ── Page Footer ── */
.page-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 28px;
    border-top: 1px solid #E2E8F0;
    background: #F8FAFC;
    font-size: 9.5px;
    color: #9CA3AF;
    flex-shrink: 0;
}

/* ── Print ── */
@media print {
    html, body {
        margin: 0;
        padding: 0;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }
    .report-root {
        background: transparent;
        padding: 0;
        gap: 0;
        min-height: auto;
    }
    .page {
        width: 100%;
        min-height: auto;
        box-shadow: none;
    }
    .section-block {
        page-break-inside: avoid;
    }
    .page-body {
        padding: 10px 18px;
    }
    .page-header-band {
        padding: 10px 18px;
    }
    .page-footer {
        padding: 6px 18px;
    }
    .kpi-row { margin-bottom: 12px; gap: 6px; }
    .kpi-card { padding: 6px 4px 4px; }
    .kpi-value { font-size: 15px; }
    .two-col { gap: 14px; }
    .col-left, .col-right { gap: 10px; }
    .section-block { gap: 5px; }
    .section-heading { font-size: 10px; padding-bottom: 4px; }
    .sec-num { width: 16px; height: 16px; font-size: 8px; }
    .body-text { font-size: 10px; line-height: 1.5; }
    .insight { padding: 4px 8px; font-size: 10px; }
    .compact-table { font-size: 9.5px; }
    .compact-table thead th { padding: 4px 6px; font-size: 8px; }
    .compact-table tbody td { padding: 4px 6px; }
    .eng-row { margin-bottom: 3px; }
    .eng-name { font-size: 10px; }
    .eng-rate { font-size: 10px; }
    .sub-label { font-size: 9px; }
    .rec-item { font-size: 10px; padding: 3px 0; }
    .rec-icon { font-size: 11px; }
    .alert-strip { font-size: 9px; padding: 5px 8px; }
    @page { size: A4; margin: 5mm; }
}"""


# =============================================================================
# HTML SECTION BUILDERS
# =============================================================================

def _esc(text) -> str:
    """HTML-escape a string."""
    if text is None:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _fmt_num(val) -> str:
    """Format a number with commas, or return '0'."""
    if val is None:
        return "0"
    try:
        if isinstance(val, float):
            if val == int(val):
                return f"{int(val):,}"
            return f"{val:,.1f}"
        return f"{int(val):,}"
    except (ValueError, TypeError):
        return str(val)


def _build_executive_summary(num: int, summary_text: str) -> str:
    """Build the executive summary section — compact body text."""
    return f'''<div class="section-block">
    <h2 class="section-heading"><span class="sec-num">{num:02d}</span> Executive Summary</h2>
    <p class="body-text">{_esc(summary_text)}</p>
</div>
'''


def _build_insights(num: int, insights_str: str) -> str:
    """Build the key insights section — dot-style with colored backgrounds."""
    items = [i.strip() for i in insights_str.split("|") if i.strip()]
    if not items:
        return ""

    # Map category to (dot color, CSS class)
    cat_map = {
        "positive": ("#10B981", "positive"),
        "warning": ("#EF4444", "critical"),
        "info": ("#3B82F6", "info"),
        "achievement": ("#7C3AED", "achievement"),
    }

    items_html = ""
    for item in items:
        if ":" in item:
            cat, text = item.split(":", 1)
            cat = cat.strip().lower()
        else:
            cat, text = "info", item

        dot_color, css_cls = cat_map.get(cat, ("#3B82F6", "info"))
        items_html += f'''        <div class="insight {css_cls}">
            <span class="ins-dot" style="background:{dot_color}"></span>
            <span>{_esc(text.strip())}</span>
        </div>
'''

    return f'''<div class="section-block">
    <h2 class="section-heading"><span class="sec-num">{num:02d}</span> Key Insights</h2>
    <div class="insight-list">
{items_html}    </div>
</div>
'''


def _build_discussion(num: int, discussion_text: str) -> str:
    """Build the recommendations section with emoji icons per line."""
    # Split discussion into individual recommendation lines
    lines = [l.strip() for l in discussion_text.replace("\n", "|").split("|") if l.strip()]

    # If it's a single paragraph (no pipes/newlines), display as body text
    if len(lines) <= 1:
        return f'''<div class="section-block">
    <h2 class="section-heading"><span class="sec-num">{num:02d}</span> Recommendations</h2>
    <p class="body-text">{_esc(discussion_text)}</p>
</div>
'''

    # Cycle through recommendation icons
    rec_icons = ["&#128269;", "&#9889;", "&#9878;&#65039;", "&#127919;", "&#128101;", "&#128230;", "&#128200;", "&#128736;"]

    items_html = ""
    for i, line in enumerate(lines):
        icon = rec_icons[i % len(rec_icons)]
        items_html += f'''        <div class="rec-item">
            <span class="rec-icon">{icon}</span>
            <span class="rec-text">{_esc(line)}</span>
        </div>
'''

    return f'''<div class="section-block">
    <h2 class="section-heading"><span class="sec-num">{num:02d}</span> Recommendations</h2>
    <div class="rec-list">
{items_html}    </div>
</div>
'''


def _build_kpi_cards(report_data: dict) -> str:
    """Build the KPI row — 6 pastel cards with bold colored values."""
    # Each card: (label, value, color, bg, sub_text)
    cards = []

    totals = report_data.get("ticket_totals", {})
    if totals and totals.get("TotalTickets", 0) > 0:
        total = totals.get("TotalTickets", 0)
        open_t = totals.get("OpenTickets", 0)
        completed = totals.get("CompletedTickets", 0)
        sla = totals.get("SLABreached", 0)
        rate = totals.get("CompletionRate", 0)
        if (rate == 0 or rate is None) and total > 0:
            rate = (completed / total) * 100
        open_pct = f"{(open_t / total * 100):.1f}%" if total > 0 else ""
        comp_pct = f"{rate:.1f}%" if isinstance(rate, float) else f"{rate}%"
        sla_pct = f"{(sla / total * 100):.1f}%" if total > 0 else ""

        cards.append(("Total Tickets", _fmt_num(total), "#2746E3", "#EEF2FF", ""))
        cards.append(("Open Tickets", _fmt_num(open_t), "#D97706", "#FEF3C7", open_pct))
        cards.append(("Completed", _fmt_num(completed), "#059669", "#D1FAE5", comp_pct))
        cards.append(("SLA Breached", _fmt_num(sla), "#DC2626", "#FEE2E2", sla_pct))

    # Task type KPIs
    type_data = report_data.get("ticket_types", [])
    for td in type_data:
        if td.get("TotalTickets", 0) > 0:
            if td["TaskType"] == "PM":
                total_all = sum(t.get("TotalTickets", 0) for t in type_data)
                pm_pct = f"{(td['TotalTickets'] / total_all * 100):.0f}%" if total_all > 0 else ""
                cards.append(("PM Tickets", _fmt_num(td["TotalTickets"]), "#7C3AED", "#F3E8FF", pm_pct))
            elif td["TaskType"] == "TR":
                total_all = sum(t.get("TotalTickets", 0) for t in type_data)
                tr_pct = f"{(td['TotalTickets'] / total_all * 100):.0f}%" if total_all > 0 else ""
                cards.append(("TR Calls", _fmt_num(td["TotalTickets"]), "#6366F1", "#E0E7FF", tr_pct))

    # Engineer KPI
    eng_summary = report_data.get("engineer_summary", {})
    engineers = report_data.get("engineers", [])
    if eng_summary and eng_summary.get("TotalEngineers", 0) > 0:
        total_eng = eng_summary.get("TotalEngineers", 0)
        active_eng = len([e for e in engineers if e.get("TotalTickets", 0) > 0])
        cards.append(("Engineers", f"{active_eng}/{total_eng}", "#0891B2", "#E0F2FE", "active"))
    elif engineers:
        active_eng = len([e for e in engineers if e.get("TotalTickets", 0) > 0])
        if active_eng > 0:
            cards.append(("Engineers", str(active_eng), "#0891B2", "#E0F2FE", "active"))

    # Inventory KPI
    inv_summary = report_data.get("inventory_summary", {})
    if inv_summary and inv_summary.get("TotalQuantity", 0) > 0:
        cards.append(("Parts Consumed", _fmt_num(inv_summary.get("TotalQuantity")), "#14B8A6", "#CCFBF1", ""))

    if not cards:
        return ""

    # Pad to 6 cards or take first 6
    cards_html = ""
    for label, value, color, bg, sub in cards[:6]:
        sub_html = f'<div class="kpi-sub">{_esc(sub)}</div>' if sub else ""
        cards_html += f'''        <div class="kpi-card" style="background:{bg}">
            <div class="kpi-value" style="color:{color}">{value}</div>
            <div class="kpi-label">{_esc(label)}</div>
            {sub_html}
        </div>
'''

    return f'''    <div class="kpi-row">
{cards_html}    </div>
'''


def _build_ticket_section(num: int, report_data: dict) -> str:
    """Build the ticket status table — compact with dark header, bar visualizations, badges."""
    totals = report_data.get("ticket_totals", {})
    total = totals.get("TotalTickets", 0)
    if total == 0:
        return ""

    open_t = totals.get("OpenTickets", 0)
    completed = totals.get("CompletedTickets", 0)
    suspended = totals.get("SuspendedTickets", 0)
    pending = totals.get("PendingApprovalTickets", 0)
    sla = totals.get("SLABreached", 0)

    rows_data = [
        ("Open", open_t, "#F59E0B", "#FEF3C7", "#B45309"),
        ("Completed", completed, "#10B981", "#D1FAE5", "#065F46"),
        ("Suspended", suspended, "#F97316", "#FFEDD5", "#9A3412"),
        ("Pending Approval", pending, "#8B5CF6", "#F3E8FF", "#5B21B6"),
        ("SLA Breached", sla, "#EF4444", "#FEE2E2", "#B91C1C"),
    ]

    table_rows = ""
    for status, count, bar_color, badge_bg, badge_color in rows_data:
        if count == 0:
            continue
        pct = (count / total * 100) if total > 0 else 0
        bar_w = f"{max(pct, 0.5):.1f}%"
        min_w = "min-width:2px;" if pct < 1 else ""
        table_rows += f'''            <tr>
                <td><span class="badge" style="background:{badge_bg};color:{badge_color}">{_esc(status)}</span></td>
                <td class="num">{_fmt_num(count)}</td>
                <td><div class="bar-cell"><div class="bar-wrap"><div class="bar" style="width:{bar_w};{min_w}background:{bar_color}"></div></div><span class="pct">{pct:.1f}%</span></div></td>
            </tr>
'''

    if not table_rows:
        return ""

    # Alert strip
    alert = ""
    if sla > 0:
        sla_pct = sla / total * 100
        if sla_pct > 50:
            alert = f'<div class="alert-strip red">&#9888; SLA breach rate critically high at {sla_pct:.1f}% &mdash; immediate intervention required.</div>'
        elif sla_pct > 20:
            alert = f'<div class="alert-strip amber">&#9888; SLA breach rate of {sla_pct:.1f}% exceeds acceptable thresholds.</div>'

    return f'''<div class="section-block">
    <h2 class="section-heading"><span class="sec-num">{num:02d}</span> Ticket Status</h2>
    <table class="compact-table">
        <thead>
            <tr><th>Status</th><th>Count</th><th>Share</th></tr>
        </thead>
        <tbody>
{table_rows}        </tbody>
    </table>
    {alert}
</div>
'''


def _build_task_type_section(num: int, report_data: dict) -> str:
    """Build the task type breakdown — compact table with share bars."""
    type_data = report_data.get("ticket_types", [])
    if not type_data:
        return ""

    active_types = [td for td in type_data if td.get("TotalTickets", 0) > 0]
    if not active_types:
        return ""

    total_all = sum(td["TotalTickets"] for td in active_types)
    type_colors = {"PM": "#7C3AED", "TR": "#6366F1", "Other": "#64748B"}
    type_bgs = {"PM": "#F3E8FF", "TR": "#E0E7FF", "Other": "#F1F5F9"}
    type_badge_colors = {"PM": "#5B21B6", "TR": "#4338CA", "Other": "#475569"}

    table_rows = ""
    for td in active_types:
        tt = td["TaskType"]
        bar_color = type_colors.get(tt, "#64748B")
        badge_bg = type_bgs.get(tt, "#F1F5F9")
        badge_color = type_badge_colors.get(tt, "#475569")
        pct = (td["TotalTickets"] / total_all * 100) if total_all > 0 else 0
        bar_w = f"{max(pct, 0.5):.1f}%"
        table_rows += f'''            <tr>
                <td><span class="badge" style="background:{badge_bg};color:{badge_color}">{_esc(tt)}</span></td>
                <td class="num">{_fmt_num(td["TotalTickets"])}</td>
                <td class="num">{_fmt_num(td["OpenTickets"])}</td>
                <td class="num">{_fmt_num(td["CompletedTickets"])}</td>
                <td><div class="bar-cell"><div class="bar-wrap"><div class="bar" style="width:{bar_w};background:{bar_color}"></div></div><span class="pct">{pct:.0f}%</span></div></td>
            </tr>
'''

    return f'''<div class="section-block">
    <h2 class="section-heading"><span class="sec-num">{num:02d}</span> Task Type Breakdown</h2>
    <table class="compact-table">
        <thead>
            <tr><th>Type</th><th>Total</th><th>Open</th><th>Done</th><th>Share</th></tr>
        </thead>
        <tbody>
{table_rows}        </tbody>
    </table>
</div>
'''


def _consolidate_engineers(engineers: list) -> list:
    """Consolidate duplicate engineer rows (same person, different regions) into one row.

    The SP groups by (EmployeeId, RegionName), so an engineer with tickets in
    multiple regions appears multiple times. This merges them into a single row
    with aggregated ticket counts and a list of all regions they cover.

    Uses EmployeeCode as the unique key (falls back to EngineerName if missing).
    This prevents merging different people who share the same name (e.g. two
    different "Administrator" accounts across projects).
    """
    by_key = {}
    for eng in engineers:
        # Use EmployeeId as unique key — it's the DB primary key per employee
        # Falls back to EmployeeCode, then EngineerName
        emp_id = eng.get("EmployeeId", "")
        emp_code = eng.get("EmployeeCode", "")
        name = eng.get("EmployeeName", eng.get("EngineerName", "Unknown"))
        key = str(emp_id) if emp_id else (emp_code if emp_code else name)

        if key in by_key:
            merged = by_key[key]
            # Sum ticket counts
            for field in ("TotalTickets", "CompletedTickets", "OpenTickets",
                          "SuspendedTickets", "SLABreached", "TRTickets",
                          "PMTickets", "OtherTickets"):
                merged[field] = merged.get(field, 0) + eng.get(field, 0)
            # Recalculate completion rate
            total = merged.get("TotalTickets", 0)
            completed = merged.get("CompletedTickets", 0)
            merged["CompletionRate"] = round(completed / total * 100, 2) if total > 0 else 0
            # Collect regions
            region = eng.get("RegionName", "")
            if region and region not in merged["_regions"]:
                merged["_regions"].append(region)
        else:
            region = eng.get("RegionName", "")
            entry = dict(eng)
            entry["_regions"] = [region] if region else []
            by_key[key] = entry

    return list(by_key.values())


def _build_engineers_section(num: int, report_data: dict) -> str:
    """Build the team performance section — supervisors table + field engineer progress bars."""
    engineers = report_data.get("engineers", [])
    if not engineers:
        return ""

    active_eng = [e for e in engineers if e.get("TotalTickets", 0) > 0]
    if not active_eng:
        return ""

    active_eng = _consolidate_engineers(active_eng)

    supervisor_roles = {"Supervisor", "Administrator", "Operations Manager",
                        "Project Manager", "Project Coordinator", "Logistics Supervisor"}

    supervisors = []
    field_engineers = []
    for eng in active_eng:
        role = eng.get("RoleName", "Field Engineer") or "Field Engineer"
        if role in supervisor_roles:
            supervisors.append(eng)
        else:
            field_engineers.append(eng)

    supervisors = sorted(supervisors, key=lambda e: e.get("TotalTickets", 0), reverse=True)
    field_engineers = sorted(field_engineers, key=lambda e: e.get("TotalTickets", 0), reverse=True)

    total_tickets = sum(e.get("TotalTickets", 0) for e in active_eng)
    total_completed = sum(e.get("CompletedTickets", 0) for e in active_eng)
    avg_rate = (total_completed / total_tickets * 100) if total_tickets > 0 else 0

    section_html = f'''<div class="section-block">
    <h2 class="section-heading"><span class="sec-num">{num:02d}</span> Team Performance</h2>
'''

    # ── Supervisors Table ──
    if supervisors:
        sv_total = sum(e.get("TotalTickets", 0) for e in supervisors)
        sv_completed = sum(e.get("CompletedTickets", 0) for e in supervisors)
        sv_rate = (sv_completed / sv_total * 100) if sv_total > 0 else 0

        section_html += f'    <p class="sub-label">Regional Supervisors &mdash; {_fmt_num(sv_total)} tickets &middot; {sv_rate:.1f}% completion</p>\n'
        section_html += '    <table class="compact-table">\n        <thead><tr><th>Name</th><th>Region</th><th>Total</th><th>Rate</th></tr></thead>\n        <tbody>\n'

        for eng in supervisors[:6]:
            name = eng.get("EmployeeName", eng.get("EngineerName", "Unknown"))
            regions = eng.get("_regions", [])
            if not regions:
                region = eng.get("RegionName", "")
                regions = [region] if region else []
            region_str = ", ".join(r for r in regions if r)[:40]
            completed = eng.get("CompletedTickets", 0)
            total_e = eng.get("TotalTickets", 0)
            rate_val = (completed / total_e * 100) if total_e > 0 else 0
            rate_color = "#10B981" if rate_val >= 50 else "#EF4444"

            section_html += f'''            <tr>
                <td class="name">{_esc(name)}</td>
                <td class="muted">{_esc(region_str)}</td>
                <td class="num">{_fmt_num(total_e)}</td>
                <td class="num" style="color:{rate_color};font-weight:700">{rate_val:.1f}%</td>
            </tr>
'''
        section_html += '        </tbody>\n    </table>\n'

    # ── Field Engineers Progress Bars ──
    if field_engineers:
        top_fe = field_engineers[:6]
        fe_total = sum(e.get("TotalTickets", 0) for e in field_engineers)
        fe_completed = sum(e.get("CompletedTickets", 0) for e in field_engineers)
        fe_rate = (fe_completed / fe_total * 100) if fe_total > 0 else 0
        max_tickets = max(e.get("TotalTickets", 1) for e in top_fe)

        section_html += f'\n    <p class="sub-label" style="margin-top:16px">Field Engineers &mdash; {_fmt_num(fe_total)} tickets &middot; {fe_rate:.1f}% completion</p>\n'

        eng_colors = ["#3B82F6", "#8B5CF6", "#06B6D4", "#10B981", "#F59E0B", "#EF4444", "#6366F1", "#EC4899"]
        for i, eng in enumerate(top_fe):
            name = eng.get("EmployeeName", eng.get("EngineerName", "Unknown"))
            completed = eng.get("CompletedTickets", 0)
            total_e = eng.get("TotalTickets", 0)
            rate_val = (completed / total_e * 100) if total_e > 0 else 0
            rate_str = f"{rate_val:.1f}%"
            rate_color = "#10B981" if rate_val > 0 else "#EF4444"
            color = eng_colors[i % len(eng_colors)]
            bar_pct = max((total_e / max_tickets * 100), 0.5) if max_tickets > 0 else 0.5

            section_html += f'''    <div class="eng-row">
        <div class="eng-top">
            <span class="eng-name">{_esc(name)}</span>
            <span class="eng-rate" style="color:{rate_color}">{rate_str}</span>
        </div>
        <div class="eng-bar-track">
            <div class="eng-bar-fill" style="width:{bar_pct:.1f}%;background:{color};min-width:3px"></div>
            <span class="eng-count">{_fmt_num(completed)}/{_fmt_num(total_e)}</span>
        </div>
    </div>
'''

    # Alert strip
    alert = ""
    if avg_rate < 40:
        alert = f'    <div class="alert-strip amber" style="margin-top:12px">&#9888; Low throughput: Review workload distribution and resource capacity.</div>\n'

    section_html += f'''{alert}</div>
'''
    return section_html


def _build_inventory_section(num: int, report_data: dict) -> str:
    """Build the inventory consumption — compact table with dark headers."""
    inventory = report_data.get("inventory", [])
    if not inventory:
        return ""

    item_totals = {}
    for txn in inventory:
        name = txn.get("ItemName", "Unknown")
        qty = txn.get("Quantity", 0)
        if qty > 0:
            if name in item_totals:
                item_totals[name] += qty
            else:
                item_totals[name] = qty

    if not item_totals:
        return ""

    sorted_items = sorted(item_totals.items(), key=lambda x: x[1], reverse=True)[:10]
    max_qty = sorted_items[0][1] if sorted_items else 1

    table_rows = ""
    for name, qty in sorted_items:
        pct = (qty / max_qty * 100) if max_qty > 0 else 0
        bar_w = f"{max(pct, 1):.0f}%"
        short_name = name[:28] + "..." if len(name) > 28 else name
        table_rows += f'''            <tr>
                <td class="name">{_esc(short_name)}</td>
                <td class="num">{_fmt_num(qty)}</td>
                <td><div class="bar-cell"><div class="bar-wrap"><div class="bar" style="width:{bar_w};background:#14B8A6"></div></div></div></td>
            </tr>
'''

    return f'''<div class="section-block">
    <h2 class="section-heading"><span class="sec-num">{num:02d}</span> Inventory Consumption</h2>
    <table class="compact-table">
        <thead>
            <tr><th>Item</th><th>Qty</th><th>Volume</th></tr>
        </thead>
        <tbody>
{table_rows}        </tbody>
    </table>
</div>
'''


def _build_certifications_section(num: int, report_data: dict) -> str:
    """Build the certifications status table — compact style."""
    certs = report_data.get("certifications", [])
    if not certs:
        return ""

    top = certs[:10]

    status_styles = {
        "Valid": ("#D1FAE5", "#065F46"),
        "Expired": ("#FEE2E2", "#B91C1C"),
        "Expiring": ("#FEF3C7", "#B45309"),
    }

    table_rows = ""
    for cert in top:
        name = cert.get("EmployeeName", "Unknown")
        cert_name = cert.get("CertificationName", "Unknown")
        status = cert.get("Status", "Unknown")
        expiry = cert.get("ExpiryDate", "N/A")

        badge_bg, badge_color = status_styles.get(status, ("#F1F5F9", "#64748B"))
        table_rows += f'''            <tr>
                <td class="name">{_esc(name)}</td>
                <td class="muted">{_esc(cert_name)}</td>
                <td><span class="badge" style="background:{badge_bg};color:{badge_color}">{_esc(status)}</span></td>
                <td class="muted">{_esc(expiry)}</td>
            </tr>
'''

    expired = sum(1 for c in certs if c.get("Status") == "Expired")
    alert = ""
    if expired > 0:
        alert = f'    <div class="alert-strip red">&#9888; {_fmt_num(expired)} certification(s) expired &mdash; renewals required.</div>\n'

    return f'''<div class="section-block">
    <h2 class="section-heading"><span class="sec-num">{num:02d}</span> Certification Status</h2>
    <table class="compact-table">
        <thead>
            <tr><th>Engineer</th><th>Certification</th><th>Status</th><th>Expiry</th></tr>
        </thead>
        <tbody>
{table_rows}        </tbody>
    </table>
{alert}</div>
'''
