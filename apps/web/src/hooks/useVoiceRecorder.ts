import { useCallback, useRef, useState } from "react";
import { api } from "../lib/api";

/** Push-to-talk recording (spec §2.3). Hold to speak, release to transcribe
 * via the local whisper.cpp pipeline on the server — nothing leaves the
 * machine as a hosted API call.
 */
export function useVoiceRecorder(onTranscript: (text: string) => void) {
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  // getUserMedia is async, so a quick tap can call stop() before the
  // recorder exists — remembered here so start() stops it immediately
  // once it's actually ready, instead of leaving the mic open.
  const stopRequestedRef = useRef(false);

  const finish = useCallback((recorder: MediaRecorder) => {
    setRecording(false);
    setTranscribing(true);
    recorder.addEventListener("stop", async () => {
      recorder.stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      try {
        const { transcript } = await api.transcribe(blob);
        if (transcript) onTranscript(transcript);
        else setError("I couldn't make out any words — try again a little closer to the mic.");
      } catch {
        setError("Transcription isn't available right now (is whisper.cpp set up?).");
      } finally {
        setTranscribing(false);
      }
    });
    recorder.stop();
  }, [onTranscript]);

  const start = useCallback(async () => {
    setError(null);
    stopRequestedRef.current = false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => chunksRef.current.push(e.data);
      recorder.start();
      recorderRef.current = recorder;

      if (stopRequestedRef.current) {
        finish(recorder);
      } else {
        setRecording(true);
      }
    } catch {
      setError("Couldn't access the microphone. Check your browser's microphone permission.");
    }
  }, [finish]);

  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    if (!recorder) {
      // start() is still awaiting getUserMedia — finish as soon as it lands.
      stopRequestedRef.current = true;
      return;
    }
    finish(recorder);
    recorderRef.current = null;
  }, [finish]);

  return { recording, transcribing, error, start, stop };
}
