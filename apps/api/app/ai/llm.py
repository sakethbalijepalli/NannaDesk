"""Model abstraction (spec §10.1). The rest of the application speaks to
`LLMProvider`, never to Qwen/llama.cpp internals directly, so the model
can be swapped without touching application logic.
"""
import logging
import re
from abc import ABC, abstractmethod

import httpx

from app.config import settings

logger = logging.getLogger("nannadesk.llm")

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class LLMUnavailable(Exception):
    """Raised when the local model can't be reached. Callers must fall
    back to a deterministic template response — never to silence or to a
    guess (spec §18.3: the LLM only narrates already-computed facts).
    """


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 500) -> str:
        raise NotImplementedError


class LlamaCppProvider(LLMProvider):
    """Talks to llama-server's OpenAI-compatible /v1/chat/completions."""

    def __init__(self, base_url: str | None = None, model: str | None = None, timeout: float | None = None):
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model_name
        self.timeout = timeout or settings.llm_timeout_seconds

    async def chat(self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 500) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    # max_tokens is a hard backstop even when --reasoning-budget
                    # isn't set server-side — a small reasoning model can
                    # otherwise generate for tens of thousands of tokens
                    # before producing a one-line answer.
                    json={"model": self.model, "messages": messages, "temperature": temperature,
                          "max_tokens": max_tokens,
                          # A small model repeating a line verbatim until it
                          # hits max_tokens was observed during development
                          # (e.g. "see a doctor immediately" dozens of
                          # times) — frequency_penalty makes that far less
                          # likely without otherwise changing phrasing.
                          "frequency_penalty": 0.4},
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return _strip_think_blocks(content).strip()
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            logger.warning("LLM call failed: %s", exc)
            raise LLMUnavailable(str(exc)) from exc


def _strip_think_blocks(text: str) -> str:
    """Qwen3-family models may emit <think>...</think> reasoning blocks
    before the actual answer; those are never shown to Dad.
    """
    return _THINK_BLOCK.sub("", text)


_default_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = LlamaCppProvider()
    return _default_provider
