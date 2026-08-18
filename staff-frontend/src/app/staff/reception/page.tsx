"use client";

/**
 * Reception dashboard — register a patient, issue a token, run the fallback.
 */

import { useCallback, useEffect, useState } from "react";

import { ConfirmDialog } from "@/components/ConfirmDialog";
import { QueueTable, StageSummaryBar } from "@/components/QueueTable";
import {
  Button,
  Card,
  ConnectionBanner,
  CountChip,
  ErrorNote,
  fieldClass,
  TokenFigure,
} from "@shared/ui/components/ui";
import { api } from "@shared/ui/lib/api";
import type {
  StaffVisit,
  StaleVisit,
  StaleVisitsState,
} from "@shared/ui/lib/types";
import { useStageQueue } from "@/lib/useStageQueue";

export default function ReceptionPage() {
  const queue = useStageQueue("registration");
  const [issued, setIssued] = useState<StaffVisit | null>(null);
  const [stale, setStale] = useState<StaleVisitsState | null>(null);
  const [confirming, setConfirming] = useState<StaleVisit | null>(null);
  const [closingId, setClosingId] = useState<number | null>(null);
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
   * Visits nothing has happened to for a full day.
   *
   * Loaded on its own rather than through the queue socket: these are not the
   * reception queue, and most of them are no longer in any stage queue at all.
   * There is nothing live about a visit that has been still for 24 hours, so a
   * fetch on mount and after each close is the whole of what it needs.
   */
  const fetchStale = useCallback(
    () => api<StaleVisitsState>("visits/stale/"),
    [],
  );

  useEffect(() => {
    // A failure here must not take the registration desk down with it —
    // issuing tokens is the job, tidying abandoned visits is housekeeping.
    fetchStale().then(setStale).catch(() => undefined);
  }, [fetchStale]);

  async function closeAbandoned(visit: StaleVisit) {
    setConfirming(null);
    setClosingId(visit.id);
    queue.setError(null);

    try {
      // By id, not token: these visits are old enough that the token may
      // already have been reissued to somebody in the waiting room.
      await api(`visits/stale/${visit.id}/close/`, { method: "POST" });
      const [refreshed] = await Promise.all([fetchStale(), queue.reload()]);
      setStale(refreshed);
    } catch (caught) {
      queue.setError(
        caught instanceof Error
          ? caught.message
          : `Could not close ${visit.token}.`,
      );
    } finally {
      setClosingId(null);
    }
  }

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

      {/*
        The live region is mounted empty and always present, never alongside the
        token it announces: a region inserted at the same moment as its content
        is not a change to that region, and screen readers stay silent. The clerk
        has to read this number out to the patient, so silence is the one
        outcome that cannot be allowed.
      */}
      <p aria-live="polite" className="sr-only">
        {issued ? `Token ${issued.token} issued.` : ""}
      </p>

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
                <TokenFigure token={issued.token} size="medium" />
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
              className={fieldClass("reception")}
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
                className={fieldClass("reception", "max-w-xs")}
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
                className={fieldClass("reception", "w-auto")}
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
                className={fieldClass("reception", "w-auto")}
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
                className={fieldClass("reception", "min-h-target w-auto")}
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

      {/* Only rendered when there is something to do. An empty panel headed
          "abandoned visits" on every shift teaches the desk to ignore it, and
          then it is still being ignored on the day it has something in it. */}
      {stale && stale.visits.length > 0 && (
        <section>
          <h2 className="mb-1 flex items-center gap-2 text-lg font-semibold">
            Abandoned visits
            <CountChip value={stale.visits.length} />
          </h2>
          <p className="mb-3 max-w-2xl text-sm text-ink-muted">
            Nothing has happened to these visits for{" "}
            {stale.stale_after_hours} hours, so the patient almost certainly
            left without telling anyone. Until they are closed they stay on the
            waiting-room board and in a stage queue. Check the desk and the
            waiting area first — closing removes the patient from every queue.
          </p>
          <QueueTable
            caption="Visits with no activity for a day or more"
            visits={stale.visits}
            columns={["stage", "presence"]}
            emptyMessage="No abandoned visits."
            renderActions={(visit) => {
              const row = visit as StaleVisit;
              return (
                <div className="flex items-center gap-3">
                  {/* The number the decision rests on, next to the button that
                      acts on it. */}
                  <span className="whitespace-nowrap text-sm text-ink-muted">
                    idle {row.idle_hours}h
                  </span>
                  <Button
                    variant="danger"
                    disabled={closingId === row.id}
                    onClick={() => setConfirming(row)}
                  >
                    {closingId === row.id ? "Closing…" : "Close as abandoned"}
                  </Button>
                </div>
              );
            }}
          />
        </section>
      )}

      {confirming && (
        <ConfirmDialog
          destructive
          title={`Close ${confirming.token} as abandoned?`}
          body={
            `Nothing has happened to this visit for ${confirming.idle_hours} hours. ` +
            `Closing it removes the patient from the ${confirming.stage_label} ` +
            "queue and from the waiting-room board, and cannot be undone. " +
            "Your name is recorded against it."
          }
          confirmLabel="Close as abandoned"
          onConfirm={() => void closeAbandoned(confirming)}
          onCancel={() => setConfirming(null)}
        />
      )}
    </div>
  );
}
