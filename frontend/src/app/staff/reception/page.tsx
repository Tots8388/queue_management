"use client";

/**
 * Reception dashboard — register a patient, issue a token, run the fallback.
 */

import { useState } from "react";

import { QueueTable, StageSummaryBar } from "@/components/QueueTable";
import {
  Button,
  Card,
  ConnectionBanner,
  CountChip,
  ErrorNote,
  TokenFigure,
} from "@/components/ui";
import { api } from "@/lib/api";
import type { StaffVisit } from "@/lib/types";
import { useStageQueue } from "@/lib/useStageQueue";

export default function ReceptionPage() {
  const queue = useStageQueue("registration");
  const [issued, setIssued] = useState<StaffVisit | null>(null);
  const [search, setSearch] = useState("");
  const [found, setFound] = useState<string | null>(null);
  const [registering, setRegistering] = useState(false);
  const [preference, setPreference] = useState<"screen" | "printed" | "sms">(
    "printed",
  );
  const [phone, setPhone] = useState("");
  const [arrivedAt, setArrivedAt] = useState("");
  const [sheetRef, setSheetRef] = useState("");
  const [reachedStage, setReachedStage] = useState("registration");
  const [reconciling, setReconciling] = useState(false);

  /**
   * Enter one line from the paper sheet kept during an outage (spec FR12).
   *
   * The arrival time is sent as typed and interpreted in the browser's own
   * timezone, which is the clinic's — the same clock the sheet was written by.
   */
  async function reconcile(event: React.FormEvent) {
    event.preventDefault();
    queue.setError(null);

    if (!arrivedAt) {
      queue.setError("Enter the arrival time written on the paper sheet.");
      return;
    }

    setReconciling(true);
    try {
      const visit = await api<StaffVisit>("visits/reconcile-fallback/", {
        method: "POST",
        body: {
          arrived_at: new Date(arrivedAt).toISOString(),
          paper_reference: sheetRef.trim(),
          stage: reachedStage,
        },
      });
      setIssued(visit);
      setArrivedAt("");
      setSheetRef("");
      await queue.reload();
    } catch (caught) {
      queue.setError(
        caught instanceof Error
          ? caught.message
          : "Could not enter that patient.",
      );
    } finally {
      setReconciling(false);
    }
  }

  async function register(event: React.FormEvent) {
    event.preventDefault();
    setRegistering(true);
    queue.setError(null);

    try {
      const visit = await api<StaffVisit>("visits/check-in/", {
        method: "POST",
        body: {
          notification_preference: preference,
          ...(preference === "sms" && phone.trim()
            ? { phone_number: phone.trim() }
            : {}),
        },
      });
      setIssued(visit);
      setPhone("");
      await queue.reload();
    } catch (caught) {
      queue.setError(
        caught instanceof Error ? caught.message : "Could not register.",
      );
    } finally {
      setRegistering(false);
    }
  }

  function lookUp(event: React.FormEvent) {
    event.preventDefault();
    const token = search.trim().toUpperCase();
    const match = queue.visits.find((visit) => visit.token === token);
    setFound(
      match
        ? `${match.token} — ${match.stage_label}, ${match.presence_label}`
        : `${token} is not waiting at reception.`,
    );
  }

  return (
    <div className="space-y-6">
      <ConnectionBanner state={queue.connection} />
      <ErrorNote message={queue.error} />

      {/* The token just issued, large enough to read out to the patient. */}
      {issued && (
        <Card className="animate-fade-rise border-role-reception/40 bg-role-reception-soft">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <span className="grid size-12 shrink-0 place-items-center rounded-full bg-role-reception text-white">
                <svg viewBox="0 0 20 20" className="size-6 fill-current" aria-hidden="true">
                  <path d="M8.2 13.6 4.6 10l-1.2 1.2 4.8 4.8 9-9L16 5.8z" />
                </svg>
              </span>
              <div>
                <p className="text-sm font-medium text-role-reception">
                  Token issued
                </p>
                <p aria-live="polite">
                  <TokenFigure token={issued.token} size="medium" />
                </p>
                <p className="mt-1 text-sm text-ink-muted">
                  Give the patient this token and point them to the waiting area.
                </p>
              </div>
            </div>
            <Button variant="secondary" onClick={() => setIssued(null)}>
              Done
            </Button>
          </div>
        </Card>
      )}

      <StageSummaryBar summary={queue.summary} />

      <Card>
        <form onSubmit={lookUp} className="flex flex-wrap items-end gap-3">
          <div className="min-w-48 flex-1">
            <label htmlFor="search" className="block font-medium">
              Find a token
            </label>
            <input
              id="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Enter token…"
              autoComplete="off"
              className="mt-1.5 w-full rounded-lg border border-line bg-surface px-3 py-2.5 shadow-xs focus:border-role-reception focus:shadow-[0_0_0_3px_var(--color-role-reception-soft)] focus-visible:outline-none"
            />
          </div>
          <Button type="submit" accent="bg-role-reception">
            Search
          </Button>
        </form>
        {found && (
          <p role="status" className="mt-3 text-sm text-ink-muted">
            {found}
          </p>
        )}
      </Card>

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
          Current queue
          <CountChip value={queue.visits.length} />
        </h2>
        <QueueTable
          caption="Patients waiting at reception"
          loading={queue.loading}
          visits={queue.visits}
          columns={["stage", "priority", "presence", "waiting"]}
          emptyMessage="Nobody is waiting at reception."
          renderActions={(visit) => (
            <>
              <Button
                variant="secondary"
                disabled={queue.busyToken === visit.token}
                onClick={() =>
                  queue.act(visit, "presence/", { presence: "called" })
                }
              >
                Call
              </Button>
              <Button
                accent="bg-role-reception"
                disabled={queue.busyToken === visit.token}
                onClick={() => queue.act(visit, "complete/")}
              >
                Send to vital signs
              </Button>
            </>
          )}
        />
      </section>

      <Card>
        <h2 className="font-semibold">Register a patient</h2>
        <form onSubmit={register} className="mt-4 space-y-4">
          <fieldset>
            <legend className="font-medium">How should they be updated?</legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {[
                { value: "printed", label: "Printed token" },
                { value: "screen", label: "Screen only" },
                { value: "sms", label: "SMS updates" },
              ].map((option) => {
                const checked = preference === option.value;
                return (
                  <label
                    key={option.value}
                    className={`flex min-h-target cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 transition-colors ${
                      checked
                        ? "border-role-reception bg-role-reception-soft font-medium text-role-reception ring-1 ring-role-reception/30"
                        : "border-line hover:bg-surface-muted"
                    }`}
                  >
                    <input
                      type="radio"
                      name="preference"
                      value={option.value}
                      checked={checked}
                      onChange={() =>
                        setPreference(option.value as typeof preference)
                      }
                      className="size-4 accent-role-reception"
                    />
                    {option.label}
                  </label>
                );
              })}
            </div>
          </fieldset>

          {preference === "sms" && (
            <div>
              <label htmlFor="phone" className="block font-medium">
                Mobile number
              </label>
              <input
                id="phone"
                type="tel"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                placeholder="+2547…"
                autoComplete="off"
                className="mt-1.5 w-full max-w-xs rounded-lg border border-line bg-surface px-3 py-2.5 shadow-xs focus:border-role-reception focus:shadow-[0_0_0_3px_var(--color-role-reception-soft)] focus-visible:outline-none"
              />
              <p className="mt-1 text-sm text-ink-muted">
                Only used to send queue updates, and deleted with the visit.
                Messages carry the token and destination only.
              </p>
            </div>
          )}

          <Button
            type="submit"
            accent="bg-role-reception"
            disabled={registering}
          >
            {registering ? "Registering…" : "+ Register patient"}
          </Button>
        </form>
      </Card>

      <Card className="bg-surface-muted">
        <h2 className="font-semibold">Paper fallback</h2>
        <p className="mt-2 text-sm text-ink-muted">
          If the system goes down, write each patient&apos;s{" "}
          <strong>arrival time</strong> and the next number on the paper sheet,
          and call numbers out loud. When the system returns, enter each line
          below. The full procedure is in the operations runbook.
        </p>

        <form onSubmit={reconcile} className="mt-4 space-y-4">
          <div className="flex flex-wrap gap-4">
            <div>
              <label htmlFor="arrived" className="block font-medium">
                Arrival time from the sheet
              </label>
              <input
                id="arrived"
                type="datetime-local"
                value={arrivedAt}
                onChange={(event) => setArrivedAt(event.target.value)}
                className="mt-1.5 rounded-lg border border-line px-3 py-2.5"
              />
              {/* The single thing this form exists to get right. */}
              <p className="mt-1 text-sm text-ink-muted">
                The time they arrived — not the time now. This is what keeps
                their place in the queue.
              </p>
            </div>

            <div>
              <label htmlFor="sheetRef" className="block font-medium">
                Sheet reference
              </label>
              <input
                id="sheetRef"
                value={sheetRef}
                onChange={(event) => setSheetRef(event.target.value)}
                placeholder="Sheet 2, line 7"
                autoComplete="off"
                className="mt-1.5 rounded-lg border border-line px-3 py-2.5"
              />
            </div>

            <div>
              <label htmlFor="reachedStage" className="block font-medium">
                Stage reached on paper
              </label>
              <select
                id="reachedStage"
                value={reachedStage}
                onChange={(event) => setReachedStage(event.target.value)}
                className="mt-1.5 min-h-target rounded-lg border border-line px-3 py-2.5"
              >
                <option value="registration">Registration</option>
                <option value="vitals">Vital signs</option>
                <option value="consultation">Consultation</option>
                <option value="pharmacy">Pharmacy</option>
              </select>
            </div>
          </div>

          <Button type="submit" variant="secondary" disabled={reconciling}>
            {reconciling ? "Entering…" : "Enter from paper fallback"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
