import { useState } from "react";
import { api } from "../lib/api";
import type { ReportExplainResponse } from "../types/api";

const FLAG_COLOR: Record<string, string> = {
  LOW: "text-[var(--margin)]", HIGH: "text-[var(--margin)]", NORMAL: "text-[var(--stamp)]",
};

export function Reports() {
  const [docType, setDocType] = useState<"LAB_REPORT" | "OFFICE" | "GOVERNMENT">("LAB_REPORT");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [explanation, setExplanation] = useState<ReportExplainResponse | null>(null);

  const handleFile = async (file: File) => {
    setBusy(true); setError(null); setExplanation(null);
    try {
      const uploaded = await api.uploadDocument(file, docType);
      if (docType === "LAB_REPORT") {
        if (uploaded.lab_results_extracted === 0) {
          setError("I couldn't find any lab values in a format I recognize in this PDF.");
        } else {
          const result = await api.explainReport(uploaded.id);
          setExplanation(result);
        }
      } else {
        setError(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong reading that file.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h1 className="font-display text-2xl mb-4">Explain a document</h1>

      <div className="flex gap-3 mb-4">
        {(["LAB_REPORT", "OFFICE", "GOVERNMENT"] as const).map((dt) => (
          <button
            key={dt}
            onClick={() => setDocType(dt)}
            className={`rounded-full px-4 py-2 text-base ${docType === dt ? "bg-[var(--ink)] text-[var(--paper)]" : "border border-[var(--paper-line)]"}`}
          >
            {dt === "LAB_REPORT" ? "Blood report" : dt === "OFFICE" ? "Office memo" : "Government order"}
          </button>
        ))}
      </div>

      <label className="block rounded-xl border-2 border-dashed border-[var(--paper-line)] p-8 text-center cursor-pointer mb-6">
        <input
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        <span className="text-lg">{busy ? "Reading the document…" : "Tap to choose a PDF"}</span>
      </label>

      {error && <p className="text-[var(--margin)] mb-4">{error}</p>}

      {explanation && (
        <div className="ledger">
          <Section title="What the report says">
            <ul className="space-y-1">
              {explanation.results.map((r) => (
                <li key={r.test} className={FLAG_COLOR[r.flag]}>
                  {r.test}: {r.value} {r.unit} — {r.flag}
                </li>
              ))}
            </ul>
          </Section>
          <Section title="What it may mean"><p>{explanation.what_it_may_mean}</p></Section>
          <Section title="What changed">
            <ul className="space-y-1">{explanation.what_changed.map((c, i) => <li key={i}>{c}</li>)}</ul>
          </Section>
          <Section title="Questions for your doctor">
            <ul className="list-disc pl-5 space-y-1">{explanation.questions_for_doctor.map((q, i) => <li key={i}>{q}</li>)}</ul>
          </Section>
          {explanation.when_to_seek_help.length > 0 && (
            <Section title="When to seek help">
              <ul className="list-disc pl-5 space-y-1 text-[var(--margin)]">
                {explanation.when_to_seek_help.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </Section>
          )}
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="ledger-row py-4">
      <h2 className="font-display text-lg mb-2">{title}</h2>
      <div className="text-lg">{children}</div>
    </div>
  );
}
