"""ElevenLabs text-to-speech is strictly optional — same pattern as
Outlook and LLMUnavailable elsewhere in this codebase: absence of
ELEVENLABS_API_KEY must degrade quietly, never break the request.
"""
from fastapi.testclient import TestClient

from app.voice import tts


def test_is_configured_false_without_api_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert tts.is_configured() is False


async def test_synthesize_speech_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setattr(tts, "_client", None)

    result = await tts.synthesize_speech("hello")

    assert result is None


async def test_synthesize_speech_degrades_on_sdk_error(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(tts, "_client", None)

    class _ExplodingClient:
        class text_to_speech:
            @staticmethod
            def convert(**kwargs):
                raise RuntimeError("network unavailable")

    monkeypatch.setattr(tts, "_get_client", lambda: _ExplodingClient())

    result = await tts.synthesize_speech("hello")

    assert result is None


def _client(db_path):
    from app.main import app
    return TestClient(app)


def test_speak_endpoint_returns_503_when_not_configured(db_path, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    from app.voice import tts as tts_module
    monkeypatch.setattr(tts_module, "_client", None)

    with _client(db_path) as client:
        resp = client.post("/api/voice/speak", json={"text": "hello"})

    assert resp.status_code == 503


def test_speak_endpoint_returns_audio_when_configured(db_path, monkeypatch):
    async def fake_synthesize(text):
        return b"fake-mp3-bytes"

    from app.api import voice as voice_module
    monkeypatch.setattr(voice_module, "synthesize_speech", fake_synthesize)

    with _client(db_path) as client:
        resp = client.post("/api/voice/speak", json={"text": "hello"})

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"
    assert resp.content == b"fake-mp3-bytes"
