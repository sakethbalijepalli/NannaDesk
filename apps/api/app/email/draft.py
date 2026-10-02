"""Builds an email draft from Dad's profile and a matched case (spec
§14.2, §14.3) — a blank composer he'd have to hand-type isn't what the
spec means by "Write an email about my PF payment."
"""
import sqlite3

from app.ai.llm import LLMUnavailable, LLMProvider, get_llm_provider

DRAFT_POLICY = """You draft short, respectful office emails on behalf of a government employee,
to be reviewed and sent by that employee — you never send anything yourself.
Keep it under 120 words. Use "Respected Sir/Madam," as the salutation and
close with the employee's name. State the request plainly; don't invent
details not given to you."""


def _match_case(db: sqlite3.Connection, request_text: str) -> dict | None:
    lowered = request_text.lower()
    keyword_by_type = {"pf": "PF", "prc": "PRC", "salary": "GENERAL", "pension": "GENERAL"}
    for keyword, case_type in keyword_by_type.items():
        if keyword in lowered:
            row = db.execute(
                "SELECT * FROM cases WHERE type = ? ORDER BY updated_at DESC LIMIT 1", (case_type,)
            ).fetchone()
            if row:
                return dict(row)
    # No keyword match: fall back to the most recently active open case,
    # if any — still never guesses which case when there isn't one.
    row = db.execute(
        "SELECT * FROM cases WHERE status != 'RESOLVED' ORDER BY updated_at DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


async def build_draft(db: sqlite3.Connection, request_text: str,
                       llm: LLMProvider | None = None) -> dict:
    llm = llm or get_llm_provider()
    profile_row = db.execute("SELECT * FROM profile LIMIT 1").fetchone()
    profile = dict(profile_row) if profile_row else {}
    case = _match_case(db, request_text)

    to_addr = profile.get("ddo_email") or "officer@example.gov.in"
    subject = f"Request for update on {case['title']}" if case else "Request for assistance"
    name = profile.get("name", "")
    employee_code = profile.get("employee_code")

    facts = (
        f"Employee: {name}\n"
        f"Designation: {profile.get('designation', '')}\n"
        f"Department: {profile.get('department', '')}\n"
        + (f"Employee code: {employee_code}\n" if employee_code else "")
        + (f"Subject of the case: {case['title']}\n" if case else "")
        + f"What Dad asked for: {request_text}"
    )

    try:
        body = await llm.chat([
            {"role": "system", "content": DRAFT_POLICY},
            {"role": "user", "content": facts},
        ], max_tokens=350)
    except LLMUnavailable:
        subject_line = case["title"].lower() if case else "the matter raised below"
        body = (
            f"Respected Sir/Madam,\n\n"
            f"I am writing to kindly request an update regarding {subject_line}"
            + (f", employee code {employee_code}." if employee_code else ".")
            + f"\n\nKindly let me know the current status at your convenience.\n\n"
            f"Thank you,\n{name}"
        )

    return {"to_addr": to_addr, "subject": subject, "body": body, "case_id": case["id"] if case else None}
