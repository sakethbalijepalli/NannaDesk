"""Spec §11, §19.1: the medication/meal state machine never guesses a
confirmation, and only moves on an explicit, user-stated outcome.
"""
import pytest

from app.reminders import engine


def test_no_confirmation_means_scheduled_not_taken(db, seeded_medication):
    rows = engine.get_medication_status(db)
    assert len(rows) == 1
    assert rows[0]["status"] == "SCHEDULED"
    assert rows[0]["confirmed_at"] is None


def test_record_medication_requires_an_existing_event(db):
    with pytest.raises(ValueError):
        engine.record_medication(db, event_id=999, outcome="TAKEN")


def test_record_medication_sets_explicit_outcome(db, seeded_medication):
    today = engine.get_medication_status(db)
    event_id = today[0]["id"]

    result = engine.record_medication(db, event_id, "TAKEN")
    assert result["status"] == "TAKEN"

    rows = engine.get_medication_status(db)
    assert rows[0]["status"] == "TAKEN"
    assert rows[0]["confirmed_at"] is not None


def test_record_meal_is_idempotent_on_the_event_row(db):
    engine.record_meal(db, "breakfast")
    today = engine.get_today_schedule(db)
    breakfast = next(i for i in today if i["label"] == "Breakfast")
    assert breakfast["status"] == "CONFIRMED"


def test_snooze_creates_a_future_reminder(db, seeded_medication):
    today = engine.get_medication_status(db)
    event_id = today[0]["id"]

    result = engine.snooze_event(db, event_id, minutes=15)
    assert result["status"] == "SNOOZED"

    pending = db.execute("SELECT * FROM reminders WHERE event_id = ?", (event_id,)).fetchall()
    assert len(pending) == 1
    assert pending[0]["status"] == "PENDING"


def test_confirm_event_rejects_taken_skipped_for_meals(db):
    engine.ensure_today_events(db)
    meal_row = db.execute("SELECT id FROM events WHERE kind = 'MEAL' LIMIT 1").fetchone()
    with pytest.raises(ValueError):
        engine.confirm_event(db, meal_row["id"], "TAKEN")
