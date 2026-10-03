"""GET/PUT /api/profile (spec §7.1). `profile` is a singleton table — this
upserts the one row rather than modeling a collection, since NannaDesk is
"a personal assistant for one user" (spec §10.3's own system prompt).
"""
from fastapi import APIRouter

from app.audit import record_audit
from app.db.connection import get_db
from app.db.models import ProfileIn, ProfileOut

router = APIRouter()


@router.get("/profile")
async def get_profile() -> ProfileOut | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM profile LIMIT 1").fetchone()
        if not row:
            return None
        data = dict(row)
        data["family_escalation_enabled"] = bool(data["family_escalation_enabled"])
        return ProfileOut(**data)


@router.put("/profile", response_model=ProfileOut)
async def put_profile(payload: ProfileIn) -> ProfileOut:
    with get_db() as db:
        existing = db.execute("SELECT id FROM profile LIMIT 1").fetchone()
        values = (
            payload.name, payload.preferred_language, payload.department, payload.designation,
            payload.office, payload.employee_code, payload.ddo_name, payload.ddo_email,
            payload.signature, int(payload.family_escalation_enabled),
            payload.family_contact_name, payload.family_contact_email,
        )
        if existing:
            db.execute(
                """UPDATE profile SET name=?, preferred_language=?, department=?, designation=?,
                   office=?, employee_code=?, ddo_name=?, ddo_email=?, signature=?,
                   family_escalation_enabled=?, family_contact_name=?, family_contact_email=?
                   WHERE id=?""",
                values + (existing["id"],),
            )
            profile_id = existing["id"]
            record_audit(db, "PROFILE_UPDATED", "profile", profile_id)
        else:
            cur = db.execute(
                """INSERT INTO profile (name, preferred_language, department, designation, office,
                   employee_code, ddo_name, ddo_email, signature, family_escalation_enabled,
                   family_contact_name, family_contact_email)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                values,
            )
            profile_id = cur.lastrowid
            record_audit(db, "PROFILE_CREATED", "profile", profile_id)

        return ProfileOut(id=profile_id, **payload.model_dump())
