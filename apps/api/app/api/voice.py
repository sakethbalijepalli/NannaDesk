"""POST /api/voice/transcribe (spec §2.3, §15): browser audio -> local,
offline transcript. MediaRecorder produces webm/opus; whisper.cpp wants
16 kHz mono WAV, so ffmpeg does the conversion server-side before whisper-cli
runs. Both steps are local subprocesses — no audio ever leaves the machine.
"""
import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import PROJECT_ROOT

router = APIRouter()

WHISPER_MODEL = PROJECT_ROOT / "models" / "whisper" / "ggml-small.bin"


def _transcribe_sync(input_path: Path) -> str:
    if not shutil.which("ffmpeg") or not shutil.which("whisper-cli"):
        raise RuntimeError("ffmpeg and whisper-cli must be installed (see scripts/start_whisper.sh)")
    if not WHISPER_MODEL.exists():
        raise RuntimeError(f"Whisper model not found at {WHISPER_MODEL}")

    wav_path = input_path.with_suffix(".wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(input_path), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(wav_path)],
        check=True, capture_output=True,
    )

    result = subprocess.run(
        ["whisper-cli", "-m", str(WHISPER_MODEL), "-l", "auto", "-np", "-nt", "-f", str(wav_path)],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


@router.post("/voice/transcribe")
async def transcribe(file: UploadFile = File(...)) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        input_path = Path(tmp) / (file.filename or "audio.webm")
        input_path.write_bytes(await file.read())
        try:
            text = await asyncio.to_thread(_transcribe_sync, input_path)
        except subprocess.CalledProcessError as exc:
            raise HTTPException(status_code=500, detail=f"Transcription failed: {exc.stderr}") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"transcript": text}
