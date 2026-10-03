import type {
  CaseOut, ChatResponse, EmailDraft, GovernmentAnswer, Medication, MedicationScheduleIn,
  Profile, ReportExplainResponse, TodayResponse,
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

  // ElevenLabs text-to-speech, on demand (not automatic — Dad taps to
  // hear a reply read aloud). 503 means it isn't configured; callers
  // should fail quietly, same as any other optional feature here.
  speak: async (text: string): Promise<Blob> => {
    const res = await fetch("/api/voice/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.blob();
  },

  getProfile: () => request<Profile | null>("/profile"),

  putProfile: (profile: Profile) =>
    request<Profile>("/profile", { method: "PUT", body: JSON.stringify(profile) }),

  listMedications: () => request<Medication[]>("/medications"),

  createMedication: (name: string, instructions: string | null, schedule: MedicationScheduleIn) =>
    request<Medication>("/medications", {
      method: "POST", body: JSON.stringify({ name, instructions, schedule }),
    }),

  updateMedication: (id: number, name: string, instructions: string | null, schedule: MedicationScheduleIn) =>
    request<Medication>(`/medications/${id}`, {
      method: "PUT", body: JSON.stringify({ name, instructions, schedule }),
    }),

  deactivateMedication: (id: number) =>
    request<{ id: number; active: boolean }>(`/medications/${id}`, { method: "DELETE" }),
};
