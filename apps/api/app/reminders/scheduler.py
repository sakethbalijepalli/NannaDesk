"""The reminder/follow-up scheduler (spec §11.4, §14.4, §18.1).

`process_reminders` is the deterministic tick: it never calls the LLM. It
decides what's due using only the clock, `medication_schedules`, `events`
and `cases` — the model never invents timing or confirmation state.

Uses APScheduler 3.x (`BackgroundScheduler`); the 4.x line has a different
API and is not what's pinned in requirements.txt.
"""
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.audit import record_audit
from app.clock import now, now_iso, today_str
from app.config import settings
from app.db.connection import get_db
from app.reminders.engine import ensure_today_events
from app.reminders.notifications import notify

logger = logging.getLogger("nannadesk.scheduler")

_scheduler: BackgroundScheduler | None = None

# Default meal check-in times (spec §3.1, §20.3 step 7: "Reminder -> Have
# you had breakfast?"). Not yet per-profile configurable — a real gap, but
# without *some* meal prompt, a meal-gated medicine (e.g. Metformin after
# breakfast) never becomes eligible unless Dad happens to tap "Had it"
# unprompted, which defeats the point of the gating.
MEAL_CHECKIN_TIMES = {"breakfast": "08:00", "lunch": "13:00", "dinner": "20:00"}


def _parse_time(hhmm: str) -> tuple[int, int]:
    h, m = hhmm.split(":")
    return int(h), int(m)


def process_reminders() -> dict:
    """One deterministic tick. Returns a summary dict (useful for tests and
    for a future admin/debug endpoint).
    """
    summary = {"reminders_sent": 0, "followups_sent": 0, "not_confirmed": 0, "cases_overdue": 0}
    event_date = today_str()
    current = now()
    # Every DB write/comparison below uses this UTC string, not
    # `current.isoformat()` (local offset) — mixed offsets don't sort
    # correctly as SQLite TEXT (see clock.now_iso()'s docstring).
    current_iso = now_iso()

    with get_db() as db:
        ensure_today_events(db, event_date)

        meal_rows = db.execute(
            "SELECT id, meal_type, status FROM events WHERE event_date = ? AND kind = 'MEAL'",
            (event_date,),
        ).fetchall()
        meal_status = {row["meal_type"]: row["status"] for row in meal_rows}

        for row in meal_rows:
            if row["status"] != "SCHEDULED":
                continue
            checkin_h, checkin_m = _parse_time(MEAL_CHECKIN_TIMES[row["meal_type"]])
            checkin_at = current.replace(hour=checkin_h, minute=checkin_m, second=0, microsecond=0)
            if current >= checkin_at:
                db.execute(
                    "UPDATE events SET status = 'REMINDER_SENT', updated_at = ? WHERE id = ?",
                    (current_iso, row["id"]),
                )
                notify("NannaDesk", f"Have you had {row['meal_type']}?")
                record_audit(db, "MEAL_CHECKIN_SENT", "event", row["id"])
                meal_status[row["meal_type"]] = "REMINDER_SENT"
                summary["reminders_sent"] += 1

        med_events = db.execute(
            """SELECT e.*, m.name AS med_name, ms.time AS due_time, ms.meal_dependency,
                      ms.repeat_minutes, ms.max_followups
               FROM events e
               JOIN medication_schedules ms ON ms.id = e.medication_schedule_id
               JOIN medications m ON m.id = ms.medication_id
               WHERE e.event_date = ? AND e.kind = 'MEDICATION'
                 AND e.status IN ('SCHEDULED', 'REMINDER_SENT', 'SNOOZED')""",
            (event_date,),
        ).fetchall()

        for row in med_events:
            due_h, due_m = _parse_time(row["due_time"])
            due_at = current.replace(hour=due_h, minute=due_m, second=0, microsecond=0)
            meal_dep = row["meal_dependency"]
            meal_ready = (meal_dep is None) or (meal_status.get(meal_dep) == "CONFIRMED")

            # SNOOZED is deliberately excluded here: a snoozed event only
            # wakes back up via its row in the `reminders` table (below),
            # whose due_at is the snooze time, not the original schedule
            # time. Including SNOOZED here re-fired the reminder on the
            # very next tick instead of honoring the snooze (caught during
            # manual testing).
            if row["status"] == "SCHEDULED" and current >= due_at and meal_ready:
                db.execute(
                    "UPDATE events SET status = 'REMINDER_SENT', updated_at = ? WHERE id = ?",
                    (current_iso, row["id"]),
                )
                notify("NannaDesk reminder", f"Time for {row['med_name']}")
                record_audit(db, "REMINDER_SENT", "event", row["id"])
                summary["reminders_sent"] += 1
                continue

            if row["status"] == "REMINDER_SENT":
                last_update = datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else due_at
                elapsed = (current - last_update).total_seconds() / 60
                if elapsed < row["repeat_minutes"]:
                    continue
                if row["followup_count"] >= row["max_followups"]:
                    db.execute(
                        "UPDATE events SET status = 'NOT_CONFIRMED', updated_at = ? WHERE id = ?",
                        (current_iso, row["id"]),
                    )
                    record_audit(db, "MEDICATION_NOT_CONFIRMED", "event", row["id"])
                    summary["not_confirmed"] += 1
                    _maybe_escalate_to_family(db, row["med_name"])
                else:
                    db.execute(
                        "UPDATE events SET followup_count = followup_count + 1, updated_at = ? WHERE id = ?",
                        (current_iso, row["id"]),
                    )
                    notify("NannaDesk reminder", f"Still waiting to confirm {row['med_name']}")
                    record_audit(db, "REMINDER_FOLLOWUP_SENT", "event", row["id"])
                    summary["followups_sent"] += 1

        # Standalone reminders table (snoozes, custom reminders)
        due_reminders = db.execute(
            "SELECT * FROM reminders WHERE status = 'PENDING' AND due_at <= ?",
            (current_iso,),
        ).fetchall()
        for reminder in due_reminders:
            notify("NannaDesk reminder", reminder["label"] or "Reminder")
            db.execute("UPDATE reminders SET status = 'SENT' WHERE id = ?", (reminder["id"],))
            if reminder["event_id"]:
                db.execute(
                    "UPDATE events SET status = 'REMINDER_SENT', updated_at = ? WHERE id = ?",
                    (current_iso, reminder["event_id"]),
                )
            record_audit(db, "REMINDER_SENT", "reminder", reminder["id"])

        # Case follow-up detection (spec §14.4)
        overdue_cases = db.execute(
            """SELECT * FROM cases WHERE status = 'WAITING_FOR_REPLY'
               AND follow_up_due_at IS NOT NULL AND follow_up_due_at <= ?""",
            (current_iso,),
        ).fetchall()
        for case in overdue_cases:
            db.execute(
                "UPDATE cases SET status = 'FOLLOW_UP_DUE', updated_at = ? WHERE id = ?",
                (current_iso, case["id"]),
            )
            notify("NannaDesk", f"Follow-up due: {case['title']}")
            record_audit(db, "FOLLOW_UP_DUE", "case", case["id"])
            summary["cases_overdue"] += 1

    return summary


def _maybe_escalate_to_family(db, med_name: str) -> None:
    row = db.execute("SELECT family_escalation_enabled, family_contact_name FROM profile LIMIT 1").fetchone()
    if row and row["family_escalation_enabled"]:
        notify(
            "NannaDesk — family notice",
            f"{med_name} has not been confirmed after repeated reminders.",
        )
        record_audit(db, "FAMILY_ESCALATION_SENT", "medication", None)


def start_scheduler(interval_seconds: int = 60) -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(process_reminders, "interval", seconds=interval_seconds, id="process_reminders")
    _scheduler.start()
    logger.info("Reminder scheduler started (interval=%ss)", interval_seconds)
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
