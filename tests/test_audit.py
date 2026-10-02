"""Spec §16.1: audit rows are metadata only — no report text, email
bodies, employee identifiers, or medication details.
"""
from app.audit import record_audit


def test_audit_table_has_no_free_text_columns(db):
    columns = {row["name"] for row in db.execute("PRAGMA table_info(audit_events)")}
    assert columns == {"id", "event_type", "entity_type", "entity_id", "created_at"}


def test_record_audit_cannot_carry_arbitrary_text(db):
    record_audit(db, "EMAIL_SENT", "email_draft", 42)
    row = db.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT 1").fetchone()
    assert row["event_type"] == "EMAIL_SENT"
    assert row["entity_id"] == 42
    # The row has exactly the metadata columns — there's nowhere for a
    # body, subject, or medication name to have been written.
    assert set(row.keys()) == {"id", "event_type", "entity_type", "entity_id", "created_at"}
