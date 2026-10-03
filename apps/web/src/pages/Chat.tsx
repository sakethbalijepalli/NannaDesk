import { useEffect, useRef, useState } from "react";
import { MicButton } from "../components/MicButton";
import { api } from "../lib/api";
import type { Action, Source } from "../types/api";

interface Turn {
  who: "dad" | "nannadesk";
  text: string;
  sources?: Source[];
  actions?: Action[];
}

export function Chat({ pendingMessage, onConsumed }: { pendingMessage: string | null; onConsumed: () => void }) {
  const [turns, setTurns] = useState<Turn[]>([
    { who: "nannadesk", text: "What's on your mind? You can type, or hold the mic and talk." },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const send = async (text: string) => {
    if (!text.trim()) return;
    setTurns((t) => [...t, { who: "dad", text }]);
    setInput("");
    setSending(true);
    try {
      const res = await api.chat(text);
      setTurns((t) => [...t, { who: "nannadesk", text: res.message, sources: res.sources, actions: res.actions }]);
    } catch {
      setTurns((t) => [...t, { who: "nannadesk", text: "I couldn't reach the backend just now." }]);
    } finally {
      setSending(false);
    }
  };

  const consumedRef = useRef<string | null>(null);
  useEffect(() => {
    // Guards against React StrictMode's double-invoke of effects in dev,
    // which previously sent a voice message from Home twice.
    if (pendingMessage && consumedRef.current !== pendingMessage) {
      consumedRef.current = pendingMessage;
      send(pendingMessage);
      onConsumed();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingMessage]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  const addTurn = (turn: Turn) => setTurns((t) => [...t, turn]);

  return (
    <div className="flex flex-col h-[70vh]">
      <h1 className="font-display text-2xl mb-4">Ask me anything</h1>
      <div className="flex-1 overflow-y-auto ledger pr-2">
        {turns.map((t, i) => (
          <div key={i} className="ledger-row py-4">
            <div className="flex items-center justify-between gap-2 mb-1">
              <p className="text-sm uppercase tracking-wide text-[var(--ink-soft)]">
                {t.who === "dad" ? "You" : "NannaDesk"}
              </p>
              {t.who === "nannadesk" && <SpeakButton text={t.text} />}
            </div>
            <p className="text-lg whitespace-pre-line">{t.text}</p>
            {t.sources && t.sources.length > 0 && (
              <ul className="mt-2 text-base text-[var(--ink-soft)]">
                {t.sources.map((s, si) => (
                  <li key={si}>
                    {s.official ? "✅ Official source: " : "Source: "}
                    {s.url ? <a className="underline" href={s.url} target="_blank" rel="noreferrer">{s.title}</a> : s.title}
                    {s.date && ` — retrieved ${new Date(s.date).toLocaleString()}`}
                  </li>
                ))}
              </ul>
            )}
            {t.actions?.map((a, ai) => (
              <TurnAction key={ai} action={a} onFollowUp={send} onNote={addTurn} />
            ))}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); send(input); }}
        className="mt-4 flex gap-2 items-stretch"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a question…"
          className="flex-1 rounded-xl border border-[var(--paper-line)] bg-transparent px-4 py-3 text-lg"
        />
        <button
          type="submit"
          disabled={sending}
          className="rounded-xl bg-[var(--ink)] text-[var(--paper)] px-6 py-3 text-lg font-medium"
        >
          Send
        </button>
      </form>
      <div className="mt-3">
        <MicButton onTranscript={send} />
      </div>
    </div>
  );
}

/** Renders the one interactive follow-up a chat response calls for, so a
 * conversational offer ("which one?", "want a draft?", a created draft)
 * is something Dad can actually act on inline, not just read.
 */
function TurnAction({
  action, onFollowUp, onNote,
}: { action: Action; onFollowUp: (text: string) => void; onNote: (turn: Turn) => void }) {
  if (action.type === "EMAIL_DRAFT_CREATED") {
    return <DraftCard draftId={action.payload.id as number} />;
  }

  if (action.type === "CHOOSE_MEDICATION") {
    return <ChooseMedication options={action.payload.options as { event_id: number; name: string }[]} onNote={onNote} />;
  }

  if (action.type === "OFFER_FOLLOWUP_DRAFT") {
    const caseTitle = action.payload.case_title as string;
    return (
      <div className="mt-3">
        <button
          onClick={() => onFollowUp(`Write a follow-up email about ${caseTitle}`)}
          className="rounded-full border border-[var(--ink-soft)] px-4 py-2 text-base"
        >
          Draft a follow-up
        </button>
      </div>
    );
  }

  return null;
}

function ChooseMedication({
  options, onNote,
}: { options: { event_id: number; name: string }[]; onNote: (turn: Turn) => void }) {
  const [chosen, setChosen] = useState<number | null>(null);

  // Once picked, the buttons disappear — the confirmation itself is the
  // new chat turn `onNote` adds below, so there's nothing left to click.
  // Not `if (chosen)` — SQLite rowids start at 1 in practice, but an
  // event_id of 0 would be falsy and leave the buttons visible after a
  // pick (code review caught this).
  if (chosen !== null) return null;

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {options.map((o) => (
        <button
          key={o.event_id}
          onClick={async () => {
            setChosen(o.event_id);
            await api.confirmEvent(o.event_id, "TAKEN");
            onNote({ who: "nannadesk", text: `Got it — ${o.name} confirmed.` });
          }}
          className="rounded-full bg-[var(--stamp)] text-[var(--paper)] px-4 py-2 text-base font-medium"
        >
          {o.name}
        </button>
      ))}
    </div>
  );
}

function DraftCard({ draftId }: { draftId: number }) {
  const [draft, setDraft] = useState<{ to_addr: string; subject: string; body: string; status: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getDraft(draftId).then(setDraft).catch(() => setError("Couldn't load the draft."));
  }, [draftId]);

  if (error && !draft) return <p className="mt-3 text-[var(--margin)]">{error}</p>;
  if (!draft) return <p className="mt-3 text-[var(--ink-soft)]">Loading draft…</p>;

  const send = async () => {
    setError(null);
    try {
      await api.sendDraft(draftId);
      setDraft({ ...draft, status: "SENT" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't send — try reopening this draft.");
    }
  };

  return (
    <div className="mt-3 rounded-xl border border-[var(--paper-line)] p-4">
      <p className="text-base"><strong>To:</strong> {draft.to_addr}</p>
      <p className="text-base mb-2"><strong>Subject:</strong> {draft.subject}</p>
      <p className="text-base whitespace-pre-line mb-3">{draft.body}</p>
      {draft.status === "SENT" ? (
        <p className="text-[var(--stamp)] font-medium">✓ Sent</p>
      ) : (
        <>
          <button onClick={send} className="rounded-full bg-[var(--stamp)] text-[var(--paper)] px-5 py-2 text-base font-medium">
            Send
          </button>
          {error && <p className="mt-2 text-[var(--margin)]">{error}</p>}
        </>
      )}
    </div>
  );
}

/** Reads a NannaDesk reply aloud via ElevenLabs — on demand (tap to hear),
 * never automatic. Fails silently to a one-line note if voice output
 * isn't configured: the text answer is already on screen either way, so
 * this is a pure enhancement, never a blocker.
 */
function SpeakButton({ text }: { text: string }) {
  const [state, setState] = useState<"idle" | "loading" | "unavailable">("idle");
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const play = async () => {
    if (state === "loading") return;
    setState("loading");
    try {
      const blob = await api.speak(text);
      const url = URL.createObjectURL(blob);
      audioRef.current?.pause();
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => URL.revokeObjectURL(url);
      await audio.play();
      setState("idle");
    } catch {
      setState("unavailable");
    }
  };

  if (state === "unavailable") {
    return <span className="text-sm text-[var(--ink-soft)]">voice output not set up</span>;
  }

  return (
    <button
      onClick={play}
      disabled={state === "loading"}
      aria-label="Read this reply aloud"
      className="text-xl leading-none text-[var(--ink-soft)] hover:text-[var(--ink)] disabled:opacity-50"
    >
      {state === "loading" ? "…" : "🔊"}
    </button>
  );
}
