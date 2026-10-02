"""POST /api/reports/{id}/explain (spec §12, §15). Pulls already-parsed,
already-flagged lab rows and an already-computed diff against the prior
report, then hands only those facts to the LLM (or the template fallback)
for phrasing. See app/health/explanation.py for why the facts come first.
"""
from fastapi import APIRouter, HTTPException

from app.db.connection import get_db
from app.db.models import ReportExplainResponse
from app.health.explanation import explain_report
from app.health.labs import compare

router = APIRouter()


@router.post("/reports/{document_id}/explain", response_model=ReportExplainResponse)
async def explain(document_id: int) -> ReportExplainResponse:
    with get_db() as db:
        doc = db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="No such document")
        if doc["doc_type"] != "LAB_REPORT":
            raise HTTPException(status_code=400, detail="Document is not a lab report")

        results = [dict(r) for r in db.execute(
            "SELECT * FROM lab_results WHERE document_id = ?", (document_id,)
        )]
        if not results:
            raise HTTPException(status_code=422, detail="No structured values were extracted from this report")

        previous_doc = db.execute(
            """SELECT * FROM documents WHERE doc_type = 'LAB_REPORT' AND id != ?
               AND uploaded_at < ? ORDER BY uploaded_at DESC LIMIT 1""",
            (document_id, doc["uploaded_at"]),
        ).fetchone()
        diffs = None
        if previous_doc:
            previous_results = [dict(r) for r in db.execute(
                "SELECT * FROM lab_results WHERE document_id = ?", (previous_doc["id"],)
            )]
            diffs = compare(results, previous_results)

    return await explain_report(results, diffs)
