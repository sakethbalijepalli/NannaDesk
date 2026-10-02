import { useEffect, useRef, useState } from "react";
import { MicButton } from "../components/MicButton";
import { TodayLedger } from "../components/TodayLedger";
import { api } from "../lib/api";
import type { TodayResponse } from "../types/api";
import type { Tab } from "../components/NavTabs";

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

export function Home({ onNavigate, onAsk }: { onNavigate: (t: Tab) => void; onAsk: (text: string) => void }) {
  const [today, setToday] = useState<TodayResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const todayRef = useRef<HTMLHeadingElement>(null);

  const refresh = () => {
    api.today().then(setToday).catch(() => setError("Couldn't load today's list. Is the backend running?"));
  };

  useEffect(refresh, []);

  const handleConfirm = async (eventId: number, outcome: "TAKEN" | "SKIPPED" | "CONFIRMED") => {
    await api.confirmEvent(eventId, outcome);
    refresh();
  };
  const handleSnooze = async (eventId: number) => {
    await api.snoozeEvent(eventId, 15);
    refresh();
  };

  return (
    <div>
      <h1 className="font-display text-2xl mb-1">{greeting()}, Nanna 👋</h1>
      <p className="text-[var(--ink-soft)] mb-8">What would you like to do?</p>

      <div className="mb-6">
        <MicButton onTranscript={onAsk} />
      </div>

      <div className="grid grid-cols-2 gap-3 mb-10">
        <QuickAction label="Draft an email" emoji="✉️" onClick={() => onNavigate("work")} />
        <QuickAction label="Explain a document" emoji="📄" onClick={() => onNavigate("documents")} />
        <QuickAction label="Payments and PF" emoji="💰" onClick={() => onNavigate("work")} />
        <QuickAction
          label="Reminders"
          emoji="🔔"
          onClick={() => todayRef.current?.scrollIntoView({ behavior: "smooth" })}
        />
      </div>

      <h2 ref={todayRef} className="font-display text-xl mb-3">Today</h2>
      {error && <p className="text-[var(--margin)]">{error}</p>}
      {today && <TodayLedger items={today.items} onConfirm={handleConfirm} onSnooze={handleSnooze} />}
    </div>
  );
}

function QuickAction({ label, emoji, onClick }: { label: string; emoji: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="rounded-xl border border-[var(--paper-line)] bg-transparent py-5 px-4 text-left hover:bg-[var(--paper-line)]/40 transition-colors"
    >
      <span className="text-2xl block mb-1" aria-hidden>{emoji}</span>
      <span className="text-lg">{label}</span>
    </button>
  );
}
