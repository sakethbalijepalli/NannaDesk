"""Reminder/event endpoints (spec §15). All state changes go through
app.reminders.engine — this file only validates input and reports results.
"""
from fastapi import APIRouter, HTTPException

from app.db.connection import get_db
from app.db.models import ConfirmEventRequest, ReminderCreate, SnoozeEventRequest, TodayResponse
from app.clock import to_iso, today_str
from app.reminders import engine

router = APIRouter()


@router.get("/reminders/today", response_model=TodayResponse)
async def today() -> TodayResponse:
    with get_db() as db:
        items = engine.get_today_schedule(db)
    return TodayResponse(date=today_str(), items=items)


@router.post("/reminders")
async def create_reminder(payload: ReminderCreate) -> dict:
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO reminders (kind, label, due_at, status) VALUES (?, ?, ?, 'PENDING')",
            (payload.kind, payload.label, to_iso(payload.due_at)),
        )
        return {"id": cur.lastrowid, **payload.model_dump(mode="json")}


@router.post("/reminders/{event_id}/confirm")
async def confirm(event_id: int, payload: ConfirmEventRequest) -> dict:
    with get_db() as db:
        try:
            return engine.confirm_event(db, event_id, payload.outcome)
        except ValueError as exc:
            # "No such event" is a 404 (matches the sibling snooze endpoint
            # below for the same condition); a wrong outcome for an
            # existing event's kind is a 400 (code review caught the
            # inconsistency — both cases were mapped to 400 here).
            status = 404 if str(exc) == "No such event" else 400
            raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/reminders/{event_id}/snooze")
async def snooze(event_id: int, payload: SnoozeEventRequest) -> dict:
    with get_db() as db:
        try:
            return engine.snooze_event(db, event_id, payload.minutes)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
