"""Text-to-speech via ElevenLabs — closes the voice loop the spec's
accessibility principle asks for (§2.3, §2.1): NannaDesk could only
*listen* (whisper.cpp) until now. For a non-technical user who may not
want to read every answer, speaking it back is a real feature, not a
bolt-on for a prize category.

Strictly optional and additive: with no ELEVENLABS_API_KEY configured,
`synthesize_speech` returns None and callers degrade to text-only — the
same pattern this codebase already uses for Outlook (not configured) and
the local LLM (LLMUnavailable). Nothing about the local-first core depends
on this being present.

Uses the official `elevenlabs` SDK per ElevenLabs' own documented
convention (ElevenLabs() auto-reads a plain ELEVENLABS_API_KEY from the
environment — see main.py's load_dotenv() call for why that's a plain env
var, not one of our own NANNADESK_-prefixed settings) rather than a
hand-rolled REST call.
"""
import asyncio
import logging
import os

from app.config import settings

logger = logging.getLogger("nannadesk.tts")

_client = None
_client_checked = False


def _get_client():
    """Lazy, cached — avoids constructing a client (and importing the SDK's
    network stack) on every call, but re-checks for a key that wasn't set
    at import time, since `.env` setup can happen after the server starts.
    """
    global _client, _client_checked
    if _client is not None:
        return _client
    if not os.getenv("ELEVENLABS_API_KEY"):
        return None
    from elevenlabs import ElevenLabs
    _client = ElevenLabs()
    return _client


def _synthesize_sync(text: str) -> bytes | None:
    client = _get_client()
    if client is None:
        return None
    try:
        # eleven_multilingual_v2 covers 29 languages at long-form quality.
        # Telugu-English mixed phrasing (spec §17) hasn't been verified
        # against it yet — the spec's own quality note applies here too:
        # "do not assume ... measure it." If Telugu comes out wrong,
        # eleven_v3 (70+ languages) is the documented fallback — change
        # settings.elevenlabs_model_id, nothing else.
        audio_chunks = client.text_to_speech.convert(
            text=text,
            voice_id=settings.elevenlabs_voice_id,
            model_id=settings.elevenlabs_model_id,
        )
        return b"".join(audio_chunks)
    except Exception as exc:
        # Never let a voice-output failure break the (already-delivered)
        # text answer — log and degrade, same as every other optional
        # external call in this codebase.
        logger.warning("ElevenLabs synthesis failed: %s", exc)
        return None


async def synthesize_speech(text: str) -> bytes | None:
    """Returns MP3 bytes, or None if ElevenLabs isn't configured or the
    call failed. Runs the SDK's synchronous client in a thread, same
    pattern as app/api/voice.py's whisper-cli/ffmpeg subprocess calls.
    """
    return await asyncio.to_thread(_synthesize_sync, text)


def is_configured() -> bool:
    return bool(os.getenv("ELEVENLABS_API_KEY"))
