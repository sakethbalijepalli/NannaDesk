export type Tab = "home" | "ask" | "documents" | "work" | "settings";

const TABS: { id: Tab; label: string }[] = [
  { id: "home", label: "Home" },
  { id: "ask", label: "Ask" },
  { id: "documents", label: "Documents" },
  { id: "work", label: "Payments & work" },
  { id: "settings", label: "Settings" },
];

export function NavTabs({ active, onChange }: { active: Tab; onChange: (t: Tab) => void }) {
  return (
    <nav className="flex gap-1 sm:gap-2 mb-8 flex-wrap" aria-label="Sections">
      {TABS.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          aria-current={active === t.id ? "page" : undefined}
          className={`rounded-full px-5 py-3 text-lg font-medium transition-colors ${
            active === t.id
              ? "bg-[var(--ink)] text-[var(--paper)]"
              : "bg-transparent text-[var(--ink-soft)] hover:bg-[var(--paper-line)]"
          }`}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );
}
