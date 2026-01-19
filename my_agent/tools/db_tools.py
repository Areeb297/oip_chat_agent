"""
Database tools for OIP Ticket Analytics Agent.
Connects to SQL Server and executes stored procedures for ticket data.

Uses pyodbc for SQL Server connectivity.
Integrates with Google ADK ToolContext for session state access.

Supports multiple project/team selections via comma-separated values.
"""

import os
import logging
import pyodbc
from typing import Optional, List, Union
from datetime import datetime, timedelta

# Configure logger for this module
logger = logging.getLogger("oip_assistant.tools.db")

# Import ToolContext for session state access
try:
    from google.adk.tools import ToolContext
except ImportError:
    ToolContext = None


def get_db_connection():
    """
    Create SQL Server connection using environment variables or defaults.

    Returns:
        pyodbc.Connection: Active database connection

    Raises:
        pyodbc.Error: If connection fails
    """
    # Build connection string from env vars or use defaults
    server = os.getenv("SQL_SERVER_HOST", "LAPTOP-3BGTAL2E\\SQLEXPRESS")
    database = os.getenv("SQL_SERVER_DATABASE", "TickTraq")
    user = os.getenv("SQL_SERVER_USER", "areeb297")
    password = os.getenv("SQL_SERVER_PASSWORD", "Nightingale@0987")
    driver = os.getenv("SQL_SERVER_DRIVER", "ODBC Driver 17 for SQL Server")

    connection_string = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
    )

    return pyodbc.connect(connection_string)


def get_current_date() -> dict:
    """
    Get current date information for context.

    Returns a dictionary with current date details that can be used
    for time-based filtering and display.

    Returns:
        dict: Current date information including:
            - today: Current date in YYYY-MM-DD format
            - current_month: Current month number (1-12)
            - current_month_name: Full month name (e.g., "January")
            - current_year: Current year (e.g., 2026)
            - last_month: Previous month number (1-12)
            - last_month_name: Previous month name
            - last_month_year: Year of the previous month
    """
    now = datetime.now()
    last_month = now.month - 1 if now.month > 1 else 12
    last_month_year = now.year if now.month > 1 else now.year - 1

    return {
        "today": now.strftime("%Y-%m-%d"),
        "current_month": now.month,
        "current_month_name": now.strftime("%B"),
        "current_year": now.year,
        "last_month": last_month,
        "last_month_name": datetime(last_month_year, last_month, 1).strftime("%B"),
        "last_month_year": last_month_year,
    }


def get_ticket_summary(
    project_names: Optional[str] = None,
    team_names: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    tool_context: "ToolContext" = None,
) -> dict:
    """
    Get ticket summary for the logged-in user from TickTraq database.

    This tool retrieves ticket statistics for the logged-in user by calling
    the usp_Chatbot_GetTicketSummary stored procedure. The stored procedure
    automatically scopes results to only the teams and projects the user
    has access to based on their role.

    The username is automatically retrieved from the session context.

    Args:
        project_names: Filter by project name(s). Optional.
                       Can be a single project like "ANB" or multiple
                       comma-separated projects like "ANB,Barclays".
                       Case-insensitive partial match supported.
        team_names: Filter by team name(s). Optional.
                    Can be a single team like "Maintenance" or multiple
                    comma-separated teams like "Maintenance,Test Team".
                    Case-insensitive partial match supported.
        month: Filter by month (1-12). Optional.
               Use with year parameter for monthly filtering.
        year: Filter by year (e.g., 2025, 2026). Optional.
              Defaults to current year if month is provided without year.
        date_from: Start date for range filter in YYYY-MM-DD format. Optional.
                   Example: "2026-01-01"
        date_to: End date for range filter in YYYY-MM-DD format. Optional.
                 Example: "2026-01-19"

    Returns:
        dict: Ticket summary containing:
            - TotalTickets: Total count of tickets matching filters
            - OpenTickets: Number of tickets in Open status
            - SuspendedTickets: Number of tickets in Suspended status
            - CompletedTickets: Number of tickets marked Complete
            - PendingApproval: Tickets awaiting supervisor approval
            - SLABreached: Tickets that have breached their SLA deadline
            - CompletionRate: Percentage of completed tickets (0-100)
            - Username: The queried username
            - UserRole: User's role (Engineer/Supervisor/Admin/PM)
            - ProjectFilter: Applied project filter or "All Projects"
            - TeamFilter: Applied team filter or "All Teams"
            - DateRange: Applied date range or "All Time"
            - Message: "Success" or error description

    Example queries this tool can answer:
        - "What are my tickets?" -> No filters needed
        - "How are my ANB tickets?" -> project_names='ANB'
        - "Show me ANB and Barclays tickets" -> project_names='ANB,Barclays'
        - "Show me Maintenance team status" -> team_names='Maintenance'
        - "My tickets this month" -> month=1 + year=2026
        - "Tickets from last month" -> month=12 + year=2025
        - "Tickets last week" -> date_from='2026-01-12' + date_to='2026-01-19'
        - "ANB project tickets in December" -> project_names='ANB' + month=12 + year=2025

    Note:
        The stored procedure enforces role-based access control:
        - Engineers see only their assigned tickets
        - Supervisors see all tickets from their teams
        - Admins/PMs can see all project tickets
    """
    try:
        logger.info("📊 Checking your ticket status...")

        # Get username from session state via tool_context
        username = None
        project_context = None
        team_context = None

        if tool_context is not None:
            username = tool_context.state.get("username")
            # Also get project/team context from session if not overridden by query
            if project_names is None:
                project_context = tool_context.state.get("projectCode")
                if project_context:
                    project_names = project_context
            if team_names is None:
                team_context = tool_context.state.get("team")
                if team_context:
                    team_names = team_context

        # Username is required - error if not found
        if not username:
            logger.warning("⚠️ Please log in to view your tickets")
            return {
                "TotalTickets": 0,
                "Message": "Error: Username not found in session. Please ensure you are logged in."
            }

        logger.info(f"👤 Retrieving data for {username}...")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build parameter list for stored procedure
        params = [username]
        param_markers = ['@Username=?']

        if project_names:
            params.append(project_names)
            param_markers.append('@ProjectNames=?')

        if team_names:
            params.append(team_names)
            param_markers.append('@TeamNames=?')

        if month is not None:
            params.append(month)
            param_markers.append('@Month=?')
            # Default year to current if month provided without year
            if year is None:
                year = datetime.now().year

        if year is not None:
            params.append(year)
            param_markers.append('@Year=?')

        if date_from:
            params.append(date_from)
            param_markers.append('@DateFrom=?')

        if date_to:
            params.append(date_to)
            param_markers.append('@DateTo=?')

        # Execute stored procedure
        sql = f"EXEC usp_Chatbot_GetTicketSummary {', '.join(param_markers)}"
        logger.info("🔄 Analyzing ticket data...")
        cursor.execute(sql, params)

        # Fetch result
        row = cursor.fetchone()
        logger.info("✅ Ticket summary ready")

        if row:
            columns = [column[0] for column in cursor.description]
            result = dict(zip(columns, row))

            # Ensure numeric fields are proper types for JSON serialization
            numeric_fields = ['TotalTickets', 'OpenTickets', 'SuspendedTickets',
                            'CompletedTickets', 'PendingApproval', 'SLABreached']
            for field in numeric_fields:
                if field in result and result[field] is not None:
                    result[field] = int(result[field])

            # Handle completion rate
            if 'CompletionRate' in result and result['CompletionRate'] is not None:
                result['CompletionRate'] = round(float(result['CompletionRate']), 2)
        else:
            result = {
                "TotalTickets": 0,
                "OpenTickets": 0,
                "SuspendedTickets": 0,
                "CompletedTickets": 0,
                "PendingApproval": 0,
                "SLABreached": 0,
                "CompletionRate": 0.0,
                "Username": username,
                "UserRole": "Unknown",
                "Message": "No tickets found matching the criteria"
            }

        cursor.close()
        conn.close()

        # IMPORTANT: Store result in session state for "chart the above" requests
        if tool_context is not None:
            tool_context.state["last_ticket_data"] = result
            tool_context.state["last_query_type"] = "ticket_summary"
            # Store the query context for follow-up chart requests
            # Build context string from the filters used
            query_context_parts = []
            if project_names:
                query_context_parts.append(f"project {project_names}")
            if team_names:
                query_context_parts.append(f"team {team_names}")
            if month:
                query_context_parts.append(f"month {month}")
            tool_context.state["last_query_context"] = " ".join(query_context_parts) if query_context_parts else "all tickets"
            logger.info("📝 Ticket data stored in session for chart requests")

        return result

    except pyodbc.Error as db_error:
        return {
            "TotalTickets": 0,
            "Message": f"Database error: {str(db_error)}"
        }
    except Exception as e:
        return {
            "TotalTickets": 0,
            "Message": f"Error: {str(e)}"
        }


def calculate_date_range(period: str) -> tuple[Optional[str], Optional[str]]:
    """
    Calculate date range from natural language period.

    Helper function to convert common time expressions to date ranges.

    Args:
        period: Natural language period like "last week", "last 7 days", "Q4 2025"

    Returns:
        tuple: (date_from, date_to) in YYYY-MM-DD format, or (None, None) if not recognized
    """
    today = datetime.now().date()

    period_lower = period.lower().strip()

    if period_lower in ("last week", "past week"):
        date_to = today
        date_from = today - timedelta(days=7)
        return (date_from.strftime("%Y-%m-%d"), date_to.strftime("%Y-%m-%d"))

    if period_lower in ("last 7 days", "past 7 days"):
        date_to = today
        date_from = today - timedelta(days=7)
        return (date_from.strftime("%Y-%m-%d"), date_to.strftime("%Y-%m-%d"))

    if period_lower in ("last 30 days", "past 30 days", "past month"):
        date_to = today
        date_from = today - timedelta(days=30)
        return (date_from.strftime("%Y-%m-%d"), date_to.strftime("%Y-%m-%d"))

    if period_lower in ("this week",):
        # Start of current week (Monday)
        date_from = today - timedelta(days=today.weekday())
        date_to = today
        return (date_from.strftime("%Y-%m-%d"), date_to.strftime("%Y-%m-%d"))

    # Quarter handling
    if "q1" in period_lower:
        year = _extract_year(period_lower) or today.year
        return (f"{year}-01-01", f"{year}-03-31")

    if "q2" in period_lower:
        year = _extract_year(period_lower) or today.year
        return (f"{year}-04-01", f"{year}-06-30")

    if "q3" in period_lower:
        year = _extract_year(period_lower) or today.year
        return (f"{year}-07-01", f"{year}-09-30")

    if "q4" in period_lower:
        year = _extract_year(period_lower) or today.year
        return (f"{year}-10-01", f"{year}-12-31")

    return (None, None)


def _extract_year(text: str) -> Optional[int]:
    """Extract 4-digit year from text."""
    import re
    match = re.search(r'20\d{2}', text)
    if match:
        return int(match.group())
    return None


def create_chart_from_session(
    metrics: List[str],
    chart_type: str,
    title: str,
    tool_context: "ToolContext" = None,
) -> str:
    """
    Create a chart using ticket data stored in the session.

    This tool is FLEXIBLE - YOU decide exactly which metrics to visualize.
    Pass a list of metric names and the tool will chart them.

    Args:
        metrics: List of metrics to include in the chart. Available metrics:
                 - "open" - Open tickets count
                 - "completed" - Completed tickets count
                 - "suspended" - Suspended tickets count
                 - "pending" - Pending approval count
                 - "breached" - SLA breached tickets count
                 - "within_sla" - Tickets within SLA (total - breached)
                 - "non_suspended" - Non-suspended tickets (total - suspended)
                 - "non_open" - Non-open tickets (total - open)
                 - "remaining" - Remaining tickets (total - completed)
                 - "total" - Total ticket count
                 - "completion_rate" - Completion rate percentage (use with gauge)

        chart_type: Chart type to render:
                    - "bar": Bar chart for comparisons (2+ metrics)
                    - "donut": Donut chart for distributions (2-5 metrics)
                    - "gauge": Gauge for single percentage value

        title: Descriptive title for the chart.

        tool_context: ADK ToolContext for accessing session state

    Returns:
        str: Chart configuration in HTML format with Recharts JSON.

    Examples:
        # Suspended vs non-suspended
        create_chart_from_session(
            metrics=["suspended", "non_suspended"],
            chart_type="bar",
            title="Suspended Tickets Analysis"
        )

        # SLA breach analysis
        create_chart_from_session(
            metrics=["breached", "within_sla"],
            chart_type="bar",
            title="SLA Breach Analysis"
        )

        # Full status distribution
        create_chart_from_session(
            metrics=["open", "completed", "suspended", "pending"],
            chart_type="donut",
            title="Ticket Status Distribution"
        )

        # Completion rate
        create_chart_from_session(
            metrics=["completion_rate"],
            chart_type="gauge",
            title="Completion Rate"
        )

        # Open vs completed comparison
        create_chart_from_session(
            metrics=["open", "completed"],
            chart_type="bar",
            title="Open vs Completed Tickets"
        )
    """
    # Import chart tools here to avoid circular imports
    from .chart_tools import (
        create_completion_rate_gauge,
        create_chart
    )

    # Check if we have session context
    if tool_context is None:
        return "<p><span style='color:#dc2626'>Error: No session context available.</span></p>"

    # Get last ticket data from session state
    last_data = tool_context.state.get("last_ticket_data")

    if not last_data:
        return """<p><span style='color:#f59e0b'>⚠️ No previous ticket data found in this session.</span></p>
<p>Please ask for ticket data first (e.g., "What are my tickets?"), then I can create a chart for you.</p>"""

    print(f"📊 [CHART] Creating chart - Metrics: {metrics}, Type: {chart_type}, Title: {title}")
    logger.info(f"📊 Creating chart - Metrics: {metrics}, Type: {chart_type}, Title: {title}")

    # Extract raw values from stored data
    raw_data = {
        "open": last_data.get("OpenTickets", 0),
        "completed": last_data.get("CompletedTickets", 0),
        "suspended": last_data.get("SuspendedTickets", 0),
        "pending": last_data.get("PendingApproval", 0),
        "breached": last_data.get("SLABreached", 0),
        "total": last_data.get("TotalTickets", 0),
        "completion_rate": last_data.get("CompletionRate", 0),
    }

    # Calculate derived metrics
    raw_data["within_sla"] = raw_data["total"] - raw_data["breached"]
    raw_data["non_suspended"] = raw_data["total"] - raw_data["suspended"]
    raw_data["non_open"] = raw_data["total"] - raw_data["open"]
    raw_data["remaining"] = raw_data["total"] - raw_data["completed"]

    # Metric display labels and colors
    metric_config = {
        "open": {"label": "Open", "color": "#3b82f6"},
        "completed": {"label": "Completed", "color": "#22c55e"},
        "suspended": {"label": "Suspended", "color": "#f59e0b"},
        "pending": {"label": "Pending Approval", "color": "#8b5cf6"},
        "breached": {"label": "SLA Breached", "color": "#ef4444"},
        "within_sla": {"label": "Within SLA", "color": "#22c55e"},
        "non_suspended": {"label": "Non-Suspended", "color": "#22c55e"},
        "non_open": {"label": "Non-Open", "color": "#22c55e"},
        "remaining": {"label": "Remaining", "color": "#f59e0b"},
        "total": {"label": "Total", "color": "#3b82f6"},
        "completion_rate": {"label": "Completion Rate", "color": "#3b82f6"},
    }

    # Handle gauge chart for completion_rate
    if chart_type == "gauge" or (len(metrics) == 1 and metrics[0] == "completion_rate"):
        return create_completion_rate_gauge(
            completion_rate=raw_data["completion_rate"],
            target_rate=80.0,
            title=title
        )

    # Build chart data from requested metrics
    chart_data = []
    colors = []

    for metric in metrics:
        metric_lower = metric.lower().replace(" ", "_").replace("-", "_")
        if metric_lower in raw_data:
            config = metric_config.get(metric_lower, {"label": metric.title(), "color": "#64748b"})
            value = raw_data[metric_lower]
            chart_data.append({
                "category": config["label"],
                "count": value,
                "color": config["color"]
            })
            colors.append(config["color"])
        else:
            logger.warning(f"Unknown metric: {metric}")

    if not chart_data:
        return "<p><span style='color:#dc2626'>Error: No valid metrics specified.</span></p>"

    # Generate description
    total = raw_data["total"]
    if len(chart_data) == 2:
        m1, m2 = chart_data[0], chart_data[1]
        description = f"{m1['category']}: {m1['count']} ({m1['count']/total*100:.1f}%) vs {m2['category']}: {m2['count']} ({m2['count']/total*100:.1f}%)" if total > 0 else "No data"
    else:
        description = f"Distribution across {len(chart_data)} categories (Total: {total})"

    print(f"📊 [CHART] Chart data prepared: {len(chart_data)} categories")
    logger.info(f"📊 Chart data prepared: {chart_data}")

    chart_output = create_chart(
        data=chart_data,
        title=title,
        x_key="category",
        y_keys=["count"],
        chart_type=chart_type,
        description=description,
        colors=colors
    )

    # Log first 200 chars of output to verify format
    print(f"📊 [CHART] Output preview: {chart_output[:200]}...")

    return chart_output
