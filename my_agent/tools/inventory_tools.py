"""
Inventory consumption tools for the OIP Assistant.
Queries SQL Server stored procedures for spare parts usage,
consumption tracking, and invoicing site lists.
"""

import logging
from typing import Optional
from datetime import datetime

from .db_tools import get_db_connection

# Configure logger
logger = logging.getLogger("oip_assistant.tools.inventory")

# Import ToolContext for session state access
try:
    from google.adk.tools import ToolContext
except ImportError:
    ToolContext = None


def get_inventory_consumption(
    project_names: Optional[str] = None,
    item_name: Optional[str] = None,
    item_code: Optional[str] = None,
    category_name: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    transaction_type: str = "OUT",
    tool_context: "ToolContext" = None,
) -> dict:
    """
    Get inventory consumption data — spare parts used, returned, or all transactions.

    Use this tool when users ask about spare parts consumed, inventory usage,
    which sites received parts, or consumption reports for invoicing.

    Args:
        project_names: Filter by project name(s). Optional.
                       Comma-separated like "ANB,Barclays".
        item_name: Filter by item/part name. Optional. Partial match.
                   Examples: "cable", "camera", "power supply"
        item_code: Filter by item code. Optional. Partial match.
                   Examples: "02318169", "CAT 6"
        category_name: Filter by category/subcategory name. Optional. Partial match.
                       Examples: "CCTV", "cable", "connector"
        month: Filter by month (1-12). Optional.
        year: Filter by year (e.g., 2025, 2026). Optional.
        date_from: Start date in YYYY-MM-DD format. Optional.
        date_to: End date in YYYY-MM-DD format. Optional.
        transaction_type: Type of transaction to filter. Default "OUT" (consumed).
                          Options: "OUT" (consumed/issued), "IN" (returned), "ALL" (both)

    Returns:
        dict containing:
            - transactions: List of transaction records (item, quantity, site, date, project)
            - summary: Aggregate totals (TotalTransactions, UniqueItems, TotalQuantity, UniqueSites)
            - count: Number of transaction records returned
            - Message: "Success" or error description

    Example queries:
        - "How many spare parts consumed in January?" -> month=1, year=2026
        - "List sites where cable was used" -> item_name="cable"
        - "Consumption for part 02318169" -> item_code="02318169"
        - "Parts used for ANB project" -> project_names="ANB"
        - "Get consumption for invoicing" -> transaction_type="OUT"
        - "Parts returned this month" -> transaction_type="IN", month=current
        - "All CCTV parts used" -> category_name="CCTV"
    """
    try:
        username = None
        if tool_context is not None:
            username = tool_context.state.get("username")

        if not username:
            return {"status": "error", "Message": "No username in session. Please log in first."}

        logger.info(f"📦 Inventory query: item={item_name}, code={item_code}, "
                     f"category={category_name}, month={month}, year={year}, type={transaction_type}")
        print(f"🔍 [INVENTORY] username={username}, item={item_name}, code={item_code}, "
              f"projects={project_names}, month={month}, year={year}, type={transaction_type}")

        conn = get_db_connection()
        cursor = conn.cursor()

        params = [username]
        param_markers = ['@Username=?']

        if project_names:
            params.append(project_names)
            param_markers.append('@ProjectNames=?')
        if item_name:
            params.append(item_name)
            param_markers.append('@ItemName=?')
        if item_code:
            params.append(item_code)
            param_markers.append('@ItemCode=?')
        if category_name:
            params.append(category_name)
            param_markers.append('@CategoryName=?')
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
        if transaction_type and transaction_type != "OUT":
            params.append(transaction_type)
            param_markers.append('@TransactionType=?')

        sql = f"EXEC usp_Chatbot_GetInventoryConsumption {', '.join(param_markers)}"
        logger.info(f"🔄 Executing: {sql}")
        cursor.execute(sql, params)

        # Result Set 1: Transaction detail
        transactions = []
        rows = cursor.fetchall()
        if rows and cursor.description:
            columns = [col[0] for col in cursor.description]
            for row in rows:
                txn = {}
                for i, col in enumerate(columns):
                    val = row[i]
                    if isinstance(val, datetime):
                        val = val.strftime("%Y-%m-%d")
                    elif hasattr(val, 'as_tuple'):
                        val = float(val)
                    txn[col] = val
                transactions.append(txn)

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

        # Check for early error
        if not transactions and summary.get("Message") and summary.get("Message") != "Success":
            return {"status": "error", "Message": summary["Message"], "transactions": [], "summary": summary, "count": 0}

        result = {
            "status": "success",
            "transactions": transactions,
            "summary": summary,
            "count": len(transactions),
            "Message": summary.get("Message", "Success"),
        }

        # Store in session for charting
        if tool_context is not None:
            tool_context.state["last_inventory_data"] = result
            tool_context.state["last_query_context"] = "inventory_consumption"
            logger.info(f"📝 Stored {len(transactions)} transactions in session")

        print(f"✅ [INVENTORY] {len(transactions)} transactions, "
              f"unique_items={summary.get('UniqueItems', 0)}, "
              f"total_qty={summary.get('TotalQuantity', 0)}")

        return result

    except Exception as e:
        print(f"❌ [INVENTORY ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "Message": f"Error: {type(e).__name__}: {str(e)}", "transactions": [], "summary": {}, "count": 0}
