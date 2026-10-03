"""FastAPI entrypoint (spec §4, §6). Wires together the API routers, runs
DB migrations on startup, and starts the deterministic reminder scheduler.
"""
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Loaded before any other app import, into the real process environment —
# not through app.config's NANNADESK_-prefixed Settings. This is deliberate:
# ElevenLabs' own SDK (app/voice/tts.py) auto-detects a plain
# ELEVENLABS_API_KEY from the environment per its own documented
# convention, and that convention is what we're following, not translating
# it into our own prefix scheme.
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import cases, chat, documents, emails, government, medications, profile, reminders, reports, voice
from app.db.connection import init_db
from app.government.goir import start_browser, stop_browser
from app.reminders.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler(interval_seconds=60)
    await start_browser()
    yield
    await stop_browser()
    stop_scheduler()


app = FastAPI(title="NannaDesk API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(reminders.router, prefix="/api")
app.include_router(emails.router, prefix="/api")
app.include_router(government.router, prefix="/api")
app.include_router(cases.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(medications.router, prefix="/api")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
