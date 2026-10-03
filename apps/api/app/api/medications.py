"""CRUD for medications + their schedules (spec §7.2) — the setup screen's
other half, alongside profile.py. A medication is soft-deleted
(`active = 0`), never hard-deleted: existing `events`/`audit_events` rows
reference it, and the spec's own action-permissions table (§16.2) treats
changing medication data as something to record, not erase.
"""
from fastapi import APIRouter, HTTPException

from app.audit import record_audit
from app.db.connection import get_db
from app.db.models import MedicationIn, MedicationOut

router = APIRouter()

_SELECT = """
    SELECT m.id, m.name, m.instructions, m.active,
           ms.id AS schedule_id, ms.time, ms.meal_dependency, ms.repeat_minutes, ms.max_followups
    FROM medications m
    JOIN medication_schedules ms ON ms.medication_id = m.id
"""


def _row_to_out(row) -> MedicationOut:
    data = dict(row)
    data["active"] = bool(data["active"])
    return MedicationOut(**data)


@router.get("/medications")
async def list_medications(include_inactive: bool = False) -> list[MedicationOut]:
    with get_db() as db:
        query = _SELECT + ("" if include_inactive else " WHERE m.active = 1") + " ORDER BY ms.time"
        return [_row_to_out(r) for r in db.execute(query)]


@router.post("/medications", response_model=MedicationOut)
async def create_medication(payload: MedicationIn) -> MedicationOut:
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO medications (name, instructions, active) VALUES (?, ?, 1)",
            (payload.name, payload.instructions),
        )
        med_id = cur.lastrowid
        db.execute(
            """INSERT INTO medication_schedules
               (medication_id, time, meal_dependency, repeat_minutes, max_followups)
               VALUES (?, ?, ?, ?, ?)""",
            (med_id, payload.schedule.time, payload.schedule.meal_dependency,
             payload.schedule.repeat_minutes, payload.schedule.max_followups),
        )
        record_audit(db, "MEDICATION_CREATED", "medication", med_id)
        row = db.execute(_SELECT + " WHERE m.id = ?", (med_id,)).fetchone()
        return _row_to_out(row)


@router.put("/medications/{medication_id}", response_model=MedicationOut)
async def update_medication(medication_id: int, payload: MedicationIn) -> MedicationOut:
    with get_db() as db:
        existing = db.execute("SELECT id FROM medications WHERE id = ?", (medication_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="No such medication")

        db.execute(
            "UPDATE medications SET name = ?, instructions = ? WHERE id = ?",
            (payload.name, payload.instructions, medication_id),
        )
        db.execute(
            """UPDATE medication_schedules SET time = ?, meal_dependency = ?,
               repeat_minutes = ?, max_followups = ? WHERE medication_id = ?""",
            (payload.schedule.time, payload.schedule.meal_dependency,
             payload.schedule.repeat_minutes, payload.schedule.max_followups, medication_id),
        )
        record_audit(db, "MEDICATION_UPDATED", "medication", medication_id)
        row = db.execute(_SELECT + " WHERE m.id = ?", (medication_id,)).fetchone()
        return _row_to_out(row)


@router.delete("/medications/{medication_id}")
async def deactivate_medication(medication_id: int) -> dict:
    with get_db() as db:
        existing = db.execute("SELECT id FROM medications WHERE id = ?", (medication_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="No such medication")
        db.execute("UPDATE medications SET active = 0 WHERE id = ?", (medication_id,))
        record_audit(db, "MEDICATION_DEACTIVATED", "medication", medication_id)
        return {"id": medication_id, "active": False}
