export type EventStatus =
  | "SCHEDULED" | "REMINDER_SENT" | "TAKEN" | "SNOOZED"
  | "NOT_CONFIRMED" | "SKIPPED" | "UNKNOWN" | "CONFIRMED";

export interface TodayItem {
  event_id: number | null;
  kind: "MEAL" | "MEDICATION";
  label: string;
  status: EventStatus;
  due_time: string | null;
}

export interface TodayResponse {
  date: string;
  items: TodayItem[];
}

export interface Source {
  title: string;
  date: string | null;
  url: string | null;
  official: boolean;
}

export interface Action {
  type: string;
  payload: Record<string, unknown>;
}

export interface ChatResponse {
  type: "answer" | "needs_confirmation" | "error";
  message: string;
  sources: Source[];
  actions: Action[];
}

export interface CaseOut {
  id: number;
  type: string;
  title: string;
  status: string;
  follow_up_due_at: string | null;
  updated_at: string;
}

export interface EmailDraft {
  id: number;
  case_id: number | null;
  to_addr: string;
  subject: string;
  body: string;
  status: "DRAFT" | "SENT";
}

export interface LabResult {
  test: string;
  value: number;
  unit: string | null;
  reference_low: number | null;
  reference_high: number | null;
  flag: "LOW" | "NORMAL" | "HIGH";
  source_page: number | null;
}

export interface ReportExplainResponse {
  what_it_says: string[];
  what_it_may_mean: string;
  what_changed: string[];
  questions_for_doctor: string[];
  when_to_seek_help: string[];
  results: LabResult[];
}

export interface GovernmentAnswer {
  answer: string;
  sources: Source[];
}
