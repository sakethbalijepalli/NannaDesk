import { useVoiceRecorder } from "../hooks/useVoiceRecorder";

/** The hero action (spec §2.1, §2.3): big, unambiguous, hold-to-speak. */
export function MicButton({ onTranscript }: { onTranscript: (text: string) => void }) {
  const { recording, transcribing, error, start, stop } = useVoiceRecorder(onTranscript);

  return (
    <div>
      <button
        onPointerDown={start}
        onPointerUp={stop}
        onPointerLeave={() => recording && stop()}
        disabled={transcribing}
        aria-pressed={recording}
        className={`w-full rounded-2xl border-2 py-7 text-xl font-medium font-display transition-all select-none
          ${recording
            ? "bg-[var(--margin)] border-[var(--margin)] text-[var(--paper)] scale-[0.99]"
            : "bg-[var(--ink)] border-[var(--ink)] text-[var(--paper)] hover:opacity-90"}`}
      >
        {transcribing ? "Listening back…" : recording ? "Release to send" : "🎤  Hold to talk"}
      </button>
      {error && <p className="mt-3 text-base text-[var(--margin)]">{error}</p>}
    </div>
  );
}
