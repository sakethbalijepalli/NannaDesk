"""POST /api/government/search (spec §15.2, §13). Freshness rule lives in
app.government.search — this file is just the HTTP boundary.
"""
from fastapi import APIRouter

from app.db.models import GovernmentAnswer, GovernmentSearchRequest
from app.government.search import search_government

router = APIRouter()


@router.post("/government/search", response_model=GovernmentAnswer)
async def government_search(payload: GovernmentSearchRequest) -> GovernmentAnswer:
    return await search_government(payload.query)
