"""POST /api/chat — spec §15, §15.1. Routes through the deterministic
intent router first (app/ai/router.py); the LLM only ever phrases a
response from an already-decided, already-fetched result.
"""
from fastapi import APIRouter

from app.ai.llm import LLMUnavailable, get_llm_provider
from app.ai.prompts import SYSTEM_PROMPT
from app.ai.router import route
from app.audit import record_audit
from app.clock import format_friendly_status, format_friendly_time
from app.db.connection import get_db
from app.db.models import Action, ChatRequest, ChatResponse, Source
from app.email.draft import build_draft
from app.reminders import engine

router = APIRouter()

SAFETY_RESPONSES = {
    "DOSE_ADVICE_DECLINED": (
        "I can't tell you to take an extra dose — that's not something I decide. "
        "Please follow the instructions on your prescription, or check with your "
        "doctor or pharmacist if you're unsure."
    ),
    "STOP_TREATMENT_DECLINED": (
        "I'm not able to tell you to stop a medicine — that needs to come from your "
        "doctor. If something feels wrong, it's worth calling them."
    ),
    "REPORT_DANGER_QUESTION": (
        "I can show you what the report says and what's outside the normal range, "
        "but I can't tell you whether it's dangerous — that needs a doctor's judgment. "
        "Would you like me to show you the report again?"
    ),
    "URGENT_SYMPTOM": (
        "I can't assess symptoms like that — please call a doctor or emergency services "
        "(108) now rather than waiting for me. I'm not able to help with this one."
    ),
}

# Message patterns that clearly name something in NannaDesk's domain but
# didn't match a specific route — asking rather than guessing (router's
# "clarify" intent).
CLARIFY_MESSAGE = (
    "I want to make sure I help with the right thing — could you say that a little "
    "differently? For example: \"did I take my medicine\", \"what's pending\", or "
    "\"explain this report\"."
)


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    with get_db() as db:
        active_names = [r["name"] for r in db.execute("SELECT name FROM medications WHERE active = 1")]
        decision = route(payload.message, known_medications=active_names)

        if decision.intent == "safety":
            message = SAFETY_RESPONSES.get(decision.safety_code, SAFETY_RESPONSES["DOSE_ADVICE_DECLINED"])
            if decision.safety_code == "UNKNOWN_DOSE":
                status_rows = engine.get_medication_status(db)
                if status_rows:
                    lines = [f"{r['med_name']}: {format_friendly_status(r['status'])}" for r in status_rows]
                    message = (
                        "I won't guess, and please don't take an extra dose just in case. "
                        "Here's what's actually on record:\n" + "\n".join(lines) +
                        "\nIf you're not sure, check your prescription instructions or ask a pharmacist."
                    )
            return ChatResponse(type="answer", message=message)

        if decision.intent == "clarify":
            return ChatResponse(type="needs_confirmation", message=CLARIFY_MESSAGE)

        if decision.intent == "get_meal_status":
            today = engine.get_today_schedule(db)
            meal_type = decision.args.get("meal_type")
            matches = [i for i in today if i["kind"] == "MEAL" and (not meal_type or i["label"].lower() == meal_type)]
            if not matches:
                return ChatResponse(type="answer", message="I don't have a record of that meal yet.")
            lines = [f"{m['label']}: {format_friendly_status(m['status'])}" for m in matches]
            return ChatResponse(type="answer", message="\n".join(lines))

        if decision.intent == "record_meal":
            result = engine.record_meal(db, decision.args["meal_type"])
            return ChatResponse(
                type="answer",
                message=f"Got it — {decision.args['meal_type']} confirmed.",
                actions=[Action(type="MEAL_CONFIRMED", payload=result)],
            )

        if decision.intent == "record_medication_statement":
            # A statement like "I took my medicine" names no specific
            # medicine. If the router already resolved one (named in the
            # message, or a bare reply to "which one?"), use it directly;
            # otherwise resolve deterministically: one pending med -> record
            # it; more than one -> ask which (with buttons), never guess.
            pending = [r for r in engine.get_medication_status(db) if r["status"] not in ("TAKEN", "SKIPPED")]
            named = decision.args.get("medication_name")
            target = next((r for r in pending if r["med_name"] == named), None) if named else None

            if not pending:
                return ChatResponse(type="answer", message="Everything's already confirmed — nothing pending right now.")
            if target is None and len(pending) > 1:
                names = ", ".join(r["med_name"] for r in pending)
                return ChatResponse(
                    type="needs_confirmation",
                    message=f"Which one did you take — {names}?",
                    actions=[Action(
                        type="CHOOSE_MEDICATION",
                        payload={"options": [{"event_id": r["id"], "name": r["med_name"]} for r in pending]},
                    )],
                )
            target = target or pending[0]
            result = engine.record_medication(db, target["id"], "TAKEN")
            return ChatResponse(
                type="answer", message=f"Got it — {target['med_name']} confirmed.",
                actions=[Action(type="MEDICATION_CONFIRMED", payload=result)],
            )

        if decision.intent == "get_medication_status":
            rows = engine.get_medication_status(db)
            if not rows:
                return ChatResponse(type="answer", message="You have no medications scheduled today.")
            lines = []
            for r in rows:
                if r["status"] in ("TAKEN", "SKIPPED"):
                    lines.append(f"{r['med_name']}: {r['status'].lower()} at {format_friendly_time(r['confirmed_at'])}".strip())
                else:
                    lines.append(f"{r['med_name']}: not confirmed yet")
            return ChatResponse(type="answer", message="\n".join(lines))

        if decision.intent == "get_pending_cases":
            cases = engine.get_pending_cases(db)
            med_status = [r for r in engine.get_medication_status(db) if r["status"] not in ("TAKEN", "SKIPPED")]
            recent_docs = db.execute(
                "SELECT filename, doc_type, uploaded_at FROM documents ORDER BY uploaded_at DESC LIMIT 1"
            ).fetchall()
            lines = [f"- {c['title']} ({format_friendly_status(c['status'])})" for c in cases]
            lines += [f"- {m['med_name']}: not confirmed yet" for m in med_status]
            lines += [f"- {d['filename']}: uploaded {format_friendly_time(d['uploaded_at'])}" for d in recent_docs]
            if not lines:
                return ChatResponse(type="answer", message="Nothing pending right now.")
            return ChatResponse(type="answer", message="You have a few things pending:\n" + "\n".join(lines))

        if decision.intent == "search_government":
            from app.ai.tools import search_government as tool_search_government
            from app.db.models import SearchGovernmentArgs
            result = await tool_search_government(db, SearchGovernmentArgs(query=decision.args["query"]))
            return ChatResponse(
                type="answer", message=result["answer"],
                sources=[Source(**s) for s in result["sources"]],
            )

        if decision.intent == "search_email":
            awaiting = engine.find_awaiting_reply_cases(db)
            if not awaiting:
                return ChatResponse(type="answer", message="I don't see anything you're waiting on a reply for.")
            lines = []
            for item in awaiting:
                case, last = item["case"], item["last_message"]
                if last:
                    sent_when = format_friendly_time(last["sent_at"]) or last["sent_at"]
                    lines.append(
                        f"You emailed about \"{case['title']}\" ({last['subject']}) — no reply recorded yet "
                        f"(sent {sent_when})."
                    )
                else:
                    lines.append(f"\"{case['title']}\" is still open with no reply on record.")
            lines.append("Want me to draft a follow-up?")
            first_case = awaiting[0]["case"]
            return ChatResponse(
                type="needs_confirmation", message="\n".join(lines),
                actions=[Action(type="OFFER_FOLLOWUP_DRAFT", payload={"case_title": first_case["title"]})],
            )

        if decision.intent == "create_email_draft":
            draft = await build_draft(db, decision.args.get("request", payload.message))
            cur = db.execute(
                "INSERT INTO email_drafts (case_id, to_addr, subject, body, status) VALUES (?, ?, ?, ?, 'DRAFT')",
                (draft["case_id"], draft["to_addr"], draft["subject"], draft["body"]),
            )
            record_audit(db, "EMAIL_DRAFT_CREATED", "email_draft", cur.lastrowid)
            return ChatResponse(
                type="needs_confirmation",
                message=f"Here's a draft to {draft['to_addr']} — review it below and press Send when ready.",
                actions=[Action(type="EMAIL_DRAFT_CREATED", payload={"id": cur.lastrowid})],
            )

        if decision.intent == "explain_latest_report":
            return ChatResponse(
                type="needs_confirmation",
                message="Upload the report under 'Explain a document' and I'll walk through it with you.",
            )

        if decision.intent == "language_switch":
            return ChatResponse(type="answer", message="Sure — I'll reply in English from now on.")

        # Fallback: general conversation, phrased by the LLM if available.
        # The router's "clarify" branch already catches anything that
        # names NannaDesk's own data (medicine, email, reports, ...), so
        # whatever reaches here is genuinely outside what the app knows
        # about — safe to hand to the open-ended model.
        try:
            llm = get_llm_provider()
            text = await llm.chat([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": payload.message},
            ])
            return ChatResponse(type="answer", message=text)
        except LLMUnavailable:
            return ChatResponse(
                type="answer",
                message=(
                    "I'm not able to reach my local language model right now, so I can only "
                    "help with the things I can look up directly — medicines, meals, pending "
                    "items, email search, and government updates."
                ),
            )
