"""
Chat history persistence for OIP Chatbot.
Stores chat sessions and messages in SQL Server (ChatbotSessions / ChatbotMessages tables).
"""

import logging
from typing import Optional

from .db_tools import get_db_connection

logger = logging.getLogger("oip_assistant.chat_history")


def get_user_id_by_username(username: str) -> Optional[int]:
    """Look up the Users.Id from a username string."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT Id FROM dbo.Users WHERE Username = ?", username)
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"Failed to look up user ID for '{username}': {e}")
        return None


def ensure_session(session_id: str, user_id: int, title: Optional[str] = None) -> bool:
    """
    Create a ChatbotSession row if it doesn't already exist (atomic).
    Returns True if session was created, False if it already existed.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Atomic insert — avoids race condition between check and insert
        cursor.execute(
            """INSERT INTO dbo.ChatbotSessions (Id, UserId, Title, CreatedAt, UpdatedAt, IsActive, IsDeleted)
               SELECT ?, ?, ?, SYSDATETIMEOFFSET(), SYSDATETIMEOFFSET(), 1, 0
               WHERE NOT EXISTS (SELECT 1 FROM dbo.ChatbotSessions WHERE Id = ?)""",
            session_id,
            user_id,
            title,
            session_id,
        )
        created = cursor.rowcount > 0
        conn.commit()
        cursor.close()
        conn.close()
        if created:
            logger.info(f"Created session {session_id} for user {user_id}")
        return created
    except Exception as e:
        logger.error(f"Failed to ensure session {session_id}: {e}")
        return False


def save_message(
    session_id: str,
    role: str,
    content: str,
    report_html: Optional[str] = None,
    report_model_json: Optional[str] = None,
) -> Optional[int]:
    """
    Insert a message into ChatbotMessages and touch the session's UpdatedAt.

    Args:
        session_id: Chat session UUID.
        role: "user" or "assistant".
        content: The chat message text/HTML (no report data embedded).
        report_html: Rendered report HTML (stored in dedicated ReportHtml column).
        report_model_json: JSON-serialized report model (stored in ReportModelJson column).

    Returns the new message Id, or None on failure.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert message with optional report columns
        cursor.execute(
            """INSERT INTO dbo.ChatbotMessages
               (SessionId, Role, Content, ReportHtml, ReportModelJson, CreatedAt)
               OUTPUT INSERTED.Id
               VALUES (?, ?, ?, ?, ?, SYSDATETIMEOFFSET())""",
            session_id,
            role,
            content,
            report_html,
            report_model_json,
        )
        row = cursor.fetchone()
        msg_id = row[0] if row else None

        # Update session timestamp
        cursor.execute(
            "UPDATE dbo.ChatbotSessions SET UpdatedAt = SYSDATETIMEOFFSET() WHERE Id = ?",
            session_id,
        )

        conn.commit()
        cursor.close()
        conn.close()
        return msg_id
    except Exception as e:
        logger.error(f"Failed to save message in session {session_id}: {e}")
        return None


def update_session_title(session_id: str, title: str) -> bool:
    """Update session title (e.g. auto-generated from first user message)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE dbo.ChatbotSessions SET Title = ? WHERE Id = ?",
            title,
            session_id,
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to update session title: {e}")
        return False


def get_sessions(user_id: int, limit: int = 50) -> list[dict]:
    """
    Return the user's chat sessions ordered by most recent first.
    Only returns non-deleted sessions.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT TOP (?) CAST(Id AS NVARCHAR(36)) AS Id, Title,
                      CONVERT(VARCHAR(30), CreatedAt, 127) AS CreatedAt,
                      CONVERT(VARCHAR(30), UpdatedAt, 127) AS UpdatedAt
               FROM dbo.ChatbotSessions
               WHERE UserId = ? AND IsDeleted = 0
               ORDER BY UpdatedAt DESC""",
            limit,
            user_id,
        )
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()
        conn.close()

        return rows
    except Exception as e:
        logger.error(f"Failed to fetch sessions for user {user_id}: {e}")
        return []


def get_session_messages(session_id: str) -> list[dict]:
    """Return all messages for a session in chronological order.

    Each dict includes Id, Role, Content, CreatedAt, and optionally
    ReportHtml / ReportModelJson (NULL when no report is attached).
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT Id, Role, Content, ReportHtml, ReportModelJson,
                      CONVERT(VARCHAR(30), CreatedAt, 127) AS CreatedAt
               FROM dbo.ChatbotMessages
               WHERE SessionId = ?
               ORDER BY Id ASC""",
            session_id,
        )
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()
        conn.close()

        return rows
    except Exception as e:
        logger.error(f"Failed to fetch messages for session {session_id}: {e}")
        return []


def delete_messages_from(session_id: str, message_id: int) -> int:
    """Delete a message and all messages after it in a session.

    Returns the number of rows deleted, or -1 on failure.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM dbo.ChatbotMessages WHERE SessionId = ? AND Id >= ?",
            session_id,
            message_id,
        )
        deleted = cursor.rowcount

        # Touch session timestamp
        cursor.execute(
            "UPDATE dbo.ChatbotSessions SET UpdatedAt = SYSDATETIMEOFFSET() WHERE Id = ?",
            session_id,
        )

        conn.commit()
        cursor.close()
        conn.close()
        logger.info(
            "Deleted %d messages from session %s (from messageId %d)",
            deleted, session_id, message_id,
        )
        return deleted
    except Exception as e:
        logger.error(f"Failed to delete messages from session {session_id}: {e}")
        return -1


def get_report_model_from_db(session_id: str) -> tuple:
    """Load the most recent report_model and HTML from the database for a session.

    Returns (report_model_dict, report_html_str) or (None, None) if not found.
    Used as fallback when in-memory ADK session has been lost (server restart).
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT TOP 1 ReportHtml, ReportModelJson
               FROM dbo.ChatbotMessages
               WHERE SessionId = ? AND ReportModelJson IS NOT NULL
               ORDER BY Id DESC""",
            session_id,
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row and row[1]:
            import json
            model = json.loads(row[1])
            html = row[0] or ""
            logger.info(f"Restored report_model from DB for session {session_id}")
            return model, html
        return None, None
    except Exception as e:
        logger.error(f"Failed to load report_model from DB for session {session_id}: {e}")
        return None, None


def update_report_in_message(session_id: str, report_html: str, report_model_json: str) -> bool:
    """Update the most recent report message in a session with new HTML + model.

    Used by inline report editing (POST /report/edit) — silently updates the
    existing report message instead of creating a new chat message.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE dbo.ChatbotMessages
               SET ReportHtml = ?, ReportModelJson = ?
               WHERE Id = (
                   SELECT MAX(Id) FROM dbo.ChatbotMessages
                   WHERE SessionId = ? AND ReportHtml IS NOT NULL
               )""",
            report_html,
            report_model_json,
            session_id,
        )
        affected = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        if affected > 0:
            logger.info(f"Updated report in session {session_id} (HTML={len(report_html)} chars)")
        return affected > 0
    except Exception as e:
        logger.error(f"Failed to update report in session {session_id}: {e}")
        return False


def delete_session(session_id: str) -> bool:
    """Soft-delete a session (set IsDeleted=1)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE dbo.ChatbotSessions SET IsDeleted = 1 WHERE Id = ?",
            session_id,
        )
        affected = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        return affected > 0
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")
        return False
