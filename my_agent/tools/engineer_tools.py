"""
Engineer performance and certification tools for the OIP Assistant.
Queries SQL Server stored procedures for engineer-level ticket analytics
and certification status tracking.
"""

import logging
from typing import Optional
from datetime import datetime

from .db_tools import get_db_connection

# Configure logger
logger = logging.getLogger("oip_assistant.tools.engineer")

# Import ToolContext for session state access
try:
    from google.adk.tools import ToolContext
except ImportError:
    ToolContext = None


def get_engineer_performance(
    employee_names: Optional[str] = None,
    project_names: Optional[str] = None,
    team_names: Optional[str] = None,
    region_names: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_activity: bool = False,
    tool_context: "ToolContext" = None,
) -> dict:
    """
    Get engineer performance data — tickets completed, task type breakdown, and optionally daily activity logs.

    Use this tool when users ask about engineer productivity, tickets completed by specific engineers,
    task type distributions (TR/PM/Other), or team performance at the engineer level.

    Args:
        employee_names: Filter by engineer name(s). Optional.
                        Comma-separated, partial match on first + last name.
                        Examples: "Areeb", "Mohammed,Ahmed", "areeb ahmed"
        project_names: Filter by project name(s). Optional.
                       Comma-separated like "ANB,Barclays".
        team_names: Filter by team name(s). Optional.
                    Comma-separated like "Central,Maintenance".
        region_names: Filter by region/province name(s). Optional.
                      Comma-separated like "Riyadh,Eastern Province".
        month: Filter by month (1-12). Optional.
        year: Filter by year (e.g., 2025, 2026). Optional.
        date_from: Start date in YYYY-MM-DD format. Optional.
        date_to: End date in YYYY-MM-DD format. Optional.
        include_activity: If True, includes DailyActivityLog breakdown (activity types, hours, distance).
                          Use for "activity type distributions", "how many hours worked".

    Returns:
        dict containing:
            - engineers: List of engineer performance rows (name, tickets, completion rate, task types)
            - summary: Aggregate totals (TotalEngineers, TotalTickets, OverallCompletionRate, etc.)
            - activity_log: List of activity entries (only if include_activity=True)
            - count: Number of engineers returned
            - Message: "Success" or error description

    Example queries:
        - "How many tickets completed by Areeb?" -> employee_names="Areeb"
        - "Engineer performance in January" -> month=1, year=2026
        - "Central team engineer stats" -> team_names="Central"
        - "Activity type distributions" -> include_activity=True
        - "Tickets completed by teams in January" -> month=1, year=2026
    """
    try:
        # Get username from session
        username = None
        if tool_context is not None:
            username = tool_context.state.get("username")

        if not username:
            return {"status": "error", "Message": "No username in session. Please log in first."}

        logger.info(f"📊 Engineer performance query: employees={employee_names}, projects={project_names}, "
                     f"teams={team_names}, month={month}, year={year}, activity={include_activity}")
        print(f"🔍 [ENGINEER PERF] username={username}, employees={employee_names}, "
              f"projects={project_names}, teams={team_names}, month={month}, year={year}")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build parameter list
        params = [username]
        param_markers = ['@Username=?']

        if employee_names:
            params.append(employee_names)
            param_markers.append('@EmployeeNames=?')
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
        if year is not None:
            params.append(year)
            param_markers.append('@Year=?')
        if date_from:
            params.append(date_from)
            param_markers.append('@DateFrom=?')
        if date_to:
            params.append(date_to)
            param_markers.append('@DateTo=?')
        if include_activity:
            params.append(1)
            param_markers.append('@IncludeActivity=?')

        sql = f"EXEC usp_Chatbot_GetEngineerPerformance {', '.join(param_markers)}"
        logger.info(f"🔄 Executing: {sql}")
        cursor.execute(sql, params)

        # Result Set 1: Engineer rows
        engineers = []
        rows = cursor.fetchall()
        if rows and cursor.description:
            columns = [col[0] for col in cursor.description]
            for row in rows:
                eng = {}
                for i, col in enumerate(columns):
                    val = row[i]
                    if isinstance(val, datetime):
                        val = val.strftime("%Y-%m-%d")
                    elif hasattr(val, 'as_tuple'):  # Decimal
                        val = float(val)
                    eng[col] = val
                engineers.append(eng)

        # Result Set 2: Summary
        summary = {}
        if cursor.nextset():
            rows = cursor.fetchall()
            if rows and cursor.description:
                columns = [col[0] for col in cursor.description]
                row = rows[0]
                for i, col in enumerate(columns):
                    val = row[i]
                    if hasattr(val, 'as_tuple'):
                        val = float(val)
                    summary[col] = val

        # Check for early exit (error message from SP)
        if not engineers and summary.get("Message") and summary.get("Message") != "Success":
            return {"status": "error", "Message": summary["Message"], "engineers": [], "summary": summary, "count": 0}

        # Result Set 3: Activity log (only if include_activity=True)
        activity_log = []
        if include_activity:
            if cursor.nextset():
                rows = cursor.fetchall()
                if rows and cursor.description:
                    columns = [col[0] for col in cursor.description]
                    for row in rows:
                        entry = {}
                        for i, col in enumerate(columns):
                            val = row[i]
                            if isinstance(val, datetime):
                                val = val.strftime("%Y-%m-%d")
                            elif hasattr(val, 'as_tuple'):
                                val = float(val)
                            entry[col] = val
                        activity_log.append(entry)

        cursor.close()
        conn.close()

        result = {
            "status": "success",
            "engineers": engineers,
            "summary": summary,
            "count": len(engineers),
            "Message": summary.get("Message", "Success"),
        }

        if include_activity:
            result["activity_log"] = activity_log

        # Store in session for charting
        if tool_context is not None:
            tool_context.state["last_engineer_data"] = result
            tool_context.state["last_query_context"] = "engineer_performance"
            logger.info(f"📝 Stored {len(engineers)} engineers in session")

        print(f"✅ [ENGINEER PERF] {len(engineers)} engineers, "
              f"total_tickets={summary.get('TotalTickets', 0)}, "
              f"completion={summary.get('OverallCompletionRate', 0)}%")

        return result

    except Exception as e:
        print(f"❌ [ENGINEER ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "Message": f"Error: {type(e).__name__}: {str(e)}", "engineers": [], "summary": {}, "count": 0}


def get_certification_status(
    project_names: Optional[str] = None,
    employee_names: Optional[str] = None,
    expiring_within_days: int = 90,
    show_all: bool = False,
    tool_context: "ToolContext" = None,
) -> dict:
    """
    Get engineer certification status — expiring, expired, and valid certifications.

    Use this tool when users ask about certification expiry, compliance status,
    or whether all engineers are certified for a project.

    Note: The certification table may be empty if no certification data has been entered yet.
    In that case, the tool returns a helpful message explaining this.

    Args:
        project_names: Filter by project name(s). Optional.
                       Comma-separated like "ANB,Barclays".
        employee_names: Filter by engineer name(s). Optional.
                        Comma-separated, partial match. "Areeb", "Mohammed,Ahmed"
        expiring_within_days: Show certs expiring within N days (default: 90).
                              Use 30 for "expiring this month", 180 for "expiring in 6 months".
        show_all: If True, shows all certifications including valid ones.
                  If False (default), shows only expiring/expired.

    Returns:
        dict containing:
            - certifications: List of certification records (engineer, cert name, status, expiry)
            - summary: Aggregate counts (TotalEngineers, ValidCerts, ExpiredCerts, ExpiringSoonCerts)
            - count: Number of certification records returned
            - Message: "Success" or error/info description

    Example queries:
        - "Which certifications are expiring?" -> (defaults work)
        - "Are all engineers certified for ANB?" -> project_names="ANB", show_all=True
        - "Certifications expiring in 30 days" -> expiring_within_days=30
        - "Show all engineer certifications" -> show_all=True
    """
    try:
        username = None
        if tool_context is not None:
            username = tool_context.state.get("username")

        if not username:
            return {"status": "error", "Message": "No username in session. Please log in first."}

        logger.info(f"📋 Certification query: projects={project_names}, employees={employee_names}, "
                     f"within_days={expiring_within_days}, show_all={show_all}")
        print(f"🔍 [CERTS] username={username}, projects={project_names}, "
              f"employees={employee_names}, days={expiring_within_days}")

        conn = get_db_connection()
        cursor = conn.cursor()

        params = [username]
        param_markers = ['@Username=?']

        if project_names:
            params.append(project_names)
            param_markers.append('@ProjectNames=?')
        if employee_names:
            params.append(employee_names)
            param_markers.append('@EmployeeNames=?')
        if expiring_within_days != 90:
            params.append(expiring_within_days)
            param_markers.append('@ExpiringWithinDays=?')
        if show_all:
            params.append(1)
            param_markers.append('@ShowAll=?')

        sql = f"EXEC usp_Chatbot_GetCertificationStatus {', '.join(param_markers)}"
        logger.info(f"🔄 Executing: {sql}")
        cursor.execute(sql, params)

        # Result Set 1: Certification records
        certifications = []
        rows = cursor.fetchall()
        if rows and cursor.description:
            columns = [col[0] for col in cursor.description]
            for row in rows:
                cert = {}
                for i, col in enumerate(columns):
                    val = row[i]
                    if isinstance(val, datetime):
                        val = val.strftime("%Y-%m-%d")
                    elif hasattr(val, 'as_tuple'):
                        val = float(val)
                    cert[col] = val
                certifications.append(cert)

        # Result Set 2: Summary
        summary = {}
        if cursor.nextset():
            rows = cursor.fetchall()
            if rows and cursor.description:
                columns = [col[0] for col in cursor.description]
                row = rows[0]
                for i, col in enumerate(columns):
                    val = row[i]
                    if hasattr(val, 'as_tuple'):
                        val = float(val)
                    summary[col] = val

        cursor.close()
        conn.close()

        # Handle empty certification table gracefully
        total_certs = summary.get("TotalCertifications", 0)
        if total_certs == 0 and not certifications:
            message = ("No certification data has been entered yet. "
                       "The certification module is available but no employee certifications have been recorded. "
                       "Please ask your HR or admin team to add certification data.")
        else:
            message = summary.get("Message", "Success")

        result = {
            "status": "success",
            "certifications": certifications,
            "summary": summary,
            "count": len(certifications),
            "Message": message,
        }

        # Store in session for charting
        if tool_context is not None:
            tool_context.state["last_certification_data"] = result
            tool_context.state["last_query_context"] = "certification_status"
            logger.info(f"📝 Stored {len(certifications)} certifications in session")

        print(f"✅ [CERTS] {len(certifications)} records, "
              f"expired={summary.get('ExpiredCerts', 0)}, "
              f"expiring={summary.get('ExpiringSoonCerts', 0)}")

        return result

    except Exception as e:
        print(f"❌ [CERT ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "Message": f"Error: {type(e).__name__}: {str(e)}", "certifications": [], "summary": {}, "count": 0}
