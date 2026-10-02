import type {
  CaseOut, ChatResponse, EmailDraft, GovernmentAnswer, ReportExplainResponse, TodayResponse,
} from "../types/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export const api = {
  chat: (message: string) =>
    request<ChatResponse>("/chat", { method: "POST", body: JSON.stringify({ message }) }),

  today: () => request<TodayResponse>("/reminders/today"),

  confirmEvent: (eventId: number, outcome: "TAKEN" | "SKIPPED" | "CONFIRMED") =>
    request(`/reminders/${eventId}/confirm`, { method: "POST", body: JSON.stringify({ outcome }) }),

  snoozeEvent: (eventId: number, minutes = 15) =>
    request(`/reminders/${eventId}/snooze`, { method: "POST", body: JSON.stringify({ minutes }) }),

  cases: () => request<CaseOut[]>("/cases"),

  getDraft: (draftId: number) => request<EmailDraft>(`/emails/${draftId}`),

  createDraft: (to_addr: string, subject: string, body: string, case_id?: number) =>
    request<EmailDraft>("/emails/draft", {
      method: "POST", body: JSON.stringify({ to_addr, subject, body, case_id }),
    }),

  sendDraft: (draftId: number) =>
    request<{ id: number; status: string }>(`/emails/${draftId}/send`, {
      method: "POST", body: JSON.stringify({ confirm: true }),
    }),

  uploadDocument: async (file: File, docType: "LAB_REPORT" | "OFFICE" | "GOVERNMENT" | "OTHER") => {
    const form = new FormData();
    form.append("file", file);
    form.append("doc_type", docType);
    const res = await fetch("/api/documents", { method: "POST", body: form });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ id: number; lab_results_extracted: number }>;
  },

  explainReport: (documentId: number) =>
    request<ReportExplainResponse>(`/reports/${documentId}/explain`, { method: "POST" }),

  governmentSearch: (query: string) =>
    request<GovernmentAnswer>("/government/search", { method: "POST", body: JSON.stringify({ query }) }),

  transcribe: async (audio: Blob) => {
    const form = new FormData();
    form.append("file", audio, "recording.webm");
    const res = await fetch("/api/voice/transcribe", { method: "POST", body: form });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ transcript: string }>;
  },
};
