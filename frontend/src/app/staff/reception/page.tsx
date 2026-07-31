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

  async function register(preference: "screen" | "printed") {
    setRegistering(true);
    queue.setError(null);
    try {
      const visit = await api<StaffVisit>("visits/check-in/", {
        method: "POST",
        body: { notification_preference: preference },
      });
      setIssued(visit);
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
        <Card className="border-role-reception bg-role-reception-soft">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-sm text-ink-muted">Token issued</p>
              <p aria-live="polite">
                <TokenFigure token={issued.token} size="medium" />
              </p>
              <p className="mt-1 text-sm text-ink-muted">
                Give the patient this token and point them to the waiting area.
              </p>
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
              className="mt-1.5 w-full rounded-lg border border-line px-3 py-2.5"
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
        <h2 className="mb-3 text-lg font-semibold">Current queue</h2>
        <QueueTable
          caption="Patients waiting at reception"
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

      <div className="flex flex-wrap gap-3">
        <Button
          variant="secondary"
          disabled={registering}
          onClick={() => register("printed")}
        >
          Register — printed token
        </Button>
        <Button
          accent="bg-role-reception"
          disabled={registering}
          onClick={() => register("screen")}
        >
          {registering ? "Registering…" : "+ Register patient"}
        </Button>
      </div>

      <Card className="bg-surface-muted">
        <h2 className="font-semibold">If the system goes down</h2>
        <p className="mt-2 text-sm text-ink-muted">
          Switch to the paper fallback: write the time of arrival and the next
          number in the day&apos;s sequence on a slip, keep the sheet in order,
          and enter the slips here once the system returns. The full procedure
          is in the operations runbook.
        </p>
      </Card>
    </div>
  );
}
