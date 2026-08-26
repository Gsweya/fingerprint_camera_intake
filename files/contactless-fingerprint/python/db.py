"""
db.py — Minimal SQLite store for enrolled fingerprint templates.

Templates are stored as SourceAFIS's serialized binary format (bytes).
Swap this for Postgres/whatever in a real deployment — this is just
enough to live-test enroll/match locally.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "templates.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            person_id TEXT PRIMARY KEY,
            template BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return conn


def save_template(person_id: str, template_bytes: bytes):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO templates (person_id, template) VALUES (?, ?)",
        (person_id, template_bytes),
    )
    conn.commit()
    conn.close()


def load_all_templates():
    """Returns list of (person_id, template_bytes) for 1:N matching."""
    conn = get_conn()
    rows = conn.execute("SELECT person_id, template FROM templates").fetchall()
    conn.close()
    return rows


def load_template(person_id: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT template FROM templates WHERE person_id = ?", (person_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else None
