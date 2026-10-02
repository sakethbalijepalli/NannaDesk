"""Deterministic intent router (spec §9.1, §9.3).

A 0.8B model cannot be trusted to reliably emit well-formed tool-call JSON
(this is the single biggest technical risk in the spec's architecture), so
routing is keyword/regex-based first. The LLM is only ever used to *phrase*
a response from an already-decided, already-fetched result — never to
decide which tool runs. This also means `/api/chat` keeps working with
llama-server turned off, and the router itself needs no model to test.

Covers English and the romanized-Telugu / Telugu-English-mix phrases named
in spec §17 and the test scenarios in §19.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

MEAL_WORDS = {"breakfast": "breakfast", "lunch": "lunch", "dinner": "dinner", "tiffin": "breakfast"}

QUESTION_START = re.compile(r"^\s*(did|have|has|do|does|is|was|will|can|should|what|when|where|who)\b", re.I)


def _is_question(message: str) -> bool:
    return message.strip().endswith("?") or bool(QUESTION_START.match(message))


# Safety-sensitive patterns are checked first and always win — spec §16.3,
# §19.3: the assistant must never give dosing/treatment advice, and must
# escalate urgent symptoms, no matter what else the message also seems to
# be about.
SAFETY_PATTERNS = [
    (re.compile(r"\b(can i take|should i take)\b.*\b(two|2|another|extra|double)\b", re.I), "DOSE_ADVICE_DECLINED"),
    (re.compile(r"\bshould i stop\b", re.I), "STOP_TREATMENT_DECLINED"),
    (re.compile(r"\b(is (this|the|my) report dangerous|am i (going to be|ok|okay))\b", re.I), "REPORT_DANGER_QUESTION"),
    (re.compile(r"\b(forgot|forgotten|don'?t remember|not sure)\b.*\b(medic|tablet|dose|took|taking|teeskunn)", re.I), "UNKNOWN_DOSE"),
    (re.compile(r"\b(what should i do|what if i missed)\b.*\b(medic|dose|tablet)", re.I), "UNKNOWN_DOSE"),
    # Urgent-symptom descriptions (spec §19.3) must escalate to professional
    # care, never be treated as small talk for the free-form LLM fallback.
    (re.compile(
        r"\b(chest (pain|hurts?)|can'?t breathe|breathless|difficulty breathing|"
        r"severe (pain|bleeding)|fainted|fainting|dizzy|dizziness|unconscious|"
        r"numbness|slurred speech|stroke)\b", re.I,
    ), "URGENT_SYMPTOM"),
]

MEAL_CONFIRM = re.compile(
    r"\b(i (had|ate|finished|took)|tinna|tinesanu)\b.{0,15}\b(breakfast|lunch|dinner|tiffin)\b"
    r"|\b(breakfast|lunch|dinner|tiffin)\b.{0,15}\b(ayipoyindi|complete|done|finished)\b",
    re.I,
)
MEAL_STATUS_QUERY = re.compile(
    r"\bdid i (eat|have)\b.{0,15}\b(breakfast|lunch|dinner|tiffin)\b|\b(breakfast|lunch|dinner)\b.{0,10}\?",
    re.I,
)
# Statement form ("I took my medicine") — a confirmation to record, with
# no specific medicine named. chat.py resolves that deterministically (one
# pending med -> record it; more than one -> ask which, with buttons,
# never guess). See route()'s `known_medications` parameter for the
# DB-aware version that resolves a message naming a specific medicine.
MEDICATION_CONFIRM = re.compile(
    r"\bi (took|had)\b.{0,20}\b(medic|tablet|dose|pill)|teeskunnanu|teesukunnanu",
    re.I,
)
# Question form: "Did I take it?", "Have I taken my medicine?". No trailing
# word required — in this app's domain, "did/have I take(n)" is what it
# almost always means.
MEDICATION_STATUS_QUERY = re.compile(
    r"\b(did i take|have i taken|have i had)\b|teeskunnaana|teesukunna", re.I,
)
PENDING_QUERY = re.compile(r"\b(what'?s|whats) pending\b|pending (items|things|tasks)|emaindi pending", re.I)
EMAIL_DRAFT = re.compile(
    r"\b(write|draft|compose)\b.{0,20}\b(email|mail|letter)\b"
    # Spec §14.3's own example — "Write to my officer asking about my PF
    # payment." — names no email/mail/letter word at all.
    r"|\b(write|draft)\b.{0,10}\bto\b.{0,20}\b(officer|ddo|boss|department|office)\b",
    re.I,
)
EMAIL_FOLLOWUP = re.compile(
    r"\b(sent|mailed).{0,30}\b(last week|few days|reply|response|nobody replied)\b|did (he|she|they) respond",
    re.I,
)
GOVERNMENT_QUERY = re.compile(
    # Deliberately no bare "latest"/"update" alternative — those words
    # alone also match a page's own footer ("Last updated on …"), which
    # produced a nonsense answer during manual testing. Require a specific
    # government topic word, optionally combined with an update word.
    r"\b(prc|go\d|government order|pay ?commission|da update|pf update|"
    r"telangana government|circular|pension update|salary update)\b",
    re.I,
)
REPORT_EXPLAIN = re.compile(
    r"\bexplain\b.{0,15}\b(this|the|my)\b.{0,10}\b(report|blood|lab)\b"
    r"|\bwhat does\b.{0,15}\b(this|the|my)\b.{0,15}\b(report|blood|lab)\b.{0,10}\bmean\b"
    # Spec §20.3 step 5's own phrasing, right after an upload: no
    # "report/blood/lab" word at all. Ambiguous out of context, but this
    # exact phrase is unambiguous enough in NannaDesk's domain to accept.
    r"|\bexplain this\b",
    re.I,
)
LANGUAGE_SWITCH = re.compile(r"\benglish lo cheppu\b|\bin english\b", re.I)

# Guards a bare medicine-name mention from being read as a confirmation.
# Without this, "I had lunch but not Metformin" or "I haven't taken
# Metformin yet" both contain a confirming verb and the medicine name, with
# nothing else distinguishing them from an actual "I took Metformin" —
# caught in review before shipping, not from a live failure.
NEGATION = re.compile(r"\b(not|never|yet|forgot|missed|skip)\b|n't\b", re.I)

# If nothing above matched but the message still clearly names something in
# NannaDesk's domain, it must not fall through to the free-form LLM chat —
# that model has no access to the actual document/email/medicine data and
# would be guessing (spec: "never invent personal history"). Routed to
# "clarify" instead of "chat". Deliberately no trailing \b: "medic" must
# still match "medicine"/"medicines" ("report" -> "reports", etc).
DOMAIN_HINT = re.compile(
    r"\b(medic|tablet|dose|pill|breakfast|lunch|dinner|report|blood|lab|"
    r"email|mail|\bpf\b|prc|case|pending)", re.I,
)


@dataclass
class RouterResult:
    intent: str                       # tool name, or "chat" / "safety" / "language_switch" / "clarify"
    args: dict = field(default_factory=dict)
    safety_code: Optional[str] = None
    force_language: Optional[str] = None


def route(message: str, known_medications: Optional[list[str]] = None) -> RouterResult:
    """`known_medications` is every active medicine name, when the caller
    has them (chat.py does) — used so a named medicine counts as a domain
    word (for UNKNOWN_DOSE and the `clarify` fallback) and so a clear
    confirmation naming one ("I took Metformin") can resolve to it
    directly. Resolving a *bare* name reply ("Metformin" alone, answering
    NannaDesk's own "which one?") is deliberately NOT done here — the
    chat UI's CHOOSE_MEDICATION buttons cover that case, and a single word
    with no verb is too easy to misread as a confirmation that was never
    actually said.
    """
    known_medications = known_medications or []
    lowered = message.lower()

    for pattern, code in SAFETY_PATTERNS:
        if pattern.search(message):
            return RouterResult(intent="safety", safety_code=code)

    if LANGUAGE_SWITCH.search(message):
        return RouterResult(intent="language_switch", force_language="en")

    is_question = _is_question(message)

    # A clear, unambiguous confirmation naming a specific medicine: not a
    # question, no negation anywhere in the message, and the confirming
    # verb comes BEFORE the medicine's name (not just present somewhere —
    # "Metformin had side effects" has "had" after the name, not before).
    if not is_question and known_medications and not NEGATION.search(lowered):
        for name in known_medications:
            pattern = rf"\b(took|had|taken|teesukunnanu|teeskunnanu)\b.{{0,15}}\b{re.escape(name.lower())}\b"
            if re.search(pattern, lowered):
                return RouterResult(intent="record_medication_statement", args={"medication_name": name})

    # Question forms are checked before statement/confirmation forms so
    # "Have I had breakfast?" is answered, not recorded as a confirmation
    # (caught during manual testing: that exact phrase matched the meal
    # confirmation pattern because it contains the substring "I had").
    if is_question:
        if MEAL_STATUS_QUERY.search(message):
            return RouterResult(intent="get_meal_status", args={"meal_type": _extract_meal(message)})
        if MEDICATION_STATUS_QUERY.search(message):
            return RouterResult(intent="get_medication_status", args={"date": "today"})
        if PENDING_QUERY.search(message):
            return RouterResult(intent="get_pending_cases")
        if EMAIL_FOLLOWUP.search(message):
            return RouterResult(intent="search_email", args={"query": message})
        if EMAIL_DRAFT.search(message):
            return RouterResult(intent="create_email_draft", args={"request": message})
        if REPORT_EXPLAIN.search(message):
            return RouterResult(intent="explain_latest_report")
        if GOVERNMENT_QUERY.search(message):
            return RouterResult(intent="search_government", args={"query": message})
    else:
        if MEAL_CONFIRM.search(message):
            meal_type = _extract_meal(message)
            if meal_type:
                return RouterResult(intent="record_meal", args={"meal_type": meal_type})
        if MEDICATION_CONFIRM.search(message):
            return RouterResult(intent="record_medication_statement")
        if PENDING_QUERY.search(message):
            return RouterResult(intent="get_pending_cases")
        if EMAIL_FOLLOWUP.search(message):
            return RouterResult(intent="search_email", args={"query": message})
        if EMAIL_DRAFT.search(message):
            return RouterResult(intent="create_email_draft", args={"request": message})
        if REPORT_EXPLAIN.search(message):
            return RouterResult(intent="explain_latest_report")
        if GOVERNMENT_QUERY.search(message):
            return RouterResult(intent="search_government", args={"query": message})

    named_medicine = any(re.search(rf"\b{re.escape(n.lower())}\b", lowered) for n in known_medications)
    if DOMAIN_HINT.search(message) or named_medicine:
        return RouterResult(intent="clarify")

    return RouterResult(intent="chat")


def _extract_meal(message: str) -> Optional[str]:
    lowered = message.lower()
    for word, canonical in MEAL_WORDS.items():
        if word in lowered:
            return canonical
    return None
