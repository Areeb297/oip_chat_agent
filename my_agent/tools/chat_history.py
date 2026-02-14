"""
Chat history persistence for OIP Chatbot.
Stores chat sessions and messages in SQL Server (ChatbotSessions / ChatbotMessages tables).
"""

import logging
from typing import Optional
from datetime import datetime

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
    Create a ChatbotSession row if it doesn't already exist.
    Returns True if session was created, False if it already existed.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if session already exists
        cursor.execute(
            "SELECT 1 FROM dbo.ChatbotSessions WHERE Id = ?",
            session_id,
        )
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return False

        # Insert new session
        cursor.execute(
            """INSERT INTO dbo.ChatbotSessions (Id, UserId, Title, CreatedAt, UpdatedAt, IsActive, IsDeleted)
               VALUES (?, ?, ?, SYSDATETIMEOFFSET(), SYSDATETIMEOFFSET(), 1, 0)""",
            session_id,
            user_id,
            title,
        )
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Created session {session_id} for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to ensure session {session_id}: {e}")
        return False


def save_message(session_id: str, role: str, content: str) -> Optional[int]:
    """
    Insert a message into ChatbotMessages and touch the session's UpdatedAt.
    Returns the new message Id, or None on failure.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert message
        cursor.execute(
            """INSERT INTO dbo.ChatbotMessages (SessionId, Role, Content, CreatedAt)
               OUTPUT INSERTED.Id
               VALUES (?, ?, ?, SYSDATETIMEOFFSET())""",
            session_id,
            role,
            content,
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
            """SELECT TOP (?) Id, Title, CreatedAt, UpdatedAt
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

        # Serialize datetimeoffset to ISO strings
        for row in rows:
            row["Id"] = str(row["Id"])
            for dt_field in ("CreatedAt", "UpdatedAt"):
                if row.get(dt_field):
                    row[dt_field] = row[dt_field].isoformat()

        return rows
    except Exception as e:
        logger.error(f"Failed to fetch sessions for user {user_id}: {e}")
        return []


def get_session_messages(session_id: str) -> list[dict]:
    """Return all messages for a session in chronological order."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT Id, Role, Content, CreatedAt
               FROM dbo.ChatbotMessages
               WHERE SessionId = ?
               ORDER BY Id ASC""",
            session_id,
        )
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()
        conn.close()

        for row in rows:
            if row.get("CreatedAt"):
                row["CreatedAt"] = row["CreatedAt"].isoformat()

        return rows
    except Exception as e:
        logger.error(f"Failed to fetch messages for session {session_id}: {e}")
        return []


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
