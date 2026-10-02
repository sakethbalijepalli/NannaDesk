"""Email endpoints (spec §14.2, §15). The safe-send pipeline:

    draft created (DRAFT) -> UI shows recipient/subject/body -> user
    presses Send with confirm=true -> provider.send() -> SENT event

`/emails/{draft_id}/send` is the ONLY path that can move a draft to SENT,
and it refuses without `confirm: true` (spec: "NO SILENT SENDING").
"""
from datetime import timedelta

from fastapi import APIRouter, HTTPException

from app.audit import record_audit
from app.clock import now, now_iso, to_iso
from app.config import settings
from app.db.connection import get_db
from app.db.models import EmailDraftRequest, EmailDraftResponse, EmailSendRequest
from app.email.factory import get_email_provider

router = APIRouter()


@router.get("/emails/search")
async def search_emails(query: str) -> list[dict]:
    provider = get_email_provider()
    return list(await provider.search(query))


@router.get("/emails/{draft_id}", response_model=EmailDraftResponse)
async def get_email(draft_id: int) -> EmailDraftResponse:
    with get_db() as db:
        row = db.execute("SELECT * FROM email_drafts WHERE id = ?", (draft_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No such draft")
        return EmailDraftResponse(**dict(row))


@router.post("/emails/draft", response_model=EmailDraftResponse)
async def create_draft(payload: EmailDraftRequest) -> EmailDraftResponse:
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO email_drafts (case_id, to_addr, subject, body, status) VALUES (?, ?, ?, ?, 'DRAFT')",
            (payload.case_id, payload.to_addr, payload.subject, payload.body),
        )
        record_audit(db, "EMAIL_DRAFT_CREATED", "email_draft", cur.lastrowid)
        return EmailDraftResponse(
            id=cur.lastrowid, case_id=payload.case_id, to_addr=payload.to_addr,
            subject=payload.subject, body=payload.body, status="DRAFT",
        )


@router.post("/emails/{draft_id}/send")
async def send_email(draft_id: int, payload: EmailSendRequest) -> dict:
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Sending requires explicit confirm=true from the user")

    with get_db() as db:
        row = db.execute("SELECT * FROM email_drafts WHERE id = ?", (draft_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No such draft")
        if row["status"] == "SENT":
            raise HTTPException(status_code=409, detail="Draft already sent")

        provider = get_email_provider()
        sent = await provider.send(row["to_addr"], row["subject"], row["body"])

        db.execute(
            "UPDATE email_drafts SET status = 'SENT', sent_at = ?, provider_message_id = ? WHERE id = ?",
            (now_iso(), sent.get("id"), draft_id),
        )
        if row["case_id"]:
            db.execute(
                """INSERT INTO case_messages (case_id, provider, provider_message_id, direction, subject, body, sent_at)
                   VALUES (?, 'mock', ?, 'OUTBOUND', ?, ?, ?)""",
                (row["case_id"], sent.get("id"), row["subject"], row["body"], now_iso()),
            )
            # A fresh follow-up date, not the old (possibly already-overdue)
            # one — otherwise the next scheduler tick immediately flips the
            # case straight back to FOLLOW_UP_DUE (caught during manual
            # end-to-end testing: sending a follow-up email on an overdue
            # case re-overdue'd it within the next 60-second tick).
            next_follow_up = now() + timedelta(days=settings.follow_up_days)
            db.execute(
                "UPDATE cases SET status = 'WAITING_FOR_REPLY', follow_up_due_at = ?, updated_at = ? WHERE id = ?",
                (to_iso(next_follow_up), now_iso(), row["case_id"]),
            )
        record_audit(db, "EMAIL_SENT", "email_draft", draft_id)
        return {"id": draft_id, "status": "SENT", "provider_message_id": sent.get("id")}
