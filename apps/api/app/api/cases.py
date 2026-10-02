"""GET /api/cases (spec §15, §18.2)."""
from fastapi import APIRouter

from app.db.connection import get_db
from app.db.models import CaseOut

router = APIRouter()


@router.get("/cases", response_model=list[CaseOut])
async def list_cases() -> list[CaseOut]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM cases ORDER BY updated_at DESC").fetchall()
        return [CaseOut(**dict(r)) for r in rows]
