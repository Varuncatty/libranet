"""Shared helpers: MySQL connection (Python DB-API), SQL-file runner, query loader.

Connection settings come from environment variables (defaults in brackets):
  MYSQL_HOST [127.0.0.1]  MYSQL_PORT [3306]  MYSQL_USER [root]
  MYSQL_PASSWORD []       MYSQL_DATABASE [libranet]
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
OUTPUT_DIR = ROOT / "output"
DB_NAME = os.getenv("MYSQL_DATABASE", "libranet")


def check_name(name):
    """Database names are interpolated into DDL, so allow only safe characters."""
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError(f"Unsafe database name: {name!r}")
    return name


def connect(database=DB_NAME):
    """Open a DB-API connection. database=None connects to the server only."""
    import mysql.connector  # imported lazily so the SQL splitter can be tested without it

    config = {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "connection_timeout": 10,
    }
    if database:
        config["database"] = check_name(database)
    return mysql.connector.connect(**config)


def connect_or_exit(database=DB_NAME):
    """Like connect(), but ends the program with a helpful message on failure."""
    import mysql.connector

    try:
        return connect(database)
    except mysql.connector.Error as exc:
        sys.exit(
            f"Cannot connect to MySQL ({exc}).\n"
            "Check that the server is running and set MYSQL_HOST / MYSQL_PORT / MYSQL_USER / "
            "MYSQL_PASSWORD if needed. If the database does not exist yet, run: "
            "python python/setup_db.py"
        )


def split_sql(text):
    """Split a SQL script into statements.

    Understands the mysql client's 'DELIMITER' command, so trigger bodies that contain
    semicolons can be sent one statement at a time. Whole-line '--' comments are dropped.
    """
    delimiter, buffer, statements = ";", [], []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        if stripped.upper().startswith("DELIMITER "):
            delimiter = stripped.split(None, 1)[1].strip()
            continue
        buffer.append(line)
        if stripped.endswith(delimiter):
            statement = "\n".join(buffer).strip()
            statements.append(statement[: -len(delimiter)].strip())
            buffer = []
    tail = "\n".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements


def run_sql_text(conn, text):
    """Execute every statement of a script on one connection, then commit."""
    cur = conn.cursor(buffered=True)
    for statement in split_sql(text):
        cur.execute(statement)
        if cur.with_rows:
            cur.fetchall()
    conn.commit()
    cur.close()


def run_sql_file(conn, path):
    run_sql_text(conn, Path(path).read_text(encoding="utf-8"))


def load_queries(path=SQL_DIR / "04_queries.sql"):
    """Parse '-- name: xyz' blocks from the SQL file into {name: sql}."""
    text = Path(path).read_text(encoding="utf-8")
    queries = {}
    for block in re.split(r"^-- name:\s*", text, flags=re.M)[1:]:
        name, _, body = block.partition("\n")
        queries[name.strip()] = body.strip().rstrip(";")
    return queries
