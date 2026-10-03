import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Medication, MedicationScheduleIn, Profile } from "../types/api";

const EMPTY_PROFILE: Profile = {
  name: "", preferred_language: "en", department: null, designation: null, office: null,
  employee_code: null, ddo_name: null, ddo_email: null, signature: null,
  family_escalation_enabled: false, family_contact_name: null, family_contact_email: null,
};

export function Settings() {
  return (
    <div>
      <h1 className="font-display text-2xl mb-1">Settings</h1>
      <p className="text-[var(--ink-soft)] mb-8">
        This is where you set up whose desk this is — Dad's real details, not demo data.
      </p>
      <ProfileSection />
      <div className="h-10" />
      <MedicationsSection />
    </div>
  );
}

function ProfileSection() {
  const [profile, setProfile] = useState<Profile>(EMPTY_PROFILE);
  const [loaded, setLoaded] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getProfile().then((p) => { if (p) setProfile(p); }).finally(() => setLoaded(true));
  }, []);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null); setSaved(false);
    try {
      const result = await api.putProfile(profile);
      setProfile(result);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save the profile.");
    }
  };

  if (!loaded) return <p className="text-[var(--ink-soft)]">Loading…</p>;

  return (
    <section>
      <h2 className="font-display text-xl mb-3">Profile</h2>
      <form onSubmit={save} className="space-y-3">
        <LabeledInput label="Name" required value={profile.name}
          onChange={(v) => setProfile({ ...profile, name: v })} />

        <div>
          <label className="block text-base text-[var(--ink-soft)] mb-1">Preferred language</label>
          <select
            value={profile.preferred_language}
            onChange={(e) => setProfile({ ...profile, preferred_language: e.target.value as Profile["preferred_language"] })}
            className="w-full rounded-xl border border-[var(--paper-line)] bg-transparent px-4 py-3 text-lg"
          >
            <option value="en">English</option>
            <option value="te">Telugu</option>
            <option value="te-en">Telugu + English mixed</option>
          </select>
        </div>

        <LabeledInput label="Department" value={profile.department ?? ""}
          onChange={(v) => setProfile({ ...profile, department: v || null })} />
        <LabeledInput label="Designation" value={profile.designation ?? ""}
          onChange={(v) => setProfile({ ...profile, designation: v || null })} />
        <LabeledInput label="Office" value={profile.office ?? ""}
          onChange={(v) => setProfile({ ...profile, office: v || null })} />
        <LabeledInput label="Employee code" value={profile.employee_code ?? ""}
          onChange={(v) => setProfile({ ...profile, employee_code: v || null })} />
        <LabeledInput label="DDO name" value={profile.ddo_name ?? ""}
          onChange={(v) => setProfile({ ...profile, ddo_name: v || null })} />
        <LabeledInput label="DDO email (emails get addressed here)" type="email" value={profile.ddo_email ?? ""}
          onChange={(v) => setProfile({ ...profile, ddo_email: v || null })} />

        <div>
          <label className="block text-base text-[var(--ink-soft)] mb-1">Email signature</label>
          <textarea
            value={profile.signature ?? ""}
            onChange={(e) => setProfile({ ...profile, signature: e.target.value || null })}
            rows={2}
            className="w-full rounded-xl border border-[var(--paper-line)] bg-transparent px-4 py-3 text-lg"
          />
        </div>

        <label className="flex items-center gap-3 text-lg py-2">
          <input
            type="checkbox"
            checked={profile.family_escalation_enabled}
            onChange={(e) => setProfile({ ...profile, family_escalation_enabled: e.target.checked })}
            className="w-5 h-5"
          />
          Notify a family member if a medicine goes unconfirmed after repeated reminders
        </label>

        {profile.family_escalation_enabled && (
          <>
            <LabeledInput label="Family contact name" value={profile.family_contact_name ?? ""}
              onChange={(v) => setProfile({ ...profile, family_contact_name: v || null })} />
            <LabeledInput label="Family contact email" type="email" value={profile.family_contact_email ?? ""}
              onChange={(v) => setProfile({ ...profile, family_contact_email: v || null })} />
          </>
        )}

        <button type="submit" className="rounded-xl bg-[var(--ink)] text-[var(--paper)] px-6 py-3 text-lg font-medium">
          Save profile
        </button>
        {saved && <span className="ml-3 text-[var(--stamp)] font-medium">✓ Saved</span>}
        {error && <p className="text-[var(--margin)]">{error}</p>}
      </form>
    </section>
  );
}

function LabeledInput({
  label, value, onChange, type = "text", required,
}: { label: string; value: string; onChange: (v: string) => void; type?: string; required?: boolean }) {
  return (
    <div>
      <label className="block text-base text-[var(--ink-soft)] mb-1">{label}</label>
      <input
        type={type} required={required} value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl border border-[var(--paper-line)] bg-transparent px-4 py-3 text-lg"
      />
    </div>
  );
}

const DEFAULT_SCHEDULE: MedicationScheduleIn = {
  time: "08:00", meal_dependency: null, repeat_minutes: 30, max_followups: 2,
};

function MedicationsSection() {
  const [meds, setMeds] = useState<Medication[]>([]);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => api.listMedications().then(setMeds).catch(() => setError("Couldn't load medications."));
  useEffect(() => { refresh(); }, []);

  const remove = async (id: number) => {
    await api.deactivateMedication(id);
    refresh();
  };

  return (
    <section>
      <h2 className="font-display text-xl mb-3">Medications</h2>
      {error && <p className="text-[var(--margin)] mb-3">{error}</p>}

      <div className="ledger mb-4">
        {meds.length === 0 && <p className="py-4 text-[var(--ink-soft)]">No medications set up yet.</p>}
        {meds.map((m) => (
          <div key={m.id} className="ledger-row py-3 flex items-center justify-between gap-4">
            <div>
              <p className="text-lg">{m.name}</p>
              <p className="text-base text-[var(--ink-soft)]">
                {m.time}{m.meal_dependency ? ` · after ${m.meal_dependency}` : ""}
                {m.instructions ? ` · ${m.instructions}` : ""}
              </p>
            </div>
            <button
              onClick={() => remove(m.id)}
              className="rounded-full border border-[var(--margin)] text-[var(--margin)] px-4 py-2 text-base"
            >
              Remove
            </button>
          </div>
        ))}
      </div>

      {adding ? (
        <AddMedicationForm onDone={() => { setAdding(false); refresh(); }} onCancel={() => setAdding(false)} />
      ) : (
        <button
          onClick={() => setAdding(true)}
          className="rounded-xl border border-[var(--paper-line)] px-5 py-3 text-lg"
        >
          + Add a medication
        </button>
      )}
    </section>
  );
}

function AddMedicationForm({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [instructions, setInstructions] = useState("");
  const [schedule, setSchedule] = useState<MedicationScheduleIn>(DEFAULT_SCHEDULE);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api.createMedication(name, instructions || null, schedule);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add that medication.");
    }
  };

  return (
    <form onSubmit={submit} className="rounded-xl border border-[var(--paper-line)] p-4 space-y-3">
      <LabeledInput label="Medicine name" required value={name} onChange={setName} />
      <LabeledInput label="Instructions (optional)" value={instructions} onChange={setInstructions} />
      <div className="flex gap-3 flex-wrap">
        <div>
          <label className="block text-base text-[var(--ink-soft)] mb-1">Time</label>
          <input
            type="time" required value={schedule.time}
            onChange={(e) => setSchedule({ ...schedule, time: e.target.value })}
            className="rounded-xl border border-[var(--paper-line)] bg-transparent px-4 py-3 text-lg"
          />
        </div>
        <div>
          <label className="block text-base text-[var(--ink-soft)] mb-1">After which meal (optional)</label>
          <select
            value={schedule.meal_dependency ?? ""}
            onChange={(e) => setSchedule({ ...schedule, meal_dependency: (e.target.value || null) as MedicationScheduleIn["meal_dependency"] })}
            className="rounded-xl border border-[var(--paper-line)] bg-transparent px-4 py-3 text-lg"
          >
            <option value="">No meal dependency</option>
            <option value="breakfast">Breakfast</option>
            <option value="lunch">Lunch</option>
            <option value="dinner">Dinner</option>
          </select>
        </div>
      </div>
      <div className="flex gap-3">
        <button type="submit" className="rounded-xl bg-[var(--ink)] text-[var(--paper)] px-6 py-3 text-lg font-medium">
          Add
        </button>
        <button type="button" onClick={onCancel} className="rounded-xl border border-[var(--paper-line)] px-6 py-3 text-lg">
          Cancel
        </button>
      </div>
      {error && <p className="text-[var(--margin)]">{error}</p>}
    </form>
  );
}
