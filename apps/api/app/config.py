"""Central configuration. Everything that varies between a dev laptop and
Dad's real machine lives here, read from environment variables so no secret
or path is hardcoded in application logic.
"""
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_ROOT = Path(__file__).resolve().parents[1]      # apps/api
PROJECT_ROOT = APP_ROOT.parents[1]                   # repo root


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NANNADESK_", env_file=".env", extra="ignore")

    # Wall-clock timezone. Medication/meal schedule times ("08:30") are
    # local times, compared against this. None (the default) means "use
    # this machine's own local timezone" — right on Dad's laptop. Set
    # NANNADESK_TIMEZONE=Asia/Kolkata explicitly when running the backend
    # somewhere else (e.g. a dev machine in a different timezone) but
    # scheduling for Dad's actual location.
    timezone: Optional[str] = None

    # Storage
    db_path: Path = PROJECT_ROOT / "data" / "nannadesk.db"
    documents_dir: Path = PROJECT_ROOT / "data" / "documents"
    reports_dir: Path = PROJECT_ROOT / "data" / "reports"

    # Local LLM (llama.cpp OpenAI-compatible server)
    llm_base_url: str = "http://127.0.0.1:8080"
    llm_model_name: str = "qwen3.5-0.8b"
    llm_timeout_seconds: float = 20.0

    # Email provider: "mock" until Outlook/Graph credentials are configured
    email_provider: str = "mock"
    outlook_client_id: str | None = None
    outlook_client_secret: str | None = None
    outlook_tenant_id: str | None = None

    # Government retrieval
    government_allowlist: tuple[str, ...] = (
        "telangana.gov.in",
        "tgepfo.cgg.gov.in",
        "treasury.telangana.gov.in",
    )
    government_fetch_timeout_seconds: float = 10.0

    # Text-to-speech (ElevenLabs). The API key itself is deliberately NOT
    # here — see app/voice/tts.py and main.py's load_dotenv() call for why
    # it's read as a plain ELEVENLABS_API_KEY, following ElevenLabs' own
    # documented convention rather than our NANNADESK_ prefix.
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"  # "Sarah" — soft, warm; matches the spec's personality (§10.3)
    elevenlabs_model_id: str = "eleven_multilingual_v2"  # long-form quality; see tts.py's docstring on Telugu coverage

    # Reminder escalation
    family_escalation_default_enabled: bool = False

    # Days after sending before a case is considered overdue for a reply
    # (spec §14.4's example uses 7 days between sent and follow-up-due).
    follow_up_days: int = 7


settings = Settings()

# Ensure local data directories exist at import time — this is local,
# idempotent filesystem setup, not a side effect worth hiding.
settings.db_path.parent.mkdir(parents=True, exist_ok=True)
settings.documents_dir.mkdir(parents=True, exist_ok=True)
settings.reports_dir.mkdir(parents=True, exist_ok=True)
