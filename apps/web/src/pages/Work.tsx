import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { CaseOut, EmailDraft } from "../types/api";

export function Work() {
  const [cases, setCases] = useState<CaseOut[]>([]);
  const [draft, setDraft] = useState<EmailDraft | null>(null);
  const [form, setForm] = useState({ to_addr: "", subject: "", body: "" });
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { api.cases().then(setCases).catch(() => {}); }, []);

  const createDraft = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const d = await api.createDraft(form.to_addr, form.subject, form.body);
      setDraft(d);
      setSent(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create the draft.");
    }
  };

  const send = async () => {
    if (!draft) return;
    await api.sendDraft(draft.id);
    setSent(true);
  };

  return (
    <div>
      <h1 className="font-display text-2xl mb-4">Payments and work</h1>

      <h2 className="font-display text-lg mb-2">Pending cases</h2>
      <div className="ledger mb-8">
        {cases.length === 0 && <p className="py-4 text-[var(--ink-soft)]">Nothing on file.</p>}
        {cases.map((c) => (
          <div key={c.id} className="ledger-row py-3 flex justify-between">
            <span className="text-lg">{c.title}</span>
            <span className="text-base text-[var(--ink-soft)]">{c.status.replace(/_/g, " ").toLowerCase()}</span>
          </div>
        ))}
      </div>

      <h2 className="font-display text-lg mb-2">Draft an email</h2>
      {sent && draft ? (
        <div className="ledger mb-8">
          <div className="ledger-row py-4 text-[var(--stamp)] text-lg font-medium">
            ✓ Sent to {draft.to_addr}
          </div>
          <div className="py-4">
            <button
              onClick={() => { setDraft(null); setSent(false); setForm({ to_addr: "", subject: "", body: "" }); }}
              className="rounded-full border border-[var(--ink-soft)] px-5 py-2 text-lg"
            >
              Write another
            </button>
          </div>
        </div>
      ) : draft ? (
        <div className="ledger mb-8">
          <div className="ledger-row py-3"><strong>To:</strong> {draft.to_addr}</div>
          <div className="ledger-row py-3"><strong>Subject:</strong> {draft.subject}</div>
          <div className="ledger-row py-4 whitespace-pre-line">{draft.body}</div>
          <div className="py-4 flex gap-3">
            <button onClick={() => setDraft(null)} className="rounded-full border border-[var(--ink-soft)] px-5 py-2 text-lg">
              Edit
            </button>
            <button onClick={send} className="rounded-full bg-[var(--stamp)] text-[var(--paper)] px-5 py-2 text-lg font-medium">
              Send
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={createDraft} className="space-y-3 mb-8">
          <input
            required placeholder="To (email address)"
            value={form.to_addr} onChange={(e) => setForm({ ...form, to_addr: e.target.value })}
            className="w-full rounded-xl border border-[var(--paper-line)] bg-transparent px-4 py-3 text-lg"
          />
          <input
            required placeholder="Subject"
            value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })}
            className="w-full rounded-xl border border-[var(--paper-line)] bg-transparent px-4 py-3 text-lg"
          />
          <textarea
            required placeholder="What should the email say?" rows={5}
            value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })}
            className="w-full rounded-xl border border-[var(--paper-line)] bg-transparent px-4 py-3 text-lg"
          />
          <button type="submit" className="rounded-xl bg-[var(--ink)] text-[var(--paper)] px-6 py-3 text-lg font-medium">
            Create draft
          </button>
          {error && <p className="text-[var(--margin)]">{error}</p>}
        </form>
      )}
    </div>
  );
}
