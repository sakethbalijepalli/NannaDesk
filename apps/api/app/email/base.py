"""Email provider abstraction (spec §14.1). The LLM only ever reaches
`create_draft` through the tool registry — `send` is an application-level
action gated behind explicit user confirmation (spec §14.2, §16.2).
"""
from abc import ABC, abstractmethod
from typing import TypedDict


class EmailMessage(TypedDict, total=False):
    id: str
    thread_id: str
    to_addr: str
    subject: str
    body: str
    direction: str  # "OUTBOUND" | "INBOUND"
    sent_at: str


class EmailProvider(ABC):
    @abstractmethod
    async def search(self, query: str) -> list[EmailMessage]: ...

    @abstractmethod
    async def get_thread(self, thread_id: str) -> list[EmailMessage]: ...

    @abstractmethod
    async def create_draft(self, to_addr: str, subject: str, body: str) -> EmailMessage: ...

    @abstractmethod
    async def send(self, to_addr: str, subject: str, body: str) -> EmailMessage: ...
