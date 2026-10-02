"""Spec §11.3, §11.4, §14.4 — the deterministic reminder/follow-up tick.
Nothing here touches the LLM; `process_reminders` only ever reads the
clock and the database.
"""
from datetime import datetime, timedelta, timezone

from app import clock as clock_module
from app.db.connection import get_db
from app.reminders import engine
from app.reminders.scheduler import process_reminders


def _set_clock(monkeypatch, dt):
    monkeypatch.setattr(clock_module, "now_provider", lambda: dt)


def _seed_meal_gated_medication(db_path):
    with get_db(db_path) as db:
        cur = db.execute("INSERT INTO medications (name, instructions, active) VALUES ('Metformin', '', 1)")
        med_id = cur.lastrowid
        cur = db.execute(
            """INSERT INTO medication_schedules
               (medication_id, time, meal_dependency, repeat_minutes, max_followups)
               VALUES (?, '08:30', 'breakfast', 10, 1)""",
            (med_id,),
        )
        schedule_id = cur.lastrowid
    return schedule_id


def test_meal_gated_medication_does_not_fire_before_meal_confirmed(db_path, monkeypatch):
    _seed_meal_gated_medication(db_path)
    _set_clock(monkeypatch, datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc))

    process_reminders()

    with get_db(db_path) as db:
        row = db.execute("SELECT status FROM events WHERE kind = 'MEDICATION'").fetchone()
    # Not SCHEDULED any more (the 08:00 meal check-in fired), but the
    # medicine itself must still be untouched: no REMINDER_SENT without
    # breakfast confirmed.
    assert row["status"] == "SCHEDULED"


def test_meal_gated_medication_fires_after_meal_confirmed(db_path, monkeypatch):
    _seed_meal_gated_medication(db_path)
    _set_clock(monkeypatch, datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc))

    with get_db(db_path) as db:
        engine.ensure_today_events(db)
        engine.record_meal(db, "breakfast")

    process_reminders()

    with get_db(db_path) as db:
        row = db.execute("SELECT status FROM events WHERE kind = 'MEDICATION'").fetchone()
    assert row["status"] == "REMINDER_SENT"


def test_snooze_is_honored_and_not_refired_immediately(db_path, monkeypatch):
    schedule_id = _seed_meal_gated_medication(db_path)
    _set_clock(monkeypatch, datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc))

    with get_db(db_path) as db:
        engine.ensure_today_events(db)
        engine.record_meal(db, "breakfast")

    process_reminders()  # fires the initial reminder

    with get_db(db_path) as db:
        event = db.execute(
            "SELECT id FROM events WHERE kind = 'MEDICATION' AND medication_schedule_id = ?", (schedule_id,)
        ).fetchone()
        engine.snooze_event(db, event["id"], minutes=15)

    # One minute later: must NOT have re-fired yet.
    _set_clock(monkeypatch, datetime(2026, 10, 2, 9, 1, tzinfo=timezone.utc))
    process_reminders()
    with get_db(db_path) as db:
        row = db.execute("SELECT status FROM events WHERE kind = 'MEDICATION'").fetchone()
    assert row["status"] == "SNOOZED"

    # After the snooze window: must fire via the reminders-table row.
    _set_clock(monkeypatch, datetime(2026, 10, 2, 9, 16, tzinfo=timezone.utc))
    process_reminders()
    with get_db(db_path) as db:
        row = db.execute("SELECT status FROM events WHERE kind = 'MEDICATION'").fetchone()
    assert row["status"] == "REMINDER_SENT"


def test_unconfirmed_medication_becomes_not_confirmed_after_max_followups(db_path, monkeypatch):
    _seed_meal_gated_medication(db_path)
    start = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)
    _set_clock(monkeypatch, start)

    with get_db(db_path) as db:
        engine.ensure_today_events(db)
        engine.record_meal(db, "breakfast")

    process_reminders()  # REMINDER_SENT, followup_count=0

    # repeat_minutes=10, max_followups=1: one followup, then NOT_CONFIRMED.
    _set_clock(monkeypatch, start + timedelta(minutes=11))
    process_reminders()
    with get_db(db_path) as db:
        row = db.execute("SELECT status, followup_count FROM events WHERE kind = 'MEDICATION'").fetchone()
    assert row["status"] == "REMINDER_SENT"
    assert row["followup_count"] == 1

    _set_clock(monkeypatch, start + timedelta(minutes=22))
    process_reminders()
    with get_db(db_path) as db:
        row = db.execute("SELECT status FROM events WHERE kind = 'MEDICATION'").fetchone()
    assert row["status"] == "NOT_CONFIRMED"


def test_overdue_case_becomes_follow_up_due(db_path, monkeypatch):
    with get_db(db_path) as db:
        db.execute(
            """INSERT INTO cases (type, title, status, follow_up_due_at)
               VALUES ('PF', 'Pending PF payment', 'WAITING_FOR_REPLY', ?)""",
            (datetime(2026, 10, 1, tzinfo=timezone.utc).isoformat(),),
        )

    _set_clock(monkeypatch, datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc))
    summary = process_reminders()

    assert summary["cases_overdue"] == 1
    with get_db(db_path) as db:
        row = db.execute("SELECT status FROM cases").fetchone()
    assert row["status"] == "FOLLOW_UP_DUE"
