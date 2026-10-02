# AGENTS.md

This file provides guidance to AI coding agents working in this repository.

## Agent skills

### Issue tracker

Issues and specs live as local markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default triage label vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Run

See `README.md` for prerequisites and model downloads. Quick reference:

```bash
./scripts/start_llama.sh                              # LLM, :8080
source apps/api/.venv/bin/activate && cd apps/api && uvicorn app.main:app --port 8000   # backend
cd apps/web && npm run dev                             # frontend, :5173
```

Python venv is at `apps/api/.venv`, built with **Python 3.13** (not 3.14 —
`pydantic-core` has no 3.14 wheels yet). Tests: `python -m pytest -q` from
the repo root (needs the venv activated).

Reseed demo data: `python scripts/seed_demo_data.py --reset`.
