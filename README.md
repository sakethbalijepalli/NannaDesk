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
| Government retrieval | **Real search against the actual GO repository**, goir.telangana.gov.in (Telangana's Government Order Issue Register) — not the originally-tried `telangana.gov.in/government-orders/` page, which turned out not to be a GO listing at all (checked directly, with and without JS rendering: it's a generic info page). The real repository is an ASP.NET form-postback search, so this is driven with a persistent headless Chromium (Playwright) rather than a plain HTTP GET. Verified live: "Any update on PRC?" returns real GO numbers, departments, dates, and subject lines about actual Pay Revision Commission orders. Falls back to the old static-page fetch only if Chromium isn't installed. |
| Email | **Mock provider**, backed by the real `case_messages`/`cases` tables (not a toy in-memory list) — draft/search/send/follow-up-date all persist. Outlook/Microsoft Graph (`app/email/outlook.py`) needs an Azure app registration this build doesn't have — it raises a clear "not connected" error rather than silently falling back. |
| Family escalation | Implemented, disabled by default (`profile.family_escalation_enabled`) |
| Voice transcription | **Verified end-to-end**: `say` → ffmpeg → whisper-cli → exact transcript, through the real `/api/voice/transcribe` endpoint. |
| UI | **Visually verified** with Playwright: all five tabs, the full chat-driven email flow (type request → review the draft card inline → press Send → case status updates), and the Settings save/add/remove round-trips, no console errors. |
| Timezone | Medication/meal times are compared in this machine's own local timezone by default. Set `NANNADESK_TIMEZONE=Asia/Kolkata` explicitly if running the backend somewhere other than Dad's machine but scheduling for his location. |
| Voice output (ElevenLabs TTS) | **Real**, optional, on-demand — a 🔊 button on each NannaDesk chat reply (`/api/voice/speak`). Closes the loop the spec's voice-first principle asks for: NannaDesk could only listen (whisper.cpp) before this. Degrades silently to text-only with no `ELEVENLABS_API_KEY` set — never breaks the chat response. |
| Real-data setup | **Real** — a Settings tab (`/api/profile`, `/api/medications`) to enter Dad's actual profile and medications through the browser, no script-editing required. `scripts/seed_demo_data.py --wipe-only` clears the fictional seed first. |

### Known limitations (by design, not oversights)

- Fonts load from the Google Fonts CDN — typography will fall back to system fonts with Wi-Fi off. Self-hosting them (e.g. via `@fontsource`) would fix this; not done here.
- Chat's "explain this report" always points to the Documents tab rather than guessing which upload you mean — there's no "current report in this conversation" concept yet.
- Meal check-in reminders use fixed default times (8am/1pm/8pm), not per-profile configuration.
- The government source-matching in `app/ai/router.py` / `app/government/search.py` is keyword-based, as is all intent routing — see that module's docstring for why.
- GOIR's search is a literal exact-text substring match, not a tokenized multi-word search (confirmed live). A query combining a generic trigger word (e.g. "circular") with unrelated terms can return real-but-loosely-related orders rather than "no results" — a standalone "circular" query is itself a legitimate spec-intended trigger, so this wasn't over-engineered further. Specific topics (PRC, DA, salary, pension) are unaffected.
- A GOIR search takes ~5s (headless page load + form postback + LLM phrasing) — slower than the other chat intents, with no loading indicator in the chat UI yet beyond the disabled input.

## Prerequisites (macOS)

```bash
brew install llama.cpp whisper-cpp ffmpeg
```

Government search drives a real headless Chromium (see "Government retrieval"
above). After installing Python deps below:

```bash
playwright install chromium
```

Without this, government search falls back to the weaker static-page fetch
rather than failing — but the live demo story needs it.

Voice output is optional. To enable it, follow ElevenLabs' own setup flow
(`elevenlabs.io/app/settings/api-keys`) and put the key in `apps/api/.env`:

```
ELEVENLABS_API_KEY=your-key-here
```

Note this is a **plain** env var, not `NANNADESK_`-prefixed like the rest
of this app's config — see `app/voice/tts.py`'s docstring for why.

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

### Switching from demo data to a real profile

```bash
python scripts/seed_demo_data.py --wipe-only   # clears the fictional seed, leaves the schema
```

Then open the **Settings** tab and fill in a real profile and medications
through the browser. This data lives only in the local SQLite file
(`data/nannadesk.db`, gitignored) — it's never committed or published.

### Demo story (spec §20.3)

1. Ask → "Any update on the latest PRC?" — searches the real GO register live and cites real order numbers, dates, and subjects, with a source link.
2. Ask → "Write to my officer asking about my PF payment." — a real draft appears inline, tied to the PF case; press Send on the card.
3. Documents → upload `data/reports/demo-blood-report-2.pdf`, get a calm explanation that still shows the abnormal values.
4. Home → confirm breakfast, then ask "Did I take my medicine?" (or "Have I taken my medicine?") for an exact, never-guessed status.
5. Ask → "What's pending?" for the PF case + medication status + the uploaded report, rolled into one answer.

### Tests

```bash
source apps/api/.venv/bin/activate
python -m pytest -q
```

81 tests, all deterministic — a conftest autouse fixture stubs the LLM as
unavailable, and the GOIR browser search is mocked rather than hitting the
live site, so nothing depends on llama-server or network access. They
cover the medication/meal state machine never guessing a confirmation
(including the full reminder scheduler: meal gating, snooze timing,
followup-to-NOT_CONFIRMED escalation, case follow-up detection), the
router's safety/question/confirmation classification against phrases
taken verbatim from the spec (plus regressions for a question or negation
never recording a medication confirmation), the "no-silent-sending" email
gate, the government freshness rule falling back to "internet required"
instead of a guess, the personal/government index separation, and the
audit trail carrying no free text.

## Repository layout

See spec §6. Notable deviations:
- `app/ai/router.py` is a deterministic keyword/regex router, not an
  LLM tool-call loop — a 0.8B model can't reliably emit tool JSON. The
  LLM is only ever asked to phrase an answer from an already-fetched
  result (see `app/ai/llm.py`'s docstring for the reasoning).
- `app/email/mock.py` reads/writes through the `case_messages` table
  instead of its own in-memory inbox, so seeded demo email persists
  across restarts.
- `app/government/goir.py` is new (not in spec's repo layout): a
  Playwright-driven search of the real GO repository, started once at
  FastAPI startup and reused across requests. See its docstring for why
  `app/government/search.py`'s original plain-HTTP approach couldn't work.

## Design

The UI direction is a household ledger/register — Dad is a government
employee, and the product's job (remembering, confirming, tracking cases)
maps onto a ledger page rather than a SaaS dashboard. See
`apps/web/src/index.css` for the token rationale.
