"""
Database tools for OIP Ticket Analytics Agent.
Connects to SQL Server and executes stored procedures for ticket data.

Uses pyodbc for SQL Server connectivity.
Integrates with Google ADK ToolContext for session state access.

Supports multiple project/team selections via comma-separated values.
"""

import os
import logging
import struct
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
    driver = os.getenv("SQL_SERVER_DRIVER", "ODBC Driver 17 for SQL Server")
    trusted = os.getenv("SQL_SERVER_TRUSTED_CONNECTION", "").lower()

    connection_string = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        "TrustServerCertificate=yes;"
    )

    if trusted in ("yes", "true", "1"):
        connection_string += "Trusted_Connection=yes;"
    else:
        user = os.getenv("SQL_SERVER_USER", "")
        password = os.getenv("SQL_SERVER_PASSWORD", "")
        connection_string += f"UID={user};PWD={password};"

    conn = pyodbc.connect(connection_string)

    # Register converter for SQL Server's datetimeoffset type (ODBC type -155)
    # which pyodbc doesn't support natively. Converts to Python datetime.
    def _handle_datetimeoffset(dto_value):
        tup = struct.unpack("<6hI2h", dto_value)
        return datetime(tup[0], tup[1], tup[2], tup[3], tup[4], tup[5], tup[6] // 1000)

    conn.add_output_converter(-155, _handle_datetimeoffset)
    return conn


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


def get_lookups(
    lookup_type: Optional[str] = None,
    tool_context: "ToolContext" = None,
) -> dict:
    """
    Get lookup data from the database (regions, projects, teams, statuses).

    This tool retrieves reference data for dropdowns, validation, and queries.
    Use this when users ask "what regions are there?" or "list all teams".

    IMPORTANT: lookup_type values are CASE-SENSITIVE and must be EXACTLY one of:
    - "Regions" (capital R, plural) - Get all regions/provinces
    - "Projects" (capital P, plural) - Get all projects
    - "Teams" (capital T, plural) - Get all teams with their project and region
    - "Statuses" (capital S, plural) - Get ticket statuses
    - "All" (capital A) - Get all lookup types
    - None - Same as "All", gets everything

    Args:
        lookup_type: MUST be exactly one of: "Regions", "Projects", "Teams", "Statuses", "All"
                     DO NOT use lowercase like "region" or "teams" - it will return empty!

    Returns:
        dict: Lookup data containing requested types:
            - regions: List of {RegionId, RegionName, RegionCode}
            - projects: List of {ProjectId, ProjectName}
            - teams: List of {TeamId, TeamName, ProjectName, RegionName}
            - statuses: List of {StatusId, StatusCode, StatusName, StatusColor}
            - Message: "Success" or error description

    Example tool calls:
        - "What regions are available?" -> get_lookups(lookup_type="Regions")
        - "List all teams" -> get_lookups(lookup_type="Teams")
        - "What projects can I filter by?" -> get_lookups(lookup_type="Projects")
        - "Show me ticket statuses" -> get_lookups(lookup_type="Statuses")
        - "Show all lookup data" -> get_lookups(lookup_type="All")
    """
    try:
        logger.info(f"📋 Fetching lookups: {lookup_type or 'All'}")
        print(f"🔍 [LOOKUPS] lookup_type={lookup_type}")

        # Get username from session state for permission filtering
        username = None
        if tool_context is not None:
            username = tool_context.state.get("username")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build parameter list
        params = []
        param_markers = []

        if lookup_type:
            params.append(lookup_type)
            param_markers.append('@LookupType=?')

        if username:
            params.append(username)
            param_markers.append('@Username=?')

        # Execute stored procedure
        if param_markers:
            sql = f"EXEC usp_Chatbot_GetLookups {', '.join(param_markers)}"
        else:
            sql = "EXEC usp_Chatbot_GetLookups"

        logger.info("🔄 Querying lookup data...")
        cursor.execute(sql, params)

        result = {"Message": "Success"}

        # Process multiple result sets
        result_index = 0
        result_names = ["regions", "projects", "teams", "statuses"]

        while True:
            rows = cursor.fetchall()
            if rows:
                columns = [column[0] for column in cursor.description]
                data = [dict(zip(columns, row)) for row in rows]

                # Determine which result set this is based on columns
                if "RegionId" in columns or "RegionName" in columns:
                    result["regions"] = data
                elif "ProjectId" in columns and "TeamId" not in columns:
                    result["projects"] = data
                elif "TeamId" in columns:
                    result["teams"] = data
                elif "StatusId" in columns:
                    result["statuses"] = data
                else:
                    # Fallback: use index-based naming
                    if result_index < len(result_names):
                        result[result_names[result_index]] = data

                result_index += 1

            # Try to move to next result set
            if not cursor.nextset():
                break

        cursor.close()
        conn.close()

        # Log what we got
        for key in ["regions", "projects", "teams", "statuses"]:
            if key in result:
                print(f"📋 [LOOKUPS] {key}: {len(result[key])} items")

        # Store in session for future reference
        if tool_context is not None:
            tool_context.state["available_lookups"] = result
            logger.info("📝 Lookups stored in session")

        return result

    except pyodbc.Error as db_error:
        print(f"❌ [DB ERROR] {db_error}")
        import traceback
        traceback.print_exc()
        return {"Message": f"Database error: {str(db_error)}"}
    except Exception as e:
        print(f"❌ [ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"Message": f"Error: {type(e).__name__}: {str(e)}"}


def get_ticket_summary(
    project_names: Optional[str] = None,
    team_names: Optional[str] = None,
    region_names: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_breakdown: bool = False,
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
        region_names: Filter by region name(s). Optional.
                      Can be a single region like "Riyadh" or multiple
                      comma-separated regions like "Riyadh,Jeddah".
                      Case-insensitive partial match supported.
                      Examples: "Riyadh", "Eastern Province", "Makkah,Madinah"
        month: Filter by month (1-12). Optional.
               Use with year parameter for monthly filtering.
        year: Filter by year (e.g., 2025, 2026). Optional.
              Defaults to current year if month is provided without year.
        date_from: Start date for range filter in YYYY-MM-DD format. Optional.
                   Example: "2026-01-01"
        date_to: End date for range filter in YYYY-MM-DD format. Optional.
                 Example: "2026-01-19"
        include_breakdown: If True, returns additional breakdown by region, project, team.
                          Use this for "X vs Others" comparisons or distribution charts.
                          Example: "Riyadh vs other regions" -> include_breakdown=True

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
            - RegionFilter: Applied region filter or "All Regions"
            - DateRange: Applied date range or "All Time"
            - Message: "Success" or error description

            If include_breakdown=True, also includes:
            - by_region: List of {RegionName, TotalTickets, OpenTickets, CompletedTickets}
            - by_project: List of {ProjectName, TotalTickets, OpenTickets, CompletedTickets}
            - by_team: List of {TeamName, TotalTickets, OpenTickets, CompletedTickets}

    Example queries this tool can answer:
        - "What are my tickets?" -> No filters needed
        - "How are my ANB tickets?" -> project_names='ANB'
        - "Show me ANB and Barclays tickets" -> project_names='ANB,Barclays'
        - "Show me Maintenance team status" -> team_names='Maintenance'
        - "Tickets in Riyadh" -> region_names='Riyadh'
        - "Tickets in Eastern Province" -> region_names='Eastern Province'
        - "Riyadh and Jeddah tickets" -> region_names='Riyadh,Jeddah'
        - "My tickets this month" -> month=1 + year=2026
        - "Tickets from last month" -> month=12 + year=2025
        - "Tickets last week" -> date_from='2026-01-12' + date_to='2026-01-19'
        - "ANB project tickets in December" -> project_names='ANB' + month=12 + year=2025
        - "Riyadh vs other regions" -> include_breakdown=True (then aggregate)
        - "Show tickets by region" -> include_breakdown=True
        - "Compare projects" -> include_breakdown=True

    Note:
        The stored procedure enforces role-based access control:
        - Engineers see only their assigned tickets
        - Supervisors see all tickets from their teams
        - Admins/PMs can see all project tickets
    """
    try:
        logger.info("📊 Checking your ticket status...")
        # Debug: Log incoming parameters
        print(f"🔍 [TOOL PARAMS] project_names={project_names}, team_names={team_names}, region_names={region_names}, month={month}, year={year}, include_breakdown={include_breakdown}")

        # Get username from session state via tool_context
        username = None
        project_context = None
        team_context = None

        if tool_context is not None:
            username = tool_context.state.get("username")

            # NOTE: We NO LONGER use session state for project/team filters
            # The filter context is now injected directly into the message via [ACTIVE_TEAM_FILTER] tags
            # The LLM reads these tags and passes the correct team_names/project_names to this tool
            # This avoids ADK session state timing issues

            print(f"🔍 [LLM PARAMS] project_names={project_names}, team_names={team_names}, region_names={region_names}")

        # Log final values used for query
        print(f"🔍 [QUERY] username={username}, project_names={project_names}, team_names={team_names}, region_names={region_names}")

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

        if region_names:
            params.append(region_names)
            param_markers.append('@RegionNames=?')

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

        if include_breakdown:
            params.append(1)
            param_markers.append('@IncludeBreakdown=?')

        # Execute stored procedure
        sql = f"EXEC usp_Chatbot_GetTicketSummary {', '.join(param_markers)}"
        logger.info("🔄 Analyzing ticket data...")
        cursor.execute(sql, params)

        # Fetch result (first result set is always the summary)
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

        # If include_breakdown=True, fetch additional result sets
        # SP returns in fixed order: by_region, by_project, by_team
        if include_breakdown:
            breakdown_order = ["by_region", "by_project", "by_team"]
            breakdown_index = 0

            while cursor.nextset():
                rows = cursor.fetchall()
                if rows and cursor.description:
                    columns = [column[0] for column in cursor.description]
                    data = []
                    for r in rows:
                        row_dict = dict(zip(columns, r))
                        # Convert numeric fields and Decimal to proper types
                        for key in row_dict:
                            val = row_dict[key]
                            if val is not None:
                                # Handle Decimal type
                                if hasattr(val, 'as_tuple'):  # Decimal check
                                    row_dict[key] = float(val)
                                elif isinstance(val, (int, float)) or 'Tickets' in key:
                                    try:
                                        row_dict[key] = int(val) if isinstance(val, int) or (isinstance(val, float) and val.is_integer()) else float(val)
                                    except (ValueError, TypeError):
                                        pass
                        data.append(row_dict)

                    # Use fixed order from SP
                    if breakdown_index < len(breakdown_order):
                        key = breakdown_order[breakdown_index]
                        result[key] = data
                        print(f"📊 [BREAKDOWN] {key}: {len(data)} items")

                    breakdown_index += 1

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
            if region_names:
                query_context_parts.append(f"region {region_names}")
            if month:
                query_context_parts.append(f"month {month}")
            tool_context.state["last_query_context"] = " ".join(query_context_parts) if query_context_parts else "all tickets"
            logger.info("📝 Ticket data stored in session for chart requests")

        return result

    except pyodbc.Error as db_error:
        print(f"❌ [DB ERROR] {db_error}")
        import traceback
        traceback.print_exc()
        return {
            "TotalTickets": 0,
            "Message": f"Database error: {str(db_error)}"
        }
    except Exception as e:
        print(f"❌ [ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {
            "TotalTickets": 0,
            "Message": f"Error: {type(e).__name__}: {str(e)}"
        }


def get_ticket_timeline(
    period: str = "month",
    project_names: Optional[str] = None,
    team_names: Optional[str] = None,
    region_names: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    tool_context: "ToolContext" = None,
) -> dict:
    """
    Get ticket creation and completion counts grouped by time period.

    Returns aggregated timeline data suitable for line or area charts.
    Use this when users ask about ticket trends over time, creation rates,
    or want to see how tickets were created/completed over weeks or months.

    After calling this tool, use create_tickets_over_time_chart() to visualize
    the returned data as a line or area chart.

    Args:
        period: Time grouping period. One of:
                - "week" — group by week (good for last 1-3 months)
                - "month" — group by month (default, good for 3-12 months)
                - "quarter" — group by quarter (good for 1-2 years)
                - "year" — group by year (good for multi-year overview)
        project_names: Filter by project name(s). Comma-separated for multiple.
        team_names: Filter by team name(s). Comma-separated for multiple.
        region_names: Filter by region name(s). Comma-separated for multiple.
        date_from: Start date in YYYY-MM-DD format. Defaults to last 12 months.
        date_to: End date in YYYY-MM-DD format. Defaults to today.

    Returns:
        dict: Timeline data containing:
            - timeline: List of {Period, TicketsCreated, TicketsCompleted}
            - period_type: The grouping used (week/month/quarter/year)
            - date_range: Applied date range
            - filters: Applied filters
            - Message: "Success" or error description

    Example queries:
        - "Show ticket creation trend" -> get_ticket_timeline()
        - "Weekly ticket trend for ANB" -> get_ticket_timeline(period="week", project_names="Arab National Bank")
        - "How many tickets were created last 3 months?" -> get_ticket_timeline(date_from="2025-12-01")
        - "Yearly ticket overview" -> get_ticket_timeline(period="year")
        - "Ticket trend for Maintenance team" -> get_ticket_timeline(team_names="Maintenance")
    """
    try:
        logger.info("📈 Fetching ticket timeline...")
        print(f"🔍 [TIMELINE] period={period}, projects={project_names}, teams={team_names}, regions={region_names}, from={date_from}, to={date_to}")

        # Get username from session state
        username = None
        if tool_context is not None:
            username = tool_context.state.get("username")

        if not username:
            return {"timeline": [], "Message": "Error: Username not found in session. Please ensure you are logged in."}

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build parameter list
        params = [username]
        param_markers = ['@Username=?']

        if project_names:
            params.append(project_names)
            param_markers.append('@ProjectNames=?')

        if team_names:
            params.append(team_names)
            param_markers.append('@TeamNames=?')

        if region_names:
            params.append(region_names)
            param_markers.append('@RegionNames=?')

        if period:
            params.append(period)
            param_markers.append('@Period=?')

        if date_from:
            params.append(date_from)
            param_markers.append('@DateFrom=?')

        if date_to:
            params.append(date_to)
            param_markers.append('@DateTo=?')

        sql = f"EXEC usp_Chatbot_GetTicketTimeline {', '.join(param_markers)}"
        logger.info("🔄 Querying ticket timeline...")
        cursor.execute(sql, params)

        rows = cursor.fetchall()
        timeline = []

        if rows and cursor.description:
            columns = [col[0] for col in cursor.description]
            for row in rows:
                row_dict = dict(zip(columns, row))
                # Ensure numeric values are proper types
                for key in row_dict:
                    val = row_dict[key]
                    if val is not None and isinstance(val, (int, float)):
                        row_dict[key] = int(val) if isinstance(val, int) or (isinstance(val, float) and val.is_integer()) else float(val)
                    elif val is not None and hasattr(val, 'as_tuple'):
                        row_dict[key] = float(val)
                timeline.append(row_dict)

        cursor.close()
        conn.close()

        print(f"📈 [TIMELINE] Got {len(timeline)} periods")

        result = {
            "timeline": timeline,
            "period_type": period,
            "date_range": f"{date_from or 'last 12 months'} to {date_to or 'today'}",
            "filters": {
                "projects": project_names or "All",
                "teams": team_names or "All",
                "regions": region_names or "All",
            },
            "Message": "Success" if timeline else "No timeline data found for the given filters.",
        }

        # Store in session for follow-up chart requests
        if tool_context is not None:
            tool_context.state["last_ticket_data"] = result
            tool_context.state["last_query_type"] = "ticket_timeline"

        return result

    except pyodbc.Error as db_error:
        print(f"❌ [DB ERROR] {db_error}")
        import traceback
        traceback.print_exc()
        return {"timeline": [], "Message": f"Database error: {str(db_error)}"}
    except Exception as e:
        print(f"❌ [ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"timeline": [], "Message": f"Error: {type(e).__name__}: {str(e)}"}


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


def get_pm_checklist_data(
    site_name: Optional[str] = None,
    field_name: Optional[str] = None,
    field_value: Optional[str] = None,
    sub_category_name: Optional[str] = None,
    pm_code: Optional[str] = None,
    ticket_status: Optional[str] = None,
    category_name: Optional[str] = None,
    project_names: Optional[str] = None,
    team_names: Optional[str] = None,
    region_names: Optional[str] = None,
    city_names: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    latest_only: bool = True,
    tool_context: "ToolContext" = None,
) -> dict:
    """
    Retrieve PM (Preventive Maintenance) checklist data from the TickTraq database.

    Use this tool for questions about site equipment collected during PM visits:
    Panel IPs, NVR IPs, keypad models, door contacts, motion detectors, PM codes, etc.

    Three query modes (determined automatically by which parameters you provide):
      1. Extension mode: Set field_name or field_value to get IPs, models, serial numbers
      2. Equipment mode: Set sub_category_name to get equipment quantities per site
      3. Overview mode: Set neither to get PM visit summaries

    Args:
        site_name: Filter by site name. Supports partial match — "730" matches "A730".
        field_name: Extension field to retrieve. Values include:
                    "Panel IP", "NVR IP", "Keypad Model", "Partition Type",
                    "Recording started on", "Panel Model", "DVR Model".
        field_value: Search by a specific field value, e.g. "D1255B" or "173.31.1.244".
                     Matches across all field names.
        sub_category_name: Equipment/sub-category name. Values include:
                          "Door Contact", "Motion Detector", "Siren", "Keypad",
                          "Panic Button", "Glass Break Detector", "Smoke Detector".
        pm_code: Filter by PM visit code (e.g. "CD627").
        ticket_status: Filter by ticket status. Use "Closed" for completed PM visits.
                       Values: "Open", "Closed".
        category_name: Filter by system category: "CCTV System", "Intrusion Alarm System",
                       "CCTV", "Intrusion Alarm".
        project_names: Comma-separated project names to filter by (e.g. "ANB,Barclays").
        team_names: Comma-separated team names (e.g. "Central,Western,Eastern").
                    Teams are organizational groups (Central, Maintenance, etc.).
        region_names: Comma-separated geographic region/province names (e.g. "Riyadh,Makkah").
                      Regions are StateProvince-level: "Riyadh", "Makkah", "Madinah",
                      "Eastern Province", "Asir", "Tabuk", "Hail", "Northern Borders",
                      "Jazan", "Najran", "Al Bahah", "Al Jawf", "Al Qassim".
        city_names: Comma-separated city names (e.g. "Jeddah,Medina,Taif").
                    Cities are within regions, e.g. Jeddah is in Makkah region.
        date_from: Start date filter on PM visit date, in YYYY-MM-DD format (e.g. "2026-01-01").
        date_to: End date filter on PM visit date, in YYYY-MM-DD format (e.g. "2026-01-31").
        latest_only: If True (default), returns only the latest PM visit per site.
                     Set to False to get all historical visits.

    Returns:
        dict containing:
            - records: List of row dicts (fields depend on query mode)
            - summary: Dict with TotalSites, optional TotalQuantity, Filters
            - query_mode: "extension", "equipment", or "overview"
            - count: Number of records returned
            - Message: "Success" or error description

    Example queries:
        - "What is the panel IP for ATM 730?"
          -> get_pm_checklist_data(site_name="730", field_name="Panel IP")
        - "List all Panel IPs for completed PM sites"
          -> get_pm_checklist_data(field_name="Panel IP", ticket_status="Closed")
        - "How many ATMs have keypad model D1255B?"
          -> get_pm_checklist_data(field_value="D1255B")
        - "Which sites have what keypad models?"
          -> get_pm_checklist_data(field_name="Keypad Model")
        - "How many total Door Contacts are installed?"
          -> get_pm_checklist_data(sub_category_name="Door Contact")
        - "How many PMs completed in Central team in January?"
          -> get_pm_checklist_data(team_names="Central", ticket_status="Closed", date_from="2026-01-01", date_to="2026-01-31")
        - "PMs in Riyadh region last month"
          -> get_pm_checklist_data(region_names="Riyadh", date_from="2026-02-01", date_to="2026-02-28")
        - "Sites in Jeddah city"
          -> get_pm_checklist_data(city_names="Jeddah")
    """
    try:
        logger.info("🔧 Fetching PM checklist data...")
        print(f"🔍 [PM] site={site_name}, field_name={field_name}, field_value={field_value}, "
              f"sub_cat={sub_category_name}, pm_code={pm_code}, status={ticket_status}, "
              f"category={category_name}, projects={project_names}, teams={team_names}, "
              f"regions={region_names}, cities={city_names}, "
              f"date_from={date_from}, date_to={date_to}, latest={latest_only}")

        # Get username from session state
        username = None
        if tool_context is not None:
            username = tool_context.state.get("username")

        if not username:
            return {"records": [], "summary": {}, "query_mode": "unknown", "count": 0,
                    "Message": "Error: Username not found in session. Please ensure you are logged in."}

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build parameter list
        params = [username]
        param_markers = ['@Username=?']

        if site_name:
            params.append(site_name)
            param_markers.append('@SiteName=?')
        if field_name:
            params.append(field_name)
            param_markers.append('@FieldName=?')
        if field_value:
            params.append(field_value)
            param_markers.append('@FieldValue=?')
        if sub_category_name:
            params.append(sub_category_name)
            param_markers.append('@SubCategoryName=?')
        if pm_code:
            params.append(pm_code)
            param_markers.append('@PMCode=?')
        if ticket_status:
            params.append(ticket_status)
            param_markers.append('@TicketStatus=?')
        if category_name:
            params.append(category_name)
            param_markers.append('@CategoryName=?')
        if project_names:
            params.append(project_names)
            param_markers.append('@ProjectNames=?')
        if team_names:
            params.append(team_names)
            param_markers.append('@TeamNames=?')
        if region_names:
            params.append(region_names)
            param_markers.append('@RegionNames=?')
        if city_names:
            params.append(city_names)
            param_markers.append('@CityNames=?')
        if date_from:
            params.append(date_from)
            param_markers.append('@DateFrom=?')
        if date_to:
            params.append(date_to)
            param_markers.append('@DateTo=?')
        if not latest_only:
            params.append(0)
            param_markers.append('@LatestOnly=?')

        sql = f"EXEC usp_Chatbot_GetPMChecklistData {', '.join(param_markers)}"
        logger.info("🔄 Querying PM checklist data...")
        cursor.execute(sql, params)

        # Result Set 1: Detail rows
        rows = cursor.fetchall()
        records = []
        sp_early_return = None
        if rows and cursor.description:
            columns = [col[0] for col in cursor.description]
            # Detect SP early-return error (e.g. "No matching projects found", "User not found")
            if columns == ['TotalResults', 'Message']:
                sp_early_return = dict(zip(columns, rows[0]))
                print(f"⚠️ [PM] SP early return: {sp_early_return}")
            else:
                for row in rows:
                    row_dict = dict(zip(columns, row))
                    # Convert datetime/Decimal to serializable types
                    for key in row_dict:
                        val = row_dict[key]
                        if val is not None:
                            if hasattr(val, 'isoformat'):  # datetime
                                row_dict[key] = val.isoformat()
                            elif hasattr(val, 'as_tuple'):  # Decimal
                                row_dict[key] = float(val)
                    records.append(row_dict)

        # Result Set 2: Summary
        summary = {}
        if cursor.nextset():
            summary_rows = cursor.fetchall()
            if summary_rows and cursor.description:
                summary_cols = [col[0] for col in cursor.description]
                summary = dict(zip(summary_cols, summary_rows[0]))
                # Convert Decimal/datetime in summary
                for key in summary:
                    val = summary[key]
                    if val is not None:
                        if hasattr(val, 'isoformat'):
                            summary[key] = val.isoformat()
                        elif hasattr(val, 'as_tuple'):
                            summary[key] = float(val)

        cursor.close()
        conn.close()

        # Determine query mode
        if field_name or field_value:
            query_mode = "extension"
        elif sub_category_name:
            query_mode = "equipment"
        else:
            query_mode = "overview"

        print(f"🔧 [PM] mode={query_mode}, records={len(records)}, summary={summary}")

        # Cross-project hint: if 0 records with site_name + project filter,
        # check if the site exists in a different project the user has access to
        no_results_message = (
            sp_early_return['Message'] if sp_early_return
            else "No PM checklist data found matching the criteria."
        )
        if not records and site_name and project_names:
            try:
                hint_conn = get_db_connection()
                hint_cursor = hint_conn.cursor()
                # Re-run without project filter to see if site exists elsewhere
                hint_params = [username, site_name]
                hint_markers = ['@Username=?', '@SiteName=?']
                if field_name:
                    hint_params.append(field_name)
                    hint_markers.append('@FieldName=?')
                hint_sql = f"EXEC usp_Chatbot_GetPMChecklistData {', '.join(hint_markers)}"
                hint_cursor.execute(hint_sql, hint_params)
                hint_rows = hint_cursor.fetchall()
                if hint_rows and hint_cursor.description:
                    hint_cols = [c[0] for c in hint_cursor.description]
                    # Check if we got actual data rows (not "User not found" etc.)
                    if 'SiteName' in hint_cols:
                        # Find which project(s) the site belongs to
                        found_projects = set()
                        for r in hint_rows:
                            rd = dict(zip(hint_cols, r))
                            # Look up project name from ticket
                            found_projects.add(rd.get('SiteName', ''))
                        # Get the actual project name via a quick query
                        hint_cursor.close()
                        hint_cursor = hint_conn.cursor()
                        hint_cursor.execute(
                            "SELECT DISTINCT p.Name FROM Tickets t "
                            "INNER JOIN Projects p ON p.Id = t.ProjectId "
                            "WHERE t.SiteName LIKE '%' + ? + '%' AND t.IsActive = 1",
                            [site_name]
                        )
                        proj_rows = hint_cursor.fetchall()
                        if proj_rows:
                            actual_projects = [r[0] for r in proj_rows]
                            no_results_message = (
                                f"Site '{site_name}' was not found in the currently selected project "
                                f"({project_names}). This site exists in: {', '.join(actual_projects)}. "
                                f"Please select the correct project or remove the project filter to see results."
                            )
                            print(f"🔍 [PM HINT] Site found in other project(s): {actual_projects}")
                hint_cursor.close()
                hint_conn.close()
            except Exception as hint_err:
                print(f"⚠️ [PM HINT] Cross-project check failed: {hint_err}")

        result = {
            "records": records,
            "summary": summary,
            "query_mode": query_mode,
            "count": len(records),
            "Message": "Success" if records else no_results_message,
        }

        # Store in session for follow-up chart requests
        if tool_context is not None:
            tool_context.state["last_pm_data"] = result
            tool_context.state["last_query_type"] = "pm_checklist"
            # Build query context description
            ctx_parts = []
            if field_name:
                ctx_parts.append(field_name)
            if field_value:
                ctx_parts.append(f"value '{field_value}'")
            if sub_category_name:
                ctx_parts.append(sub_category_name)
            if site_name:
                ctx_parts.append(f"site {site_name}")
            tool_context.state["last_query_context"] = " ".join(ctx_parts) if ctx_parts else "PM checklist"
            logger.info("📝 PM data stored in session for chart requests")

        return result

    except pyodbc.Error as db_error:
        print(f"❌ [DB ERROR] {db_error}")
        import traceback
        traceback.print_exc()
        return {"records": [], "summary": {}, "query_mode": "unknown", "count": 0,
                "Message": f"Database error: {str(db_error)}"}
    except Exception as e:
        print(f"❌ [ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"records": [], "summary": {}, "query_mode": "unknown", "count": 0,
                "Message": f"Error: {type(e).__name__}: {str(e)}"}


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
                    - "pie": True pie chart - solid filled circle with slices (no hole in center)
                    - "donut": Donut chart - ring with hollow center (2-5 metrics)
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
