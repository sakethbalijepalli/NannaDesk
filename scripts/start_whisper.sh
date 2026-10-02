#!/usr/bin/env bash
# Checks the whisper.cpp install and model used by /api/voice/transcribe.
#
# The transcribe endpoint (app/api/voice.py) shells out to `whisper-cli`
# per request rather than running a persistent server — simpler, and fine
# for push-to-talk latency on a short recording. This script just verifies
# the pieces are in place; there's no long-running whisper process to start.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODEL_PATH="$REPO_ROOT/models/whisper/ggml-small.bin"

ok=true
for bin in whisper-cli ffmpeg; do
    if ! command -v "$bin" >/dev/null 2>&1; then
        echo "$bin not found. Install with: brew install whisper-cpp ffmpeg" >&2
        ok=false
    fi
done

if [ ! -f "$MODEL_PATH" ]; then
    echo "Whisper model not found at $MODEL_PATH" >&2
    echo "Download it with:" >&2
    echo "  curl -L -o '$MODEL_PATH' https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin" >&2
    ok=false
fi

if [ "$ok" = true ]; then
    echo "whisper-cli, ffmpeg, and the model are all present. Voice transcription is ready."
fi
