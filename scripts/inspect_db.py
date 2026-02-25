"""
Developer utility: Inspect TickTraq database schema.

Dumps table names, column definitions, primary keys, and foreign keys
so you can quickly reference them when writing new stored procedures.

Usage:
    python scripts/inspect_db.py                    # List all tables
    python scripts/inspect_db.py Tickets            # Schema for one table
    python scripts/inspect_db.py Tickets Projects   # Schema for multiple tables
    python scripts/inspect_db.py --all              # Full dump of every table
    python scripts/inspect_db.py --sp               # List stored procedures
    python scripts/inspect_db.py --sp usp_Chatbot%  # Show SP parameters matching pattern
    python scripts/inspect_db.py --save             # Save full schema to docs/db-schema.txt

NOT for agent use — developer reference only.
"""

import os
import sys
import pyodbc
from pathlib import Path

# ---------------------------------------------------------------------------
# Connection (reuses same env vars as db_tools.py)
# ---------------------------------------------------------------------------

def get_connection():
    server = os.getenv("SQL_SERVER_HOST", "LAPTOP-3BGTAL2E\\SQLEXPRESS")
    database = os.getenv("SQL_SERVER_DATABASE", "TickTraq")
    driver = os.getenv("SQL_SERVER_DRIVER", "ODBC Driver 17 for SQL Server")
    trusted = os.getenv("SQL_SERVER_TRUSTED_CONNECTION", "").lower()

    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        "TrustServerCertificate=yes;"
    )
    if trusted in ("yes", "true", "1"):
        conn_str += "Trusted_Connection=yes;"
    else:
        user = os.getenv("SQL_SERVER_USER", "")
        pwd = os.getenv("SQL_SERVER_PASSWORD", "")
        conn_str += f"UID={user};PWD={pwd};"

    return pyodbc.connect(conn_str)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

SQL_LIST_TABLES = """
SELECT TABLE_SCHEMA, TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_SCHEMA, TABLE_NAME
"""

SQL_TABLE_COLUMNS = """
SELECT
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.CHARACTER_MAXIMUM_LENGTH,
    c.NUMERIC_PRECISION,
    c.IS_NULLABLE,
    c.COLUMN_DEFAULT,
    CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 'PK' ELSE '' END AS IS_PK
FROM INFORMATION_SCHEMA.COLUMNS c
LEFT JOIN (
    SELECT ku.TABLE_SCHEMA, ku.TABLE_NAME, ku.COLUMN_NAME
    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
    JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
        ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
    WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
) pk ON pk.TABLE_SCHEMA = c.TABLE_SCHEMA
    AND pk.TABLE_NAME = c.TABLE_NAME
    AND pk.COLUMN_NAME = c.COLUMN_NAME
WHERE c.TABLE_SCHEMA = ? AND c.TABLE_NAME = ?
ORDER BY c.ORDINAL_POSITION
"""

SQL_FOREIGN_KEYS = """
SELECT
    fk.name AS FK_Name,
    COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS Column_Name,
    OBJECT_SCHEMA_NAME(fkc.referenced_object_id) + '.' +
    OBJECT_NAME(fkc.referenced_object_id) AS References_Table,
    COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS References_Column
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
WHERE fk.parent_object_id = OBJECT_ID(?)
ORDER BY fk.name
"""

SQL_LIST_STORED_PROCS = """
SELECT ROUTINE_SCHEMA, ROUTINE_NAME, CREATED, LAST_ALTERED
FROM INFORMATION_SCHEMA.ROUTINES
WHERE ROUTINE_TYPE = 'PROCEDURE'
  AND ROUTINE_NAME LIKE ?
ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME
"""

SQL_SP_PARAMETERS = """
SELECT
    PARAMETER_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    PARAMETER_MODE
FROM INFORMATION_SCHEMA.PARAMETERS
WHERE SPECIFIC_SCHEMA = ? AND SPECIFIC_NAME = ?
ORDER BY ORDINAL_POSITION
"""

SQL_ROW_COUNTS = """
SELECT
    s.name AS SchemaName,
    t.name AS TableName,
    p.rows AS TotalRows
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0, 1)
ORDER BY p.rows DESC
"""


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def fmt_type(row):
    """Format column type string like 'NVARCHAR(100)' or 'INT'."""
    dtype = row.DATA_TYPE.upper()
    if row.CHARACTER_MAXIMUM_LENGTH:
        length = row.CHARACTER_MAXIMUM_LENGTH
        if length == -1:
            return f"{dtype}(MAX)"
        return f"{dtype}({length})"
    if row.NUMERIC_PRECISION and dtype not in ("INT", "BIGINT", "SMALLINT", "TINYINT", "BIT"):
        return f"{dtype}({row.NUMERIC_PRECISION})"
    return dtype


def print_table_schema(cursor, schema, table):
    """Print formatted schema for one table."""
    header = f"{schema}.{table}"
    print(f"\n{'='*60}")
    print(f"  {header}")
    print(f"{'='*60}")

    # Columns
    cursor.execute(SQL_TABLE_COLUMNS, schema, table)
    rows = cursor.fetchall()
    if not rows:
        print("  (no columns found)")
        return

    print(f"  {'Column':<30} {'Type':<20} {'Null':<6} {'PK':<4} {'Default'}")
    print(f"  {'-'*30} {'-'*20} {'-'*6} {'-'*4} {'-'*20}")
    for r in rows:
        null = "YES" if r.IS_NULLABLE == "YES" else "NO"
        default = str(r.COLUMN_DEFAULT or "").strip("()")[:20]
        print(f"  {r.COLUMN_NAME:<30} {fmt_type(r):<20} {null:<6} {r.IS_PK:<4} {default}")

    # Foreign keys
    full_name = f"{schema}.{table}"
    cursor.execute(SQL_FOREIGN_KEYS, full_name)
    fks = cursor.fetchall()
    if fks:
        print(f"\n  Foreign Keys:")
        for fk in fks:
            print(f"    {fk.Column_Name} -> {fk.References_Table}({fk.References_Column})  [{fk.FK_Name}]")


def print_sp_list(cursor, pattern):
    """List stored procedures matching pattern."""
    cursor.execute(SQL_LIST_STORED_PROCS, pattern)
    rows = cursor.fetchall()
    if not rows:
        print(f"No stored procedures matching '{pattern}'")
        return

    print(f"\n{'='*60}")
    print(f"  Stored Procedures ({len(rows)} found)")
    print(f"{'='*60}")
    for r in rows:
        altered = r.LAST_ALTERED.strftime("%Y-%m-%d") if r.LAST_ALTERED else "?"
        print(f"  {r.ROUTINE_SCHEMA}.{r.ROUTINE_NAME:<45} (modified: {altered})")

        # Show parameters
        cursor.execute(SQL_SP_PARAMETERS, r.ROUTINE_SCHEMA, r.ROUTINE_NAME)
        params = cursor.fetchall()
        if params:
            for p in params:
                ptype = p.DATA_TYPE.upper()
                if p.CHARACTER_MAXIMUM_LENGTH:
                    ptype += f"({p.CHARACTER_MAXIMUM_LENGTH})" if p.CHARACTER_MAXIMUM_LENGTH != -1 else "(MAX)"
                print(f"      {p.PARAMETER_NAME:<25} {ptype:<20} {p.PARAMETER_MODE}")
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    from dotenv import load_dotenv
    load_dotenv()

    conn = get_connection()
    cursor = conn.cursor()
    print(f"Connected to: {os.getenv('SQL_SERVER_DATABASE', 'TickTraq')}")

    args = sys.argv[1:]

    # --sp flag: list/inspect stored procedures
    if "--sp" in args:
        args.remove("--sp")
        pattern = args[0] if args else "usp_Chatbot%"
        print_sp_list(cursor, pattern)
        conn.close()
        return

    # Get all tables
    cursor.execute(SQL_LIST_TABLES)
    all_tables = [(r.TABLE_SCHEMA, r.TABLE_NAME) for r in cursor.fetchall()]

    # --save: dump everything to file
    save_mode = "--save" in args
    if save_mode:
        args.remove("--save")
        out_path = Path(__file__).parent.parent / "docs" / "db-schema.txt"
        old_stdout = sys.stdout
        sys.stdout = open(out_path, "w", encoding="utf-8")
        print(f"# TickTraq Database Schema (auto-generated)")
        print(f"# Tables: {len(all_tables)}\n")

    # --all: show every table
    if "--all" in args or save_mode:
        if "--all" in args:
            args.remove("--all")
        # Row counts first
        cursor.execute(SQL_ROW_COUNTS)
        counts = cursor.fetchall()
        print(f"\nTable Row Counts:")
        print(f"  {'Table':<45} {'Rows':>10}")
        print(f"  {'-'*45} {'-'*10}")
        for c in counts:
            print(f"  {c.SchemaName}.{c.TableName:<43} {c.RowCount:>10,}")
        # Then schemas
        for schema, table in all_tables:
            print_table_schema(cursor, schema, table)
    elif args:
        # Specific table names provided
        for name in args:
            matches = [(s, t) for s, t in all_tables if t.lower() == name.lower()]
            if matches:
                for s, t in matches:
                    print_table_schema(cursor, s, t)
            else:
                # Try fuzzy match
                fuzzy = [(s, t) for s, t in all_tables if name.lower() in t.lower()]
                if fuzzy:
                    print(f"\nNo exact match for '{name}', showing partial matches:")
                    for s, t in fuzzy:
                        print_table_schema(cursor, s, t)
                else:
                    print(f"\nTable '{name}' not found.")
    else:
        # No args: just list tables with row counts
        cursor.execute(SQL_ROW_COUNTS)
        counts = {f"{r.SchemaName}.{r.TableName}": r.TotalRows for r in cursor.fetchall()}
        print(f"\n{len(all_tables)} tables found:\n")
        print(f"  {'Table':<45} {'Rows':>10}")
        print(f"  {'-'*45} {'-'*10}")
        for schema, table in all_tables:
            key = f"{schema}.{table}"
            cnt = counts.get(key, 0)
            print(f"  {key:<45} {cnt:>10,}")
        print(f"\nUse: python scripts/inspect_db.py <TableName> for details")
        print(f"     python scripts/inspect_db.py --sp              for stored procedures")
        print(f"     python scripts/inspect_db.py --all             for full dump")
        print(f"     python scripts/inspect_db.py --save            for save to docs/db-schema.txt")

    if save_mode:
        sys.stdout.close()
        sys.stdout = old_stdout
        print(f"Schema saved to: {out_path}")

    conn.close()


if __name__ == "__main__":
    main()
