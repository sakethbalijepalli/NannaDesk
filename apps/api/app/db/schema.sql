-- NannaDesk schema. SQLite. See docs/agents/domain.md for the glossary this maps to.

PRAGMA foreign_keys = ON;

-- ==========================================================================
-- Structured memory: profile, medications, schedules
-- ==========================================================================

CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    preferred_language TEXT DEFAULT 'en', -- 'en' | 'te' | 'te-en'
    department TEXT,
    designation TEXT,
    office TEXT,
    employee_code TEXT,
    ddo_name TEXT,
    ddo_email TEXT,
    signature TEXT,
    family_escalation_enabled INTEGER DEFAULT 0,
    family_contact_name TEXT,
    family_contact_email TEXT
);

CREATE TABLE IF NOT EXISTS medications (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    instructions TEXT,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS medication_schedules (
    id INTEGER PRIMARY KEY,
    medication_id INTEGER NOT NULL,
    time TEXT NOT NULL,                 -- 'HH:MM', 24h
    meal_dependency TEXT,               -- 'breakfast' | 'lunch' | 'dinner' | NULL
    repeat_minutes INTEGER DEFAULT 30,  -- re-reminder cadence while unconfirmed
    max_followups INTEGER DEFAULT 2,
    FOREIGN KEY (medication_id) REFERENCES medications(id)
);

-- ==========================================================================
-- Event memory: meal + medication confirmations, one row per (date, slot)
-- ==========================================================================

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    event_date TEXT NOT NULL,           -- 'YYYY-MM-DD', local day this event belongs to
    kind TEXT NOT NULL CHECK (kind IN ('MEAL', 'MEDICATION')),
    meal_type TEXT,                     -- 'breakfast' | 'lunch' | 'dinner' (kind = MEAL)
    medication_schedule_id INTEGER,     -- FK (kind = MEDICATION)
    status TEXT NOT NULL CHECK (status IN (
        'SCHEDULED', 'REMINDER_SENT', 'TAKEN', 'SNOOZED',
        'NOT_CONFIRMED', 'SKIPPED', 'UNKNOWN', 'CONFIRMED'
    )),
    followup_count INTEGER DEFAULT 0,
    confirmed_at DATETIME,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (medication_schedule_id) REFERENCES medication_schedules(id)
);

CREATE INDEX IF NOT EXISTS idx_events_date_kind ON events(event_date, kind);

-- ==========================================================================
-- Reminders (deterministic scheduler state, survives restarts)
-- ==========================================================================

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY,
    event_id INTEGER,
    kind TEXT NOT NULL,                 -- 'MEDICATION' | 'MEAL' | 'FOLLOW_UP' | 'CUSTOM'
    label TEXT,
    due_at DATETIME NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'SENT', 'CANCELLED')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id)
);

CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(due_at, status);

-- ==========================================================================
-- Cases and email (office/admin workflows)
-- ==========================================================================

CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,                 -- 'PF' | 'PRC' | 'GENERAL' ...
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN (
        'OPEN', 'WAITING_FOR_REPLY', 'FOLLOW_UP_DUE', 'RESOLVED'
    )),
    follow_up_due_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS case_messages (
    id INTEGER PRIMARY KEY,
    case_id INTEGER,
    provider TEXT,                      -- 'mock' | 'outlook'
    provider_message_id TEXT,
    direction TEXT CHECK (direction IN ('OUTBOUND', 'INBOUND')),
    subject TEXT,
    body TEXT,
    sent_at DATETIME,
    FOREIGN KEY (case_id) REFERENCES cases(id)
);

CREATE TABLE IF NOT EXISTS email_drafts (
    id INTEGER PRIMARY KEY,
    case_id INTEGER,
    to_addr TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'SENT')),
    provider TEXT NOT NULL DEFAULT 'mock',
    provider_message_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    sent_at DATETIME,
    FOREIGN KEY (case_id) REFERENCES cases(id)
);

-- ==========================================================================
-- Documents and lab results (document memory)
-- ==========================================================================

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    doc_type TEXT NOT NULL CHECK (doc_type IN ('LAB_REPORT', 'OFFICE', 'GOVERNMENT', 'OTHER')),
    path TEXT NOT NULL,
    page_count INTEGER,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lab_results (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL,
    test TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    reference_low REAL,
    reference_high REAL,
    flag TEXT NOT NULL CHECK (flag IN ('LOW', 'NORMAL', 'HIGH')),
    source_page INTEGER,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

-- Personal document full-text index. Kept separate from government_fts
-- (see 8.1 in the spec) so a medical question can never retrieve government
-- web content by accident, and vice versa.
CREATE VIRTUAL TABLE IF NOT EXISTS personal_fts USING fts5(
    content,
    document_id UNINDEXED,
    page UNINDEXED,
    doc_type UNINDEXED
);

-- Cache of retrieved official government pages, for the current session /
-- demo replay. Never used as a source of truth for "latest" questions
-- without a fresh fetch — see app/government/search.py.
CREATE VIRTUAL TABLE IF NOT EXISTS government_fts USING fts5(
    content,
    source_url UNINDEXED,
    title UNINDEXED,
    department UNINDEXED,
    pub_date UNINDEXED,
    retrieved_at UNINDEXED
);

-- ==========================================================================
-- Audit trail — metadata only. Never write report text, email bodies,
-- employee identifiers, or medication details here.
-- ==========================================================================

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY,
    event_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
