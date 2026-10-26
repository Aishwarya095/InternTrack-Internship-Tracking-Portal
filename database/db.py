"""
INTERNTRACK — Database Connection & Query Management
Provides thread-safe connections, WAL mode initialization, and query execution.
"""

import os
import sqlite3
from config import DB_FILE, SCHEMA_FILE

def get_connection():
    """Returns a SQLite connection with row_factory=sqlite3.Row and foreign keys enabled."""
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db():
    """Initializes the database using schema.sql."""
    conn = get_connection()
    cursor = conn.cursor()
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    cursor.executescript(schema_sql)
    conn.commit()
    conn.close()

def query_all(sql, params=()):
    """Executes a SELECT query and returns all rows as a list of dicts."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def query_one(sql, params=()):
    """Executes a SELECT query and returns a single row as a dict, or None."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def execute(sql, params=()):
    """Executes an INSERT/UPDATE/DELETE query and commits."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()
