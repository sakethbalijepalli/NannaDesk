"""Pydantic DTOs for the API layer and for validating LLM tool-call
arguments (spec §9.3: "Validate tool arguments with Pydantic before
execution"). These are transport/validation shapes, not the SQL schema.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class Source(BaseModel):
    title: str
    date: Optional[str] = None
    url: Optional[str] = None
    official: bool = False


class Action(BaseModel):
    type: str
    payload: dict = {}


class ChatResponse(BaseModel):
    type: Literal["answer", "needs_confirmation", "error"] = "answer"
    message: str
    sources: list[Source] = []
    actions: list[Action] = []


# ---------------------------------------------------------------------------
# Reminders / events
# ---------------------------------------------------------------------------

EventStatus = Literal[
    "SCHEDULED", "REMINDER_SENT", "TAKEN", "SNOOZED",
    "NOT_CONFIRMED", "SKIPPED", "UNKNOWN", "CONFIRMED",
]


class TodayItem(BaseModel):
    event_id: Optional[int] = None
    kind: Literal["MEAL", "MEDICATION"]
    label: str
    status: EventStatus
    due_time: Optional[str] = None


class TodayResponse(BaseModel):
    date: str
    items: list[TodayItem]


class ReminderCreate(BaseModel):
    kind: Literal["MEDICATION", "MEAL", "FOLLOW_UP", "CUSTOM"]
    label: str
    due_at: datetime


class ConfirmEventRequest(BaseModel):
    """What the user explicitly stated — never inferred by the model."""
    outcome: Literal["TAKEN", "SKIPPED", "CONFIRMED"]


class SnoozeEventRequest(BaseModel):
    minutes: int = Field(default=15, ge=1, le=180)


# ---------------------------------------------------------------------------
# Reports / lab results
# ---------------------------------------------------------------------------


class LabResult(BaseModel):
    test: str
    value: float
    unit: Optional[str] = None
    reference_low: Optional[float] = None
    reference_high: Optional[float] = None
    flag: Literal["LOW", "NORMAL", "HIGH"]
    source_page: Optional[int] = None


class ReportExplainResponse(BaseModel):
    what_it_says: list[str]
    what_it_may_mean: str
    what_changed: list[str]
    questions_for_doctor: list[str]
    when_to_seek_help: list[str]
    results: list[LabResult]


# ---------------------------------------------------------------------------
# Email / cases
# ---------------------------------------------------------------------------


class EmailDraftRequest(BaseModel):
    case_id: Optional[int] = None
    to_addr: str
    subject: str
    body: str


class EmailDraftResponse(BaseModel):
    id: int
    case_id: Optional[int]
    to_addr: str
    subject: str
    body: str
    status: Literal["DRAFT", "SENT"]


class EmailSendRequest(BaseModel):
    confirm: bool = False


class CaseOut(BaseModel):
    id: int
    type: str
    title: str
    status: str
    follow_up_due_at: Optional[datetime] = None
    updated_at: datetime


# ---------------------------------------------------------------------------
# Government
# ---------------------------------------------------------------------------


class GovernmentSearchRequest(BaseModel):
    query: str = Field(min_length=1)


class GovernmentAnswer(BaseModel):
    answer: str
    sources: list[Source]


# ---------------------------------------------------------------------------
# Tool-calling contract (spec §9.3)
# ---------------------------------------------------------------------------


class GetMedicationStatusArgs(BaseModel):
    date: Literal["today", "yesterday"] = "today"
    medication: Optional[str] = None


class RecordMealArgs(BaseModel):
    meal_type: Literal["breakfast", "lunch", "dinner"]


class RecordMedicationArgs(BaseModel):
    medication_schedule_id: int
    outcome: Literal["TAKEN", "SKIPPED"]


class SearchDocumentsArgs(BaseModel):
    query: str = Field(min_length=1)


class SearchGovernmentArgs(BaseModel):
    query: str = Field(min_length=1)


class SearchEmailArgs(BaseModel):
    query: str = Field(min_length=1)


class CreateEmailDraftArgs(BaseModel):
    case_id: Optional[int] = None
    to_addr: str
    subject: str
    body: str


class CreateReminderArgs(BaseModel):
    kind: Literal["MEDICATION", "MEAL", "FOLLOW_UP", "CUSTOM"]
    label: str
    due_at: datetime


class CompareReportsArgs(BaseModel):
    document_id: int
