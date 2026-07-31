"use client";

/**
 * Recording a clinical priority decision (spec FR3, FR5).
 *
 * The reason is required and offered as non-sensitive categories rather than a
 * free-text box. That is not a UI nicety: a free-text field beside a patient is
 * where a diagnosis or a symptom would end up, and this database holds neither.
 * "Other" still accepts short text, bounded and labelled as non-clinical.
 */

import { useEffect, useRef, useState } from "react";

import { Button, ErrorNote, Spinner } from "@/components/ui";

const REASONS = [
  "Clinical assessment at triage",
  "Referred urgently by clinician",
  "Escalated during vital signs",
  "Deteriorated while waiting",
];

export function PriorityDialog({
  token,
  onSubmit,
  onClose,
}: {
  token: string;
  onSubmit: (priority: string, reason: string) => Promise<boolean>;
  onClose: () => void;
}) {
  const [priority, setPriority] = useState("urgent");
  const [reason, setReason] = useState(REASONS[0]);
  const [other, setOther] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const headingRef = useRef<HTMLHeadingElement>(null);

  // Move focus into the dialog so a keyboard user is not left behind on the
  // page underneath.
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const finalReason = reason === "Other" ? other.trim() : reason;

    if (!finalReason) {
      setError("A reason is required. It is recorded against your role.");
      return;
    }

    setBusy(true);
    const ok = await onSubmit(priority, finalReason);
    setBusy(false);
    if (ok) onClose();
    else setError("The priority change was not saved.");
  }

  const options = [
    {
      value: "emergency",
      label: "Emergency",
      hint: "Immediate clinical attention",
      selected: "border-priority-emergency bg-priority-emergency-soft ring-1 ring-priority-emergency/40",
      dot: "text-priority-emergency",
    },
    {
      value: "urgent",
      label: "Urgent",
      hint: "Next appropriate slot",
      selected: "border-priority-urgent bg-priority-urgent-soft ring-1 ring-priority-urgent/40",
      dot: "text-priority-urgent",
    },
    {
      value: "routine",
      label: "Routine",
      hint: "Check-in order",
      selected: "border-priority-routine bg-priority-routine-soft ring-1 ring-priority-routine/30",
      dot: "text-priority-routine",
    },
  ];

  const selectClass =
    "mt-1.5 min-h-target w-full rounded-lg border border-line bg-surface px-3 py-2.5 shadow-xs " +
    "focus:border-brand-500 focus:shadow-[0_0_0_3px_var(--color-brand-100)] focus-visible:outline-none";

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 px-4 py-4 backdrop-blur-sm sm:items-center">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="priority-heading"
        className="animate-fade-rise w-full max-w-md rounded-2xl bg-surface p-6 shadow-lg"
      >
        <h2
          id="priority-heading"
          ref={headingRef}
          tabIndex={-1}
          className="text-lg font-semibold focus-visible:outline-none"
        >
          Set clinical priority for{" "}
          <span className="token-figure">{token}</span>
        </h2>
        <p className="mt-1 text-sm text-ink-muted">
          Your role, the time and this reason are recorded. The patient is not
          shown their priority.
        </p>

        <form onSubmit={submit} className="mt-5 space-y-4">
          <fieldset>
            <legend className="font-medium">Priority</legend>
            <div className="mt-2 space-y-2">
              {options.map((option) => {
                const checked = priority === option.value;
                return (
                  <label
                    key={option.value}
                    className={`flex min-h-target cursor-pointer items-center gap-3 rounded-lg border px-3 py-2.5 transition-colors ${
                      checked
                        ? option.selected
                        : "border-line hover:bg-surface-muted"
                    }`}
                  >
                    <input
                      type="radio"
                      name="priority"
                      value={option.value}
                      checked={checked}
                      onChange={(event) => setPriority(event.target.value)}
                      className="size-4 accent-brand-600"
                    />
                    <span
                      aria-hidden="true"
                      className={`size-2.5 rounded-full bg-current ${option.dot}`}
                    />
                    <span className="flex-1">
                      <span className="font-medium">{option.label}</span>
                      <span className="block text-sm text-ink-muted">
                        {option.hint}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>

          <div>
            <label htmlFor="reason" className="block font-medium">
              Reason
            </label>
            <select
              id="reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              className={selectClass}
            >
              {REASONS.map((option) => (
                <option key={option}>{option}</option>
              ))}
              <option>Other</option>
            </select>
          </div>

          {reason === "Other" && (
            <div>
              <label htmlFor="other" className="block font-medium">
                Reason (non-clinical)
              </label>
              <input
                id="other"
                value={other}
                onChange={(event) => setOther(event.target.value)}
                maxLength={120}
                className="mt-1.5 w-full rounded-lg border border-line bg-surface px-3 py-2.5 shadow-xs focus:border-brand-500 focus:shadow-[0_0_0_3px_var(--color-brand-100)] focus-visible:outline-none"
              />
              <p className="mt-1 text-sm text-ink-muted">
                Do not record symptoms, a diagnosis or a prescription here.
              </p>
            </div>
          )}

          <ErrorNote message={error} />

          <div className="flex justify-end gap-3 border-t border-line pt-4">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant={priority === "emergency" ? "danger" : "primary"}
              disabled={busy}
            >
              {busy ? (
                <>
                  <Spinner /> Saving…
                </>
              ) : (
                "Save priority"
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
