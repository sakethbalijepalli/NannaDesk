"""POST /api/documents (spec §15, §8: document memory). Uploads go to a
local directory and are indexed into `personal_fts` only — never into
`government_fts` (spec §8.1).
"""
import shutil
import uuid
from pathlib import Path
from typing import Literal

import fitz  # PyMuPDF
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.clock import now_iso
from app.config import settings
from app.db.connection import get_db
from app.health.parser import parse_pdf
from app.memory.store import index_document

router = APIRouter()

DocType = Literal["LAB_REPORT", "OFFICE", "GOVERNMENT", "OTHER"]


@router.post("/documents")
async def upload_document(file: UploadFile = File(...), doc_type: DocType = Form("OTHER")) -> dict:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF upload is supported in this build")

    dest_dir = settings.reports_dir if doc_type == "LAB_REPORT" else settings.documents_dir
    stored_name = f"{uuid.uuid4().hex[:8]}-{file.filename}"
    dest_path = Path(dest_dir) / stored_name
    with dest_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    with fitz.open(dest_path) as doc:
        page_count = doc.page_count
        pages_text = [page.get_text() for page in doc]

    with get_db() as db:
        cur = db.execute(
            "INSERT INTO documents (filename, doc_type, path, page_count, uploaded_at) VALUES (?, ?, ?, ?, ?)",
            # uploaded_at set explicitly (UTC, via now_iso()) rather than
            # relying on the schema's CURRENT_TIMESTAMP default, which
            # writes naive "YYYY-MM-DD HH:MM:SS" — a different, non-sortable
            # format from every other timestamp in this database (caught
            # during manual testing: it made a same-day upload look older
            # than a report seeded weeks earlier).
            (file.filename, doc_type, str(dest_path), page_count, now_iso()),
        )
        document_id = cur.lastrowid
        index_document(db, document_id, doc_type, pages_text)

        lab_results = []
        if doc_type == "LAB_REPORT":
            lab_results = parse_pdf(str(dest_path))
            for row in lab_results:
                db.execute(
                    """INSERT INTO lab_results (document_id, test, value, unit, reference_low,
                       reference_high, flag, source_page) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (document_id, row["test"], row["value"], row["unit"], row["reference_low"],
                     row["reference_high"], row["flag"], row["source_page"]),
                )

    return {
        "id": document_id, "filename": file.filename, "doc_type": doc_type,
        "page_count": page_count, "lab_results_extracted": len(lab_results),
    }
