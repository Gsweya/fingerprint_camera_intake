"""
db.py — Minimal SQLite store for enrolled fingerprint templates plus a
lightweight CSV registry for names/labels.

Templates are stored as serialized minutiae payloads from the local
compatibility layer. The CSV registry is meant to be human-editable and easy
to back up or version.
"""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "templates.db"
REGISTRY_PATH = Path(__file__).parent / "registry.csv"


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


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _ensure_registry_exists() -> None:
    if not REGISTRY_PATH.exists():
        with REGISTRY_PATH.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=["person_id", "name", "notes", "created_at", "updated_at"],
            )
            writer.writeheader()


def load_registry_rows() -> list[dict[str, str]]:
    _ensure_registry_exists()
    with REGISTRY_PATH.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def load_registry_map() -> dict[str, dict[str, str]]:
    return {row["person_id"]: row for row in load_registry_rows()}


def lookup_registry(person_id: str) -> dict[str, str] | None:
    return load_registry_map().get(person_id)


def save_registry_entry(person_id: str, name: str, notes: str = "") -> None:
    _ensure_registry_exists()
    rows = load_registry_rows()
    now = now_iso()
    updated = False
    for row in rows:
        if row["person_id"] == person_id:
            row["name"] = name
            row["notes"] = notes
            row["updated_at"] = now
            updated = True
            break
    if not updated:
        rows.append({
            "person_id": person_id,
            "name": name,
            "notes": notes,
            "created_at": now,
            "updated_at": now,
        })

    with REGISTRY_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["person_id", "name", "notes", "created_at", "updated_at"],
        )
        writer.writeheader()
        writer.writerows(rows)
