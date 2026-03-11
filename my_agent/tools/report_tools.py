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

        print(f"[REPORT COLLECT] type={report_type}, projects={project_names}, "
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
                # Summary row (last result set usually)
                for rs_idx in range(len(rs) - 1, -1, -1):
                    if rs[rs_idx] and any("TotalTickets" in r for r in rs[rs_idx]):
                        report_data["ticket_totals"] = rs[rs_idx][0] if rs[rs_idx] else {}
                        break
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
                    totals = {}
                    for rs_idx in range(len(rs) - 1, -1, -1):
                        if rs[rs_idx] and any("TotalTickets" in r for r in rs[rs_idx]):
                            totals = rs[rs_idx][0] if rs[rs_idx] else {}
                            break
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

        print(f"[REPORT BUILD] title={title}, sections={report_data.get('sections_collected', [])}")

        logo_uri = _get_logo_base64()
        gen_date = datetime.now().strftime("%d %B %Y")

        # Build subtitle parts (only things NOT already in the title)
        subtitle_parts = []
        if report_data.get("team_names"):
            subtitle_parts.append(report_data["team_names"])
        if report_data.get("region_names"):
            subtitle_parts.append(report_data["region_names"])

        # Period
        if report_data.get("month") and report_data.get("year"):
            month_name = datetime(report_data["year"], report_data["month"], 1).strftime("%B %Y")
            subtitle_parts.append(month_name)
        elif report_data.get("date_from") and report_data.get("date_to"):
            subtitle_parts.append(f"{report_data['date_from']} to {report_data['date_to']}")
        elif report_data.get("year"):
            subtitle_parts.append(str(report_data["year"]))

        subtitle_parts.append(gen_date)
        subtitle_line = "&nbsp;&nbsp;&middot;&nbsp;&nbsp;".join(subtitle_parts)

        # ── Build HTML sections (numbered) ──
        sections_html = ""
        section_num = 1

        # Executive Summary
        if executive_summary:
            sections_html += _build_executive_summary(section_num, executive_summary)
            section_num += 1

        # KPI Cards (no number — visual grid)
        kpi_cards = _build_kpi_cards(report_data)
        if kpi_cards:
            sections_html += kpi_cards

        # Key Insights
        if insights:
            sections_html += _build_insights(section_num, insights)
            section_num += 1

        # Ticket Status Table + Chart
        totals = report_data.get("ticket_totals", {})
        has_ticket_data = totals.get("TotalTickets", 0) > 0
        if "tickets" in report_data.get("sections_collected", []) and has_ticket_data:
            sections_html += _build_ticket_section(section_num, report_data)
            section_num += 1

        # Task Type Breakdown + Chart
        type_data = report_data.get("ticket_types", [])
        has_type_data = any(td.get("TotalTickets", 0) > 0 for td in type_data)
        if "ticket_types" in report_data.get("sections_collected", []) and has_type_data:
            sections_html += _build_task_type_section(section_num, report_data)
            section_num += 1

        # Top Engineers + Chart
        engineers = report_data.get("engineers", [])
        has_eng_data = any(e.get("TotalTickets", 0) > 0 for e in engineers)
        if "engineers" in report_data.get("sections_collected", []) and has_eng_data:
            sections_html += _build_engineers_section(section_num, report_data)
            section_num += 1

        # Inventory
        inventory = report_data.get("inventory", [])
        has_inv_data = any(txn.get("Quantity", 0) > 0 for txn in inventory)
        if "inventory" in report_data.get("sections_collected", []) and has_inv_data:
            sections_html += _build_inventory_section(section_num, report_data)
            section_num += 1

        # Certifications
        certs = report_data.get("certifications", [])
        if "certifications" in report_data.get("sections_collected", []) and certs:
            sections_html += _build_certifications_section(section_num, report_data)
            section_num += 1

        # Discussion / Conclusion
        if discussion:
            sections_html += _build_discussion(section_num, discussion)
            section_num += 1

        # If no sections had data, show a message
        if not sections_html.strip():
            sections_html = '''<div class="no-data-msg">
    <div class="no-data-icon">&#128202;</div>
    <p>No data available for the selected filters and period.</p>
    <p style="font-size:13px;color:#94a3b8;margin-top:4px;">Try adjusting the project, date range, or team filters.</p>
</div>'''

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
<div class="report-header">
    <div class="header-content">
        <img src="{logo_uri}" alt="Ebttikar OIP" class="header-logo">
        <h1>{_esc(title)}</h1>
        <p class="header-meta">{subtitle_line}</p>
    </div>
</div>
<div class="report-body">
{sections_html}
</div>
<div class="report-footer">
    <div class="footer-line"></div>
    <div class="powered">Powered by Onasi</div>
    <div class="copyright">&copy; 2026 Onasi-CloudTech. All Rights Reserved.</div>
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
    """Return the complete CSS for the report."""
    return """* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #fff; color: #1e293b; line-height: 1.6; font-size: 14px; }

/* ── Header (white, centered logo) ── */
.report-header {
    background: #fff; padding: 36px 40px 24px; text-align: center;
    border-bottom: 2px solid #e2e8f0;
}
.header-content {}
.header-logo { height: 52px; margin-bottom: 20px; }
.header-content h1 { font-size: 22px; font-weight: 700; color: #1a4f71; margin-bottom: 8px; letter-spacing: -0.3px; }
.header-meta { font-size: 13px; color: #64748b; letter-spacing: 0.2px; }

/* ── Body ── */
.report-body { padding: 32px 40px; max-width: 920px; margin: 0 auto; }

/* ── Executive Summary ── */
.exec-summary {
    background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
    border-left: 4px solid #1a4f71; border-radius: 0 12px 12px 0;
    padding: 24px 28px; margin-bottom: 32px;
}
.exec-summary .section-title { margin-bottom: 12px; border-bottom: none; padding-bottom: 0; }
.exec-summary p { color: #334155; font-size: 14px; line-height: 1.7; }

/* ── KPI Cards ── */
.kpi-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 16px; margin-bottom: 32px;
}
.kpi-card {
    background: #fff; border-radius: 12px; padding: 20px 16px; text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06); border: 1px solid #e2e8f0;
    position: relative; overflow: hidden;
}
.kpi-card .kpi-value { font-size: 32px; font-weight: 800; margin-bottom: 4px; letter-spacing: -1px; }
.kpi-card .kpi-label { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 600; }

/* ── Insights ── */
.insights-box {
    background: #fefce8; border: 1px solid #fde68a; border-radius: 12px;
    padding: 24px 28px; margin-bottom: 32px;
}
.insights-box .section-title { border-bottom: none; padding-bottom: 0; margin-bottom: 14px; }
.insight-item {
    display: flex; align-items: flex-start; gap: 10px; padding: 8px 0;
    font-size: 14px; color: #334155;
}
.insight-icon {
    width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center;
    justify-content: center; font-size: 12px; flex-shrink: 0; margin-top: 1px;
}
.insight-positive { background: #dcfce7; color: #16a34a; }
.insight-warning { background: #fef3c7; color: #d97706; }
.insight-info { background: #dbeafe; color: #2563eb; }
.insight-achievement { background: #f3e8ff; color: #7c3aed; }

/* ── Discussion ── */
.discussion-box {
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    border-left: 4px solid #0ea5e9; border-radius: 0 12px 12px 0;
    padding: 24px 28px; margin-bottom: 32px;
}
.discussion-box .section-title { margin-bottom: 12px; border-bottom: none; padding-bottom: 0; }
.discussion-box p { color: #334155; font-size: 14px; line-height: 1.7; }

/* ── Sections ── */
.section { margin-bottom: 36px; }
.section-title {
    font-size: 16px; font-weight: 700; color: #1a4f71; margin-bottom: 16px;
    padding-bottom: 8px; border-bottom: 2px solid #68cce4;
    display: flex; align-items: center; gap: 10px;
}
.section-num {
    background: #1a4f71; color: white; width: 26px; height: 26px; border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 700; flex-shrink: 0;
}
.section-desc {
    font-size: 13px; color: #64748b; font-style: italic; margin-bottom: 16px;
    line-height: 1.5; padding-left: 2px;
}
.section-insight {
    font-size: 13px; color: #1a4f71; font-style: italic; margin-top: 12px;
    padding: 10px 14px; background: #f0f9ff; border-radius: 8px;
    border-left: 3px solid #68cce4; line-height: 1.5;
}

/* ── Charts (CSS-based) ── */
.chart-container {
    margin: 20px 0; padding: 16px; background: #fafbfc; border-radius: 10px;
    border: 1px solid #f1f5f9;
}
.chart-title {
    font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase;
    letter-spacing: 0.5px; margin-bottom: 14px;
}
.hbar-row {
    display: flex; align-items: center; gap: 12px; margin-bottom: 10px;
}
.hbar-label {
    width: 110px; font-size: 12px; font-weight: 500; color: #475569;
    text-align: right; flex-shrink: 0; white-space: nowrap; overflow: hidden;
    text-overflow: ellipsis;
}
.hbar-track {
    flex: 1; height: 22px; background: #f1f5f9; border-radius: 6px;
    overflow: hidden; position: relative;
}
.hbar-fill {
    height: 100%; border-radius: 6px; display: flex; align-items: center;
    padding-left: 8px; font-size: 11px; font-weight: 700; color: white;
    min-width: 28px; transition: width 0.3s ease;
}
.hbar-value {
    font-size: 12px; font-weight: 700; color: #334155; width: 40px;
    text-align: right; flex-shrink: 0;
}
.donut-container {
    display: flex; align-items: center; gap: 28px; justify-content: center;
    flex-wrap: wrap;
}
.donut {
    width: 140px; height: 140px; border-radius: 50%; position: relative;
    display: flex; align-items: center; justify-content: center;
}
.donut-hole {
    width: 80px; height: 80px; border-radius: 50%; background: #fafbfc;
    display: flex; align-items: center; justify-content: center;
    flex-direction: column; position: absolute;
}
.donut-total { font-size: 24px; font-weight: 800; color: #1e293b; }
.donut-label-small { font-size: 10px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; }
.donut-legend { display: flex; flex-direction: column; gap: 8px; }
.legend-item { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #475569; }
.legend-dot { width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }

/* ── Tables ── */
table { width: 100%; border-collapse: collapse; font-size: 13px; border-radius: 8px; overflow: hidden; }
thead th {
    background: #f1f5f9; color: #475569; font-weight: 600; text-align: left;
    padding: 12px 14px; border-bottom: 2px solid #e2e8f0; font-size: 12px;
    text-transform: uppercase; letter-spacing: 0.5px;
}
td { padding: 11px 14px; border-bottom: 1px solid #f1f5f9; }
tr:hover td { background: #f8fafc; }
tbody tr:last-child td { border-bottom: none; }

/* ── Status badges ── */
.status-badge {
    display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px;
    border-radius: 20px; font-weight: 600; font-size: 12px;
}
.pct-bar {
    display: inline-block; height: 6px; border-radius: 3px; min-width: 4px;
    vertical-align: middle; margin-left: 8px;
}

/* ── No data ── */
.no-data-msg {
    text-align: center; padding: 60px 20px; color: #64748b;
}
.no-data-icon { font-size: 48px; margin-bottom: 12px; }

/* ── Footer ── */
.report-footer {
    text-align: center; padding: 28px 40px 24px; margin-top: 20px;
}
.footer-line { height: 1px; background: linear-gradient(90deg, transparent, #cbd5e1, transparent); margin-bottom: 20px; }
.powered { font-size: 14px; font-weight: 700; color: #475569; margin-bottom: 4px; letter-spacing: 0.3px; }
.copyright { font-size: 12px; color: #94a3b8; }

/* ── Print ── */
@media print {
    body { -webkit-print-color-adjust: exact; print-color-adjust: exact; font-size: 12px; }
    .report-header, .kpi-card, table, .section, .exec-summary, .insights-box, .discussion-box, .chart-container { break-inside: avoid; }
    .report-header { padding: 20px 24px; }
    .report-body { padding: 16px 24px; }
    @page { size: A4; margin: 10mm; }
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
    """Build the executive summary section."""
    return f'''<div class="exec-summary">
    <div class="section-title"><span class="section-num">{num}</span> Executive Summary</div>
    <p>{_esc(summary_text)}</p>
</div>
'''


def _build_insights(num: int, insights_str: str) -> str:
    """Build the key insights section from pipe-separated string."""
    items = [i.strip() for i in insights_str.split("|") if i.strip()]
    if not items:
        return ""

    icon_map = {
        "positive": ("&#10003;", "insight-positive"),
        "warning": ("&#9888;", "insight-warning"),
        "info": ("&#8505;", "insight-info"),
        "achievement": ("&#9733;", "insight-achievement"),
    }

    items_html = ""
    for item in items:
        if ":" in item:
            cat, text = item.split(":", 1)
            cat = cat.strip().lower()
        else:
            cat, text = "info", item

        icon_char, icon_cls = icon_map.get(cat, ("&#8226;", "insight-info"))
        items_html += f'''    <div class="insight-item">
        <div class="insight-icon {icon_cls}">{icon_char}</div>
        <div>{_esc(text.strip())}</div>
    </div>
'''

    return f'''<div class="insights-box">
    <div class="section-title"><span class="section-num">{num}</span> Key Insights</div>
{items_html}</div>
'''


def _build_discussion(num: int, discussion_text: str) -> str:
    """Build the discussion/conclusion section."""
    return f'''<div class="discussion-box">
    <div class="section-title"><span class="section-num">{num}</span> Discussion &amp; Recommendations</div>
    <p>{_esc(discussion_text)}</p>
</div>
'''


def _build_kpi_cards(report_data: dict) -> str:
    """Build the KPI summary cards grid."""
    cards = []

    # Ticket KPIs
    totals = report_data.get("ticket_totals", {})
    if totals and totals.get("TotalTickets", 0) > 0:
        total = totals.get("TotalTickets", 0)
        completed = totals.get("CompletedTickets", 0)
        # Calculate rate from data (SP may return 0)
        rate = totals.get("CompletionRate", 0)
        if (rate == 0 or rate is None) and total > 0:
            rate = (completed / total) * 100
        rate_str = f"{rate:.1f}%" if isinstance(rate, float) else f"{rate}%"

        cards.append(("#3b82f6", _fmt_num(total), "Total Tickets"))
        cards.append(("#f59e0b", _fmt_num(totals.get("OpenTickets")), "Open"))
        cards.append(("#22c55e", _fmt_num(completed), f"Completed ({rate_str})"))
        cards.append(("#ef4444", _fmt_num(totals.get("SLABreached")), "SLA Breached"))

    # Task type KPIs
    type_data = report_data.get("ticket_types", [])
    for td in type_data:
        if td.get("TotalTickets", 0) > 0:
            if td["TaskType"] == "PM":
                cards.append(("#8b5cf6", _fmt_num(td["TotalTickets"]), "PM Tickets"))
            elif td["TaskType"] == "TR":
                cards.append(("#6366f1", _fmt_num(td["TotalTickets"]), "TR Calls"))

    # Engineer KPIs
    eng_summary = report_data.get("engineer_summary", {})
    if eng_summary and eng_summary.get("TotalEngineers", 0) > 0:
        cards.append(("#0ea5e9", _fmt_num(eng_summary.get("TotalEngineers")), "Engineers"))

    # Inventory KPIs
    inv_summary = report_data.get("inventory_summary", {})
    if inv_summary and inv_summary.get("TotalQuantity", 0) > 0:
        cards.append(("#14b8a6", _fmt_num(inv_summary.get("TotalQuantity")), "Parts Consumed"))

    if not cards:
        return ""

    cards_html = ""
    for color, value, label in cards:
        cards_html += f'''    <div class="kpi-card">
        <div style="position:absolute;top:0;left:0;right:0;height:4px;background:{color};border-radius:12px 12px 0 0;"></div>
        <div class="kpi-value" style="color:{color}">{value}</div>
        <div class="kpi-label">{_esc(label)}</div>
    </div>\n'''

    return f'<div class="kpi-grid">\n{cards_html}</div>\n'


def _build_ticket_section(num: int, report_data: dict) -> str:
    """Build the ticket status overview table with donut chart and insight."""
    totals = report_data.get("ticket_totals", {})
    total = totals.get("TotalTickets", 0)
    if total == 0:
        return ""

    open_t = totals.get("OpenTickets", 0)
    completed = totals.get("CompletedTickets", 0)
    suspended = totals.get("SuspendedTickets", 0)
    pending = totals.get("PendingApprovalTickets", 0)
    sla = totals.get("SLABreached", 0)

    # Calculate completion rate
    comp_rate = (completed / total * 100) if total > 0 else 0

    # Section description
    desc = (f"Overview of all {_fmt_num(total)} tickets across their lifecycle statuses. "
            f"The completion rate stands at {comp_rate:.1f}%, with {_fmt_num(open_t)} tickets still open.")

    # Build CSS donut chart
    segments = [
        ("Open", open_t, "#f59e0b"),
        ("Completed", completed, "#22c55e"),
        ("Suspended", suspended, "#f97316"),
        ("Pending", pending, "#8b5cf6"),
    ]
    # Filter zero segments
    segments = [(l, v, c) for l, v, c in segments if v > 0]

    donut_html = ""
    if segments:
        # Build conic-gradient
        gradient_parts = []
        cumulative = 0
        for label, val, color in segments:
            pct = val / total * 100
            gradient_parts.append(f"{color} {cumulative:.1f}% {cumulative + pct:.1f}%")
            cumulative += pct
        gradient = f"conic-gradient({', '.join(gradient_parts)})"

        # Legend
        legend_items = ""
        for label, val, color in segments:
            pct = val / total * 100
            legend_items += f'<div class="legend-item"><span class="legend-dot" style="background:{color}"></span>{label}: {_fmt_num(val)} ({pct:.1f}%)</div>\n'

        donut_html = f'''    <div class="chart-container">
        <div class="chart-title">Figure {num}.1 &mdash; Ticket Status Distribution</div>
        <div class="donut-container">
            <div class="donut" style="background:{gradient}">
                <div class="donut-hole">
                    <div class="donut-total">{_fmt_num(total)}</div>
                    <div class="donut-label-small">Total</div>
                </div>
            </div>
            <div class="donut-legend">
{legend_items}            </div>
        </div>
    </div>
'''

    # Table rows
    rows_data = [
        ("Open", open_t, "#f59e0b", "#fef3c7"),
        ("Completed", completed, "#22c55e", "#dcfce7"),
        ("Suspended", suspended, "#f97316", "#ffedd5"),
        ("Pending Approval", pending, "#8b5cf6", "#f3e8ff"),
        ("SLA Breached", sla, "#ef4444", "#fee2e2"),
    ]

    table_rows = ""
    for status, count, color, bg in rows_data:
        if count == 0:
            continue
        pct = (count / total * 100) if total > 0 else 0
        bar_width = max(4, min(120, int(pct * 1.2)))
        table_rows += f'''        <tr>
            <td><span class="status-badge" style="background:{bg};color:{color}">{status}</span></td>
            <td style="font-weight:600">{_fmt_num(count)}</td>
            <td>{pct:.1f}%<span class="pct-bar" style="width:{bar_width}px;background:{color}"></span></td>
        </tr>\n'''

    if not table_rows:
        return ""

    # Insight
    insight = ""
    if sla > 0:
        sla_pct = sla / total * 100
        if sla_pct > 50:
            insight = f'<div class="section-insight">&#9888; <strong>Attention:</strong> SLA breach rate is critically high at {sla_pct:.1f}% ({_fmt_num(sla)} of {_fmt_num(total)} tickets). Immediate review of response processes and resource allocation is recommended.</div>'
        elif sla_pct > 20:
            insight = f'<div class="section-insight">&#9888; <strong>Note:</strong> SLA breach rate of {sla_pct:.1f}% ({_fmt_num(sla)} tickets) exceeds acceptable thresholds. Consider reviewing ticket assignment workflows.</div>'
    elif comp_rate >= 80:
        insight = f'<div class="section-insight">&#10003; <strong>Strong performance:</strong> Completion rate of {comp_rate:.1f}% indicates effective ticket resolution processes.</div>'

    return f'''<div class="section">
    <div class="section-title"><span class="section-num">{num}</span> Ticket Status Overview</div>
    <p class="section-desc">{desc}</p>
{donut_html}    <table>
        <thead><tr><th>Status</th><th>Count</th><th>Distribution</th></tr></thead>
        <tbody>
{table_rows}        </tbody>
    </table>
{insight}
</div>
'''


def _build_task_type_section(num: int, report_data: dict) -> str:
    """Build the task type breakdown table with horizontal bar chart."""
    type_data = report_data.get("ticket_types", [])
    if not type_data:
        return ""

    active_types = [td for td in type_data if td.get("TotalTickets", 0) > 0]
    if not active_types:
        return ""

    total_all = sum(td["TotalTickets"] for td in active_types)
    max_val = max(td["TotalTickets"] for td in active_types)

    # Description
    type_summary = ", ".join(f"{td['TaskType']}: {_fmt_num(td['TotalTickets'])}" for td in active_types)
    dominant = max(active_types, key=lambda x: x["TotalTickets"])
    desc = (f"Breakdown of tickets by task type ({type_summary}). "
            f"{dominant['TaskType']} tickets represent the largest category at "
            f"{(dominant['TotalTickets']/total_all*100):.0f}% of total volume.")

    type_colors = {"PM": "#8b5cf6", "TR": "#6366f1", "Other": "#64748b"}
    type_bgs = {"PM": "#f3e8ff", "TR": "#e0e7ff", "Other": "#f1f5f9"}

    # Horizontal bar chart
    chart_bars = ""
    for td in active_types:
        tt = td["TaskType"]
        color = type_colors.get(tt, "#64748b")
        pct = (td["TotalTickets"] / max_val * 100) if max_val > 0 else 0
        chart_bars += f'''        <div class="hbar-row">
            <div class="hbar-label">{tt}</div>
            <div class="hbar-track"><div class="hbar-fill" style="width:{pct:.0f}%;background:{color}">{_fmt_num(td["TotalTickets"])}</div></div>
            <div class="hbar-value">{(td["TotalTickets"]/total_all*100):.0f}%</div>
        </div>\n'''

    chart_html = f'''    <div class="chart-container">
        <div class="chart-title">Figure {num}.1 &mdash; Ticket Volume by Task Type</div>
{chart_bars}    </div>
'''

    # Table
    table_rows = ""
    for td in active_types:
        tt = td["TaskType"]
        color = type_colors.get(tt, "#64748b")
        bg = type_bgs.get(tt, "#f1f5f9")
        table_rows += f'''        <tr>
            <td><span class="status-badge" style="background:{bg};color:{color}">{tt}</span></td>
            <td style="font-weight:600">{_fmt_num(td["TotalTickets"])}</td>
            <td>{_fmt_num(td["OpenTickets"])}</td>
            <td>{_fmt_num(td["CompletedTickets"])}</td>
            <td>{_fmt_num(td["SuspendedTickets"])}</td>
        </tr>\n'''

    # Insight
    pm_count = next((td["TotalTickets"] for td in active_types if td["TaskType"] == "PM"), 0)
    tr_count = next((td["TotalTickets"] for td in active_types if td["TaskType"] == "TR"), 0)
    insight = ""
    if pm_count > 0 and tr_count > 0:
        ratio = pm_count / tr_count if tr_count > 0 else 0
        if ratio > 2:
            insight = f'<div class="section-insight">&#8505; PM tickets outnumber TR calls by {ratio:.1f}:1, indicating a proactive maintenance focus. This helps reduce reactive incidents over time.</div>'
        elif ratio < 0.5:
            insight = f'<div class="section-insight">&#9888; TR calls ({_fmt_num(tr_count)}) significantly exceed PM tickets ({_fmt_num(pm_count)}). Consider increasing preventive maintenance schedules to reduce reactive workload.</div>'

    return f'''<div class="section">
    <div class="section-title"><span class="section-num">{num}</span> Tickets by Task Type</div>
    <p class="section-desc">{desc}</p>
{chart_html}    <table>
        <thead><tr><th>Type</th><th>Total</th><th>Open</th><th>Completed</th><th>Suspended</th></tr></thead>
        <tbody>
{table_rows}        </tbody>
    </table>
{insight}
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
    """Build the team performance section with supervisors and field engineers separated."""
    engineers = report_data.get("engineers", [])
    if not engineers:
        return ""

    # Filter out engineers with 0 tickets
    active_eng = [e for e in engineers if e.get("TotalTickets", 0) > 0]
    if not active_eng:
        return ""

    # Consolidate duplicate rows (same person across multiple regions)
    active_eng = _consolidate_engineers(active_eng)

    # Separate by role: Supervisors/Team Leads vs Field Engineers
    supervisor_roles = {"Supervisor", "Administrator", "Operations Manager",
                        "Project Manager", "Project Coordinator", "Logistics Supervisor"}
    field_roles = {"Field Engineer", "Resident Engineer"}

    supervisors = []
    field_engineers = []
    for eng in active_eng:
        role = eng.get("RoleName", "Field Engineer") or "Field Engineer"
        if role in supervisor_roles:
            supervisors.append(eng)
        else:
            field_engineers.append(eng)

    # Sort each group by completed desc
    supervisors = sorted(supervisors, key=lambda e: e.get("CompletedTickets", 0), reverse=True)
    field_engineers = sorted(field_engineers, key=lambda e: e.get("CompletedTickets", 0), reverse=True)

    total_tickets = sum(e.get("TotalTickets", 0) for e in active_eng)
    total_completed = sum(e.get("CompletedTickets", 0) for e in active_eng)
    avg_rate = (total_completed / total_tickets * 100) if total_tickets > 0 else 0

    fe_count = len(field_engineers)
    sv_count = len(supervisors)
    desc = (f"Performance metrics for {len(active_eng)} active team members "
            f"({sv_count} regional team lead{'s' if sv_count != 1 else ''}, "
            f"{fe_count} field engineer{'s' if fe_count != 1 else ''}) "
            f"handling a combined {_fmt_num(total_tickets)} tickets with an overall "
            f"completion rate of {avg_rate:.1f}%.")

    section_html = f'''<div class="section">
    <div class="section-title"><span class="section-num">{num}</span> Team Performance</div>
    <p class="section-desc">{desc}</p>
'''

    # ── Subsection: Regional Team Leads / Supervisors ──
    if supervisors:
        sv_total = sum(e.get("TotalTickets", 0) for e in supervisors)
        sv_completed = sum(e.get("CompletedTickets", 0) for e in supervisors)
        sv_rate = (sv_completed / sv_total * 100) if sv_total > 0 else 0

        sv_rows = ""
        for i, eng in enumerate(supervisors, 1):
            name = eng.get("EmployeeName", eng.get("EngineerName", "Unknown"))
            role = eng.get("RoleName", "Supervisor")
            regions = eng.get("_regions", [])
            if not regions:
                region = eng.get("RegionName", "")
                regions = [region] if region else []
            completed = eng.get("CompletedTickets", 0)
            total_e = eng.get("TotalTickets", 0)
            rate_val = (completed / total_e * 100) if total_e > 0 else 0
            rate_color = "#22c55e" if rate_val >= 80 else "#f59e0b" if rate_val >= 50 else "#ef4444"
            region_badges = "".join(
                f' <span style="background:#e0f2fe;color:#0369a1;padding:1px 6px;border-radius:8px;font-size:11px">{_esc(r)}</span>'
                for r in regions if r
            )

            sv_rows += f'''        <tr>
            <td>{i}</td>
            <td style="font-weight:600">{_esc(name)}{region_badges}</td>
            <td><span style="color:#6366f1;font-weight:500">{_esc(role)}</span></td>
            <td>{_fmt_num(total_e)}</td>
            <td>{_fmt_num(completed)}</td>
            <td><span style="color:{rate_color};font-weight:700">{rate_val:.1f}%</span></td>
        </tr>\n'''

        section_html += f'''    <div style="margin-top:16px">
        <div style="font-weight:700;font-size:15px;color:#1e293b;margin-bottom:8px">
            {num}.1 Regional Team Leads
            <span style="font-weight:400;color:#64748b;font-size:13px">&mdash; {sv_count} lead{'s' if sv_count != 1 else ''}, {_fmt_num(sv_total)} tickets overseen, {sv_rate:.1f}% completion</span>
        </div>
    </div>
    <table>
        <thead><tr><th style="width:40px">#</th><th>Name</th><th>Role</th><th>Total</th><th>Completed</th><th>Rate</th></tr></thead>
        <tbody>
{sv_rows}        </tbody>
    </table>
'''

    # ── Subsection: Field Engineers ──
    if field_engineers:
        top_fe = field_engineers[:15]
        fe_total = sum(e.get("TotalTickets", 0) for e in field_engineers)
        fe_completed = sum(e.get("CompletedTickets", 0) for e in field_engineers)
        fe_rate = (fe_completed / fe_total * 100) if fe_total > 0 else 0
        max_tickets = max(e.get("TotalTickets", 0) for e in top_fe)

        # Horizontal bar chart (top 8 field engineers)
        chart_bars = ""
        eng_colors = ["#3b82f6", "#6366f1", "#8b5cf6", "#0ea5e9", "#14b8a6", "#22c55e", "#f59e0b", "#ef4444"]
        for i, eng in enumerate(top_fe[:8]):
            name = eng.get("EmployeeName", eng.get("EngineerName", "Unknown"))
            short_name = name[:16] + "..." if len(name) > 16 else name
            total_e = eng.get("TotalTickets", 0)
            completed_e = eng.get("CompletedTickets", 0)
            pct = (total_e / max_tickets * 100) if max_tickets > 0 else 0
            color = eng_colors[i % len(eng_colors)]
            chart_bars += f'''        <div class="hbar-row">
            <div class="hbar-label">{_esc(short_name)}</div>
            <div class="hbar-track"><div class="hbar-fill" style="width:{pct:.0f}%;background:{color}">{_fmt_num(completed_e)}/{_fmt_num(total_e)}</div></div>
            <div class="hbar-value">{_fmt_num(total_e)}</div>
        </div>\n'''

        fig_label = f"{num}.2" if supervisors else f"{num}.1"
        chart_html = f'''    <div class="chart-container">
        <div class="chart-title">Figure {fig_label} &mdash; Ticket Assignment by Field Engineer (Completed / Total)</div>
{chart_bars}    </div>
''' if chart_bars else ""

        fe_rows = ""
        for i, eng in enumerate(top_fe, 1):
            name = eng.get("EmployeeName", eng.get("EngineerName", "Unknown"))
            regions = eng.get("_regions", [])
            if not regions:
                region = eng.get("RegionName", "")
                regions = [region] if region else []
            completed = eng.get("CompletedTickets", 0)
            total_e = eng.get("TotalTickets", 0)
            rate_val = (completed / total_e * 100) if total_e > 0 else 0
            rate_color = "#22c55e" if rate_val >= 80 else "#f59e0b" if rate_val >= 50 else "#ef4444"
            rank_html = f'<span style="background:#fef3c7;color:#d97706;padding:2px 8px;border-radius:12px;font-weight:700;font-size:12px">{i}</span>' if i <= 3 else str(i)
            region_badges = "".join(
                f' <span style="background:#e0f2fe;color:#0369a1;padding:1px 6px;border-radius:8px;font-size:11px">{_esc(r)}</span>'
                for r in regions if r
            )

            fe_rows += f'''        <tr>
            <td>{rank_html}</td>
            <td style="font-weight:600">{_esc(name)}{region_badges}</td>
            <td>{_fmt_num(total_e)}</td>
            <td>{_fmt_num(completed)}</td>
            <td><span style="color:{rate_color};font-weight:700">{rate_val:.1f}%</span></td>
        </tr>\n'''

        showing = f" (Top {len(top_fe)} of {fe_count})" if fe_count > 15 else ""
        sub_num = f"{num}.2" if supervisors else f"{num}.1"

        section_html += f'''    <div style="margin-top:20px">
        <div style="font-weight:700;font-size:15px;color:#1e293b;margin-bottom:8px">
            {sub_num} Field Engineers{showing}
            <span style="font-weight:400;color:#64748b;font-size:13px">&mdash; {fe_count} engineer{'s' if fe_count != 1 else ''}, {_fmt_num(fe_total)} tickets, {fe_rate:.1f}% completion</span>
        </div>
    </div>
{chart_html}    <table>
        <thead><tr><th style="width:50px">#</th><th>Engineer</th><th>Total</th><th>Completed</th><th>Rate</th></tr></thead>
        <tbody>
{fe_rows}        </tbody>
    </table>
'''

    # Insight
    insight = ""
    if avg_rate < 40:
        insight = f'<div class="section-insight">&#9888; <strong>Low throughput:</strong> The overall completion rate of {avg_rate:.1f}% indicates significant backlog. Consider reviewing workload distribution and resource capacity.</div>'
    elif field_engineers:
        best = field_engineers[0]
        best_name = best.get("EmployeeName", best.get("EngineerName", "Unknown"))
        best_completed = best.get("CompletedTickets", 0)
        best_total = best.get("TotalTickets", 0)
        best_rate = (best_completed / best_total * 100) if best_total > 0 else 0
        insight = f'<div class="section-insight">&#10003; <strong>Top performer:</strong> {_esc(best_name)} leads with {_fmt_num(best_completed)} completed tickets ({best_rate:.0f}% rate), handling {(best_total/total_tickets*100):.0f}% of the total workload.</div>'

    section_html += f'''{insight}
</div>
'''
    return section_html


def _build_inventory_section(num: int, report_data: dict) -> str:
    """Build the inventory consumption table with chart (capped at 15)."""
    inventory = report_data.get("inventory", [])
    if not inventory:
        return ""

    # Aggregate by item name
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

    sorted_items = sorted(item_totals.items(), key=lambda x: x[1], reverse=True)[:15]
    max_qty = sorted_items[0][1] if sorted_items else 1
    total_qty = sum(v for _, v in sorted_items)

    # Description
    inv_summary = report_data.get("inventory_summary", {})
    total_all = inv_summary.get("TotalQuantity", total_qty)
    unique_items = inv_summary.get("UniqueItems", len(item_totals))
    desc = (f"Spare parts consumption tracking across {_fmt_num(unique_items)} unique items "
            f"with {_fmt_num(total_all)} total units consumed. "
            f"The table shows the top items by consumption volume.")

    # Horizontal bar chart (top 8)
    chart_bars = ""
    inv_colors = ["#14b8a6", "#0ea5e9", "#3b82f6", "#6366f1", "#8b5cf6", "#22c55e", "#f59e0b", "#f97316"]
    for i, (name, qty) in enumerate(sorted_items[:8]):
        short_name = name[:22] + "..." if len(name) > 22 else name
        pct = (qty / max_qty * 100) if max_qty > 0 else 0
        color = inv_colors[i % len(inv_colors)]
        chart_bars += f'''        <div class="hbar-row">
            <div class="hbar-label" style="width:160px">{_esc(short_name)}</div>
            <div class="hbar-track"><div class="hbar-fill" style="width:{pct:.0f}%;background:{color}">{_fmt_num(qty)}</div></div>
            <div class="hbar-value">{_fmt_num(qty)}</div>
        </div>\n'''

    chart_html = f'''    <div class="chart-container">
        <div class="chart-title">Figure {num}.1 &mdash; Top Items by Consumption Volume</div>
{chart_bars}    </div>
''' if chart_bars else ""

    # Table
    table_rows = ""
    for name, qty in sorted_items:
        bar_width = max(4, int((qty / max_qty) * 100))
        table_rows += f'''        <tr>
            <td style="font-weight:500">{_esc(name)}</td>
            <td style="font-weight:600">{_fmt_num(qty)}</td>
            <td><span class="pct-bar" style="width:{bar_width}px;background:#14b8a6"></span></td>
        </tr>\n'''

    total_items = len(item_totals)
    showing = f" (Top {len(sorted_items)} of {total_items})" if total_items > 15 else ""

    # Insight
    insight = ""
    if sorted_items:
        top_name = sorted_items[0][0]
        top_qty = sorted_items[0][1]
        top_pct = (top_qty / total_all * 100) if total_all > 0 else 0
        if top_pct > 30:
            short = top_name[:30] + "..." if len(top_name) > 30 else top_name
            insight = f'<div class="section-insight">&#8505; <strong>Concentration:</strong> "{_esc(short)}" accounts for {top_pct:.0f}% of total consumption. Monitor stock levels for this high-usage item.</div>'

    return f'''<div class="section">
    <div class="section-title"><span class="section-num">{num}</span> Inventory Consumption{showing}</div>
    <p class="section-desc">{desc}</p>
{chart_html}    <table>
        <thead><tr><th>Item</th><th>Qty Consumed</th><th>Distribution</th></tr></thead>
        <tbody>
{table_rows}        </tbody>
    </table>
{insight}
</div>
'''


def _build_certifications_section(num: int, report_data: dict) -> str:
    """Build the certifications status table."""
    certs = report_data.get("certifications", [])
    if not certs:
        return ""

    top = certs[:15]

    # Description
    cert_summary = report_data.get("cert_summary", {})
    total_certs = cert_summary.get("TotalCertifications", len(certs))
    expired = sum(1 for c in certs if c.get("Status") == "Expired")
    expiring = sum(1 for c in certs if c.get("Status") == "Expiring")
    desc = (f"Certification compliance status for {_fmt_num(total_certs)} tracked certifications. "
            f"{_fmt_num(expired)} expired and {_fmt_num(expiring)} expiring soon." if expired or expiring
            else f"Certification compliance status for {_fmt_num(total_certs)} tracked certifications.")

    status_styles = {
        "Valid": ("background:#dcfce7;color:#16a34a", "&#10003;"),
        "Expired": ("background:#fee2e2;color:#dc2626", "&#10007;"),
        "Expiring": ("background:#fef3c7;color:#d97706", "&#9888;"),
    }

    table_rows = ""
    for cert in top:
        name = cert.get("EmployeeName", "Unknown")
        cert_name = cert.get("CertificationName", "Unknown")
        status = cert.get("Status", "Unknown")
        expiry = cert.get("ExpiryDate", "N/A")

        style, icon = status_styles.get(status, ("background:#f1f5f9;color:#64748b", "&#8226;"))
        table_rows += f'''        <tr>
            <td>{_esc(name)}</td>
            <td>{_esc(cert_name)}</td>
            <td><span class="status-badge" style="{style}">{icon} {_esc(status)}</span></td>
            <td>{_esc(expiry)}</td>
        </tr>\n'''

    # Insight
    insight = ""
    if expired > 0:
        insight = f'<div class="section-insight">&#9888; <strong>Action required:</strong> {_fmt_num(expired)} certification(s) have expired. Schedule renewals immediately to maintain compliance.</div>'

    return f'''<div class="section">
    <div class="section-title"><span class="section-num">{num}</span> Certification Status</div>
    <p class="section-desc">{desc}</p>
    <table>
        <thead><tr><th>Engineer</th><th>Certification</th><th>Status</th><th>Expiry Date</th></tr></thead>
        <tbody>
{table_rows}        </tbody>
    </table>
{insight}
</div>
'''
