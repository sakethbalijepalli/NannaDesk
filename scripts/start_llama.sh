#!/usr/bin/env bash
# Starts the local Qwen3.5-0.8B model behind llama.cpp's OpenAI-compatible
# server, matching app/config.py's default NANNADESK_LLM_BASE_URL
# (http://127.0.0.1:8080). See spec §10.2.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODEL_PATH="$REPO_ROOT/models/qwen/Qwen3.5-0.8B-Q4_K_M.gguf"

if ! command -v llama-server >/dev/null 2>&1; then
    echo "llama-server not found. Install with: brew install llama.cpp" >&2
    exit 1
fi

if [ ! -f "$MODEL_PATH" ]; then
    echo "Model not found at $MODEL_PATH" >&2
    echo "Download it with:" >&2
    echo "  curl -L -o '$MODEL_PATH' https://huggingface.co/unsloth/Qwen3.5-0.8B-GGUF/resolve/main/Qwen3.5-0.8B-Q4_K_M.gguf" >&2
    exit 1
fi

echo "Starting llama-server on http://127.0.0.1:8080 ..."
# --reasoning-budget caps Qwen3.5's <think> trace. Without it, this small
# model can ramble for tens of thousands of tokens before answering a
# one-line question (observed during development) — harmless but slow and
# a bad fit for a reminder/report app that needs snappy phrasing.
exec llama-server -m "$MODEL_PATH" --port 8080 --reasoning-budget 128
