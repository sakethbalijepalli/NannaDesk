"""The tool set from spec §9.2, with Pydantic argument validation per
§9.3 ("the model should never generate raw Python, SQL, filesystem paths,
or arbitrary network requests"). `send_email` is deliberately absent —
sending is an application action gated by explicit user confirmation
(spec §14.2), never something the model can request directly.
"""
import sqlite3

from app.audit import record_audit
from app.clock import now, to_iso
from app.db.models import (
    CompareReportsArgs, CreateEmailDraftArgs, CreateReminderArgs,
    GetMedicationStatusArgs, RecordMealArgs, RecordMedicationArgs,
    SearchDocumentsArgs, SearchEmailArgs, SearchGovernmentArgs,
)
from app.email.factory import get_email_provider
from app.government.search import search_government as _search_government
from app.health.labs import compare as compare_labs
from app.memory.retrieval import search_documents as _search_documents
from app.memory.retrieval import search_personal_memory as _search_personal_memory
from app.reminders import engine


def search_personal_memory(db: sqlite3.Connection, args: SearchDocumentsArgs) -> dict:
    return _search_personal_memory(db, args.query)


def search_documents(db: sqlite3.Connection, args: SearchDocumentsArgs) -> list[dict]:
    return _search_documents(db, args.query)


async def search_government(db: sqlite3.Connection, args: SearchGovernmentArgs) -> dict:
    result = await _search_government(args.query)
    return result.model_dump()


def get_today_schedule(db: sqlite3.Connection, args: None = None) -> list[dict]:
    return engine.get_today_schedule(db)


def get_medication_status(db: sqlite3.Connection, args: GetMedicationStatusArgs) -> list[dict]:
    return engine.get_medication_status(db, medication_name=args.medication)


def record_meal(db: sqlite3.Connection, args: RecordMealArgs) -> dict:
    return engine.record_meal(db, args.meal_type)


def record_medication(db: sqlite3.Connection, args: RecordMedicationArgs) -> dict:
    """Resolves today's event row for the given schedule, then records the
    explicit, user-stated outcome. Never invoked without a prior user
    statement — the router only reaches this after parsing a clear
    confirmation, and the chat layer re-confirms when ambiguous.
    """
    today_events = engine.get_medication_status(db)
    event = next((e for e in today_events if e["medication_schedule_id"] == args.medication_schedule_id), None)
    if event is None:
        raise ValueError("No scheduled medication event found for today")
    return engine.record_medication(db, event["id"], args.outcome)


def get_pending_cases(db: sqlite3.Connection, args: None = None) -> list[dict]:
    return engine.get_pending_cases(db)


async def search_email(db: sqlite3.Connection, args: SearchEmailArgs) -> list[dict]:
    provider = get_email_provider()
    results = await provider.search(args.query)
    return list(results)


def create_email_draft(db: sqlite3.Connection, args: CreateEmailDraftArgs) -> dict:
    cur = db.execute(
        "INSERT INTO email_drafts (case_id, to_addr, subject, body, status) VALUES (?, ?, ?, ?, 'DRAFT')",
        (args.case_id, args.to_addr, args.subject, args.body),
    )
    record_audit(db, "EMAIL_DRAFT_CREATED", "email_draft", cur.lastrowid)
    return {"id": cur.lastrowid, "case_id": args.case_id, "to_addr": args.to_addr,
            "subject": args.subject, "body": args.body, "status": "DRAFT"}


def create_reminder(db: sqlite3.Connection, args: CreateReminderArgs) -> dict:
    due_at_iso = to_iso(args.due_at)
    cur = db.execute(
        "INSERT INTO reminders (kind, label, due_at, status) VALUES (?, ?, ?, 'PENDING')",
        (args.kind, args.label, due_at_iso),
    )
    record_audit(db, "REMINDER_CREATED", "reminder", cur.lastrowid)
    return {"id": cur.lastrowid, "kind": args.kind, "label": args.label, "due_at": due_at_iso}


def compare_reports(db: sqlite3.Connection, args: CompareReportsArgs) -> list[dict]:
    current = [dict(r) for r in db.execute(
        "SELECT * FROM lab_results WHERE document_id = ?", (args.document_id,)
    )]
    doc = db.execute("SELECT * FROM documents WHERE id = ?", (args.document_id,)).fetchone()
    if not doc:
        raise ValueError("No such document")

    previous_doc = db.execute(
        """SELECT * FROM documents WHERE doc_type = 'LAB_REPORT' AND id != ?
           AND uploaded_at < ? ORDER BY uploaded_at DESC LIMIT 1""",
        (args.document_id, doc["uploaded_at"]),
    ).fetchone()
    previous = []
    if previous_doc:
        previous = [dict(r) for r in db.execute(
            "SELECT * FROM lab_results WHERE document_id = ?", (previous_doc["id"],)
        )]
    return compare_labs(current, previous)


TOOL_REGISTRY = {
    "search_personal_memory": search_personal_memory,
    "search_documents": search_documents,
    "search_government": search_government,
    "get_today_schedule": get_today_schedule,
    "get_medication_status": get_medication_status,
    "record_meal": record_meal,
    "record_medication": record_medication,
    "get_pending_cases": get_pending_cases,
    "search_email": search_email,
    "create_email_draft": create_email_draft,
    "create_reminder": create_reminder,
    "compare_reports": compare_reports,
}
