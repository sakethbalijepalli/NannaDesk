"""Shared audit-trail writer. Spec §16.1: never write report text, email
bodies, employee identifiers, or medication details into logs — only
action metadata (event type + entity reference).
"""
import sqlite3

from app.clock import now_iso


def record_audit(db: sqlite3.Connection, event_type: str, entity_type: str | None = None,
                  entity_id: int | None = None) -> None:
    db.execute(
        "INSERT INTO audit_events (event_type, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?)",
        (event_type, entity_type, entity_id, now_iso()),
    )
