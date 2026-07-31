"use client";

/**
 * Pharmacy dashboard — medicine ready, issued or unavailable, then close.
 *
 * "Unavailable" is a first-class action, not an error state. The patient still
 * needs somewhere to go, so the visit stays open and the row stays on screen.
 */

import { QueueTable, StageSummaryBar } from "@/components/QueueTable";
import { Button, Card, ConnectionBanner, ErrorNote } from "@/components/ui";
import { useStageQueue } from "@/lib/useStageQueue";

export default function PharmacyPage() {
  const queue = useStageQueue("pharmacy");

  return (
    <div className="space-y-6">
      <ConnectionBanner state={queue.connection} />
      <ErrorNote message={queue.error} />

      <StageSummaryBar summary={queue.summary} />

      <section>
        <h2 className="mb-3 text-lg font-semibold">Waiting for dispensing</h2>
        <QueueTable
          caption="Patients waiting at pharmacy"
          visits={queue.visits}
          columns={["priority", "presence", "waiting"]}
          emptyMessage="Nobody is waiting at pharmacy."
          renderActions={(visit) => (
            <>
              <Button
                variant="secondary"
                disabled={queue.busyToken === visit.token}
                onClick={() =>
                  queue.act(visit, "pharmacy/", { state: "medicine_ready" })
                }
              >
                Ready
              </Button>
              <Button
                accent="bg-role-pharmacy"
                disabled={queue.busyToken === visit.token}
                onClick={() =>
                  queue.act(visit, "pharmacy/", { state: "medicine_issued" })
                }
              >
                Dispense &amp; close
              </Button>
            </>
          )}
        />
      </section>

      <Card>
        <h2 className="font-semibold">Medicine not available</h2>
        <p className="mt-1 text-sm text-ink-muted">
          Recording this keeps the visit open so the patient can be directed
          onward. It does not close their visit.
        </p>

        {queue.visits.length === 0 ? (
          <p className="mt-4 text-ink-muted">No patients at pharmacy.</p>
        ) : (
          <ul className="mt-4 flex flex-wrap gap-2">
            {queue.visits.map((visit) => (
              <li key={visit.token}>
                <Button
                  variant="secondary"
                  disabled={queue.busyToken === visit.token}
                  onClick={() =>
                    queue.act(visit, "pharmacy/", {
                      state: "medicine_unavailable",
                    })
                  }
                >
                  {visit.token} — not available
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
