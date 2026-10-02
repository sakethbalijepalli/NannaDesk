"""FastAPI entrypoint (spec §4, §6). Wires together the API routers, runs
DB migrations on startup, and starts the deterministic reminder scheduler.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import cases, chat, documents, emails, government, reminders, reports, voice
from app.db.connection import init_db
from app.reminders.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler(interval_seconds=60)
    yield
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


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
