# NannaDesk

> Remember. Understand. Get things done.

A local-first personal AI assistant built around one real person: a
non-technical father who needs help remembering routines, understanding
documents, following up on office work, and getting small administrative
tasks done. Built from `NannaDesk_Full_Project_Specification.pdf`.

**Architecture thesis** (kept throughout this codebase): *the LLM decides
how to help; deterministic software decides what actually happens.*
Medication state, email sending, reminder timing, and government-source
filtering all come from the database and a rule-based router — never from
model memory. The local LLM (Qwen3.5-0.8B via llama.cpp) only ever phrases
an already-decided, already-fetched result.

## What's real vs. stubbed in this build

| Piece | Status |
|---|---|
| Local chat, reminders, medication state machine, cases, audit trail | **Real** — SQLite, fully deterministic, has tests |
| Report parsing + explanation (PyMuPDF → flag → LLM phrasing) | **Real** — tested against two synthetic demo reports |
| Local LLM (Qwen3.5-0.8B, llama.cpp) | **Real** — runs fully offline |
| Voice transcription (whisper.cpp) | **Real** — `/api/voice/transcribe`, shells out per request |
| Government retrieval | **Real fetch** against live `telangana.gov.in` / `treasury.telangana.gov.in`, with a real allowlist, real passage extraction, and a real LLM summary when one's reachable. **Confirmed it cannot yet answer a substantive PRC question**: checked directly — neither allowlisted page's static HTML contains "pay revision" (or "PRC") anywhere, because the real GO listing is client-rendered. The honest "didn't find anything on the official page" response is what actually ships for that query today, not a working live answer — no JS execution would be the real fix. |
| Email | **Mock provider**, backed by the real `case_messages`/`cases` tables (not a toy in-memory list) — draft/search/send/follow-up-date all persist. Outlook/Microsoft Graph (`app/email/outlook.py`) needs an Azure app registration this build doesn't have — it raises a clear "not connected" error rather than silently falling back. |
| Family escalation | Implemented, disabled by default (`profile.family_escalation_enabled`) |
| Voice transcription | **Verified end-to-end**: `say` → ffmpeg → whisper-cli → exact transcript, through the real `/api/voice/transcribe` endpoint. |
| UI | **Visually verified** with Playwright: all four tabs, plus the full chat-driven email flow (type request → review the draft card inline → press Send → case status updates), no console errors. |
| Timezone | Medication/meal times are compared in this machine's own local timezone by default. Set `NANNADESK_TIMEZONE=Asia/Kolkata` explicitly if running the backend somewhere other than Dad's machine but scheduling for his location. |

### Known limitations (by design, not oversights)

- Fonts load from the Google Fonts CDN — typography will fall back to system fonts with Wi-Fi off. Self-hosting them (e.g. via `@fontsource`) would fix this; not done here.
- Chat's "explain this report" always points to the Documents tab rather than guessing which upload you mean — there's no "current report in this conversation" concept yet.
- Meal check-in reminders use fixed default times (8am/1pm/8pm), not per-profile configuration.
- The government source-matching in `app/ai/router.py` / `app/government/search.py` is keyword-based, as is all intent routing — see that module's docstring for why.

## Prerequisites (macOS)

```bash
brew install llama.cpp whisper-cpp ffmpeg
```

Models (not checked into git — see `.gitignore`):

```bash
curl -L -o models/qwen/Qwen3.5-0.8B-Q4_K_M.gguf \
  https://huggingface.co/unsloth/Qwen3.5-0.8B-GGUF/resolve/main/Qwen3.5-0.8B-Q4_K_M.gguf
curl -L -o models/whisper/ggml-small.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin
```

## Run it

```bash
# 1. Local LLM server (port 8080)
./scripts/start_llama.sh

# 2. Backend (port 8000) — first time: create the venv and install deps
python3.13 -m venv apps/api/.venv
source apps/api/.venv/bin/activate
pip install -r apps/api/requirements.txt
python scripts/seed_demo_data.py        # sanitized, fictional demo data
cd apps/api && uvicorn app.main:app --port 8000

# 3. Frontend (port 5173)
cd apps/web && npm install && npm run dev
```

Open http://localhost:5173. The dev server proxies `/api` to `:8000`.

Use Python **3.13**, not 3.14 — `pydantic-core` doesn't have prebuilt
wheels for 3.14 yet and fails to build from source.

### Demo story (spec §20.3)

1. Ask → "Any update on the latest PRC?" — fetches an official source live and cites it with a date; today it honestly reports no PRC-specific content found there rather than a live substantive answer (see the government retrieval limitation above — this is the one flow that doesn't fully deliver yet).
2. Ask → "Write to my officer asking about my PF payment." — a real draft appears inline, tied to the PF case; press Send on the card.
3. Documents → upload `data/reports/demo-blood-report-2.pdf`, get a calm explanation that still shows the abnormal values.
4. Home → confirm breakfast, then ask "Did I take my medicine?" (or "Have I taken my medicine?") for an exact, never-guessed status.
5. Ask → "What's pending?" for the PF case + medication status + the uploaded report, rolled into one answer.

### Tests

```bash
source apps/api/.venv/bin/activate
python -m pytest -q
```

54 tests, all deterministic — a conftest autouse fixture stubs the LLM as
unavailable so nothing depends on llama-server actually running. They
cover the medication/meal state machine never guessing a confirmation
(including the full reminder scheduler: meal gating, snooze timing,
followup-to-NOT_CONFIRMED escalation, case follow-up detection), the
router's safety/question/confirmation classification against phrases
taken verbatim from the spec, the "no-silent-sending" email gate, the
government freshness rule falling back to "internet required" instead of
a guess, the personal/government index separation, and the audit trail
carrying no free text.

## Repository layout

See spec §6. Notable deviations:
- `app/ai/router.py` is a deterministic keyword/regex router, not an
  LLM tool-call loop — a 0.8B model can't reliably emit tool JSON. The
  LLM is only ever asked to phrase an answer from an already-fetched
  result (see `app/ai/llm.py`'s docstring for the reasoning).
- `app/email/mock.py` reads/writes through the `case_messages` table
  instead of its own in-memory inbox, so seeded demo email persists
  across restarts.

## Design

The UI direction is a household ledger/register — Dad is a government
employee, and the product's job (remembering, confirming, tracking cases)
maps onto a ledger page rather than a SaaS dashboard. See
`apps/web/src/index.css` for the token rationale.
