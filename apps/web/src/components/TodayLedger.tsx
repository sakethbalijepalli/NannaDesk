import type { TodayItem } from "../types/api";

const DONE_STATUSES = new Set(["TAKEN", "CONFIRMED"]);
const WAITING_STATUSES = new Set(["SCHEDULED", "REMINDER_SENT", "SNOOZED"]);

function Glyph({ status }: { status: TodayItem["status"] }) {
  if (DONE_STATUSES.has(status)) {
    return (
      <span
        className="inline-block animate-stamp text-[var(--stamp)] text-2xl font-display -rotate-6"
        aria-label="Confirmed"
      >
        ✓
      </span>
    );
  }
  if (status === "NOT_CONFIRMED" || status === "SKIPPED") {
    return <span className="text-[var(--margin)] text-xl" aria-label="Not confirmed">●</span>;
  }
  if (WAITING_STATUSES.has(status)) {
    return <span className="text-[var(--gold)] text-xl" aria-label="Waiting">○</span>;
  }
  return <span className="text-[var(--ink-soft)] text-xl" aria-label="Unknown">?</span>;
}

export function TodayLedger({
  items, onConfirm, onSnooze,
}: {
  items: TodayItem[];
  onConfirm: (eventId: number, outcome: "TAKEN" | "SKIPPED" | "CONFIRMED") => void;
  onSnooze: (eventId: number) => void;
}) {
  return (
    <div className="ledger">
      {items.map((item, i) => {
        const canAct = item.event_id != null && !DONE_STATUSES.has(item.status) && item.status !== "SKIPPED";
        const outcome = item.kind === "MEAL" ? "CONFIRMED" : "TAKEN";
        return (
          <div
            // event_id, not kind+label — two schedules for the same
            // medicine (e.g. twice daily) would otherwise collide and
            // React could bind a button to the wrong row after a
            // re-render (code review caught this).
            key={item.event_id ?? `${item.kind}-${item.label}-${i}`}
            className="ledger-row py-4 flex items-center justify-between gap-4 animate-write-in"
            style={{ animationDelay: `${i * 60}ms` }}
          >
            <div className="flex items-center gap-4">
              <Glyph status={item.status} />
              <div>
                <p className="text-lg">{item.label}</p>
                {item.due_time && <p className="text-base text-[var(--ink-soft)]">{item.due_time}</p>}
              </div>
            </div>
            {canAct && (
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={() => onConfirm(item.event_id!, outcome)}
                  className="rounded-full bg-[var(--stamp)] text-[var(--paper)] px-4 py-2 text-base font-medium"
                >
                  {item.kind === "MEAL" ? "Had it" : "Taken"}
                </button>
                {item.kind === "MEDICATION" && (
                  <button
                    onClick={() => onSnooze(item.event_id!)}
                    className="rounded-full border border-[var(--ink-soft)] px-4 py-2 text-base"
                  >
                    Snooze
                  </button>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
