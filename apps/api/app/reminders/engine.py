"""Deterministic medication/meal state machine (spec §11).

SCHEDULED -> REMINDER_SENT -> TAKEN
                            -> SNOOZED -> REMINDER_SENT
                            -> NOT_CONFIRMED
Other explicit terminal states: SKIPPED, UNKNOWN.

The LLM may interpret "yes, I took it" as natural language, but only this
module writes event rows. Nothing here ever guesses a confirmation.
"""
import sqlite3
from datetime import timedelta
from typing import Literal, Optional

from app.audit import record_audit
from app.clock import now, now_iso, to_iso, today_str

MEAL_TYPES = ("breakfast", "lunch", "dinner")


def ensure_today_events(db: sqlite3.Connection, event_date: Optional[str] = None) -> None:
    """Idempotently create today's MEAL and MEDICATION event rows so the
    rest of the system always has something to query/update, even before
    any reminder has fired.
    """
    event_date = event_date or today_str()

    for meal_type in MEAL_TYPES:
        existing = db.execute(
            "SELECT id FROM events WHERE event_date = ? AND kind = 'MEAL' AND meal_type = ?",
            (event_date, meal_type),
        ).fetchone()
        if not existing:
            db.execute(
                "INSERT INTO events (event_date, kind, meal_type, status) VALUES (?, 'MEAL', ?, 'SCHEDULED')",
                (event_date, meal_type),
            )

    schedules = db.execute(
        """SELECT ms.id FROM medication_schedules ms
           JOIN medications m ON m.id = ms.medication_id
           WHERE m.active = 1"""
    ).fetchall()
    for sched in schedules:
        existing = db.execute(
            "SELECT id FROM events WHERE event_date = ? AND kind = 'MEDICATION' AND medication_schedule_id = ?",
            (event_date, sched["id"]),
        ).fetchone()
        if not existing:
            db.execute(
                """INSERT INTO events (event_date, kind, medication_schedule_id, status)
                   VALUES (?, 'MEDICATION', ?, 'SCHEDULED')""",
                (event_date, sched["id"]),
            )


def get_today_schedule(db: sqlite3.Connection, event_date: Optional[str] = None) -> list[dict]:
    event_date = event_date or today_str()
    ensure_today_events(db, event_date)

    items = []
    for row in db.execute(
        "SELECT * FROM events WHERE event_date = ? AND kind = 'MEAL' ORDER BY meal_type", (event_date,)
    ):
        items.append({
            "event_id": row["id"], "kind": "MEAL", "label": row["meal_type"].capitalize(),
            "status": row["status"], "due_time": None,
        })

    for row in db.execute(
        """SELECT e.*, m.name AS med_name, ms.time AS due_time
           FROM events e
           JOIN medication_schedules ms ON ms.id = e.medication_schedule_id
           JOIN medications m ON m.id = ms.medication_id
           WHERE e.event_date = ? AND e.kind = 'MEDICATION'
           ORDER BY ms.time""",
        (event_date,),
    ):
        items.append({
            "event_id": row["id"], "kind": "MEDICATION", "label": row["med_name"],
            "status": row["status"], "due_time": row["due_time"],
        })

    return items


def get_medication_status(db: sqlite3.Connection, event_date: Optional[str] = None,
                           medication_name: Optional[str] = None) -> list[dict]:
    event_date = event_date or today_str()
    ensure_today_events(db, event_date)

    query = """SELECT e.*, m.name AS med_name, ms.time AS due_time
               FROM events e
               JOIN medication_schedules ms ON ms.id = e.medication_schedule_id
               JOIN medications m ON m.id = ms.medication_id
               WHERE e.event_date = ? AND e.kind = 'MEDICATION'"""
    params: list = [event_date]
    if medication_name:
        query += " AND m.name LIKE ?"
        params.append(f"%{medication_name}%")
    query += " ORDER BY ms.time"

    return [dict(row) for row in db.execute(query, params)]


def record_meal(db: sqlite3.Connection, meal_type: Literal["breakfast", "lunch", "dinner"]) -> dict:
    """Record an explicit, user-stated meal confirmation. This is the only
    thing that makes a meal-dependent medicine reminder eligible to fire.
    """
    event_date = today_str()
    ensure_today_events(db, event_date)

    row = db.execute(
        "SELECT id FROM events WHERE event_date = ? AND kind = 'MEAL' AND meal_type = ?",
        (event_date, meal_type),
    ).fetchone()
    db.execute(
        "UPDATE events SET status = 'CONFIRMED', confirmed_at = ?, updated_at = ? WHERE id = ?",
        (now_iso(), now_iso(), row["id"]),
    )
    record_audit(db, "MEAL_CONFIRMED", "event", row["id"])
    return {"event_id": row["id"], "meal_type": meal_type, "status": "CONFIRMED"}


def record_medication(db: sqlite3.Connection, event_id: int,
                       outcome: Literal["TAKEN", "SKIPPED"]) -> dict:
    """Record an explicit, user-stated medication outcome. Never called by
    the LLM directly — only after the user has made a clear statement.
    """
    row = db.execute("SELECT * FROM events WHERE id = ? AND kind = 'MEDICATION'", (event_id,)).fetchone()
    if not row:
        raise ValueError("No such medication event")

    db.execute(
        "UPDATE events SET status = ?, confirmed_at = ?, updated_at = ? WHERE id = ?",
        (outcome, now_iso(), now_iso(), event_id),
    )
    record_audit(db, f"MEDICATION_{outcome}", "event", event_id)
    return {"event_id": event_id, "status": outcome}


def confirm_event(db: sqlite3.Connection, event_id: int,
                   outcome: Literal["TAKEN", "SKIPPED", "CONFIRMED"]) -> dict:
    """Generic confirmation entry point for the /api/reminders/{id}/confirm
    endpoint, which only has an event id to work with. Dispatches to the
    MEAL or MEDICATION path by the event's own kind.
    """
    row = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not row:
        raise ValueError("No such event")

    if row["kind"] == "MEAL":
        if outcome != "CONFIRMED":
            raise ValueError("Meals can only be confirmed, not marked TAKEN/SKIPPED")
        db.execute(
            "UPDATE events SET status = 'CONFIRMED', confirmed_at = ?, updated_at = ? WHERE id = ?",
            (now_iso(), now_iso(), event_id),
        )
        record_audit(db, "MEAL_CONFIRMED", "event", event_id)
        return {"event_id": event_id, "status": "CONFIRMED"}

    if outcome not in ("TAKEN", "SKIPPED"):
        raise ValueError("Medication events must be confirmed as TAKEN or SKIPPED")
    return record_medication(db, event_id, outcome)


def snooze_event(db: sqlite3.Connection, event_id: int, minutes: int = 15) -> dict:
    row = db.execute(
        """SELECT e.*, m.name AS med_name FROM events e
           LEFT JOIN medication_schedules ms ON ms.id = e.medication_schedule_id
           LEFT JOIN medications m ON m.id = ms.medication_id
           WHERE e.id = ?""",
        (event_id,),
    ).fetchone()
    if not row:
        raise ValueError("No such event")

    db.execute(
        "UPDATE events SET status = 'SNOOZED', updated_at = ? WHERE id = ?",
        (now_iso(), event_id),
    )
    due_at = now() + timedelta(minutes=minutes)
    label = f"Time for {row['med_name']}" if row["med_name"] else "Reminder"
    db.execute(
        "INSERT INTO reminders (event_id, kind, label, due_at, status) VALUES (?, 'MEDICATION', ?, ?, 'PENDING')",
        (event_id, label, to_iso(due_at)),
    )
    record_audit(db, "EVENT_SNOOZED", "event", event_id)
    return {"event_id": event_id, "status": "SNOOZED", "next_reminder_at": to_iso(due_at)}


def get_case_with_last_message(db: sqlite3.Connection, case_id: int) -> Optional[dict]:
    case = db.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    if not case:
        return None
    last_message = db.execute(
        "SELECT * FROM case_messages WHERE case_id = ? ORDER BY sent_at DESC LIMIT 1", (case_id,)
    ).fetchone()
    return {"case": dict(case), "last_message": dict(last_message) if last_message else None}


def find_awaiting_reply_cases(db: sqlite3.Connection) -> list[dict]:
    """Cases Dad has sent something about but hasn't heard back on —
    backs the "I sent this last week, did they reply?" conversation
    (spec §2.2, §14.4) with real case/message state instead of a
    substring search over the whole sentence.
    """
    rows = db.execute(
        "SELECT id FROM cases WHERE status IN ('WAITING_FOR_REPLY', 'FOLLOW_UP_DUE') ORDER BY updated_at DESC"
    ).fetchall()
    results = []
    for row in rows:
        detail = get_case_with_last_message(db, row["id"])
        if detail:
            results.append(detail)
    return results


def get_pending_cases(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        "SELECT * FROM cases WHERE status != 'RESOLVED' ORDER BY updated_at DESC"
    ).fetchall()
    return [dict(row) for row in rows]
