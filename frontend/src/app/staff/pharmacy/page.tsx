"use client";

/**
 * Pharmacy dashboard — medicine ready, issued or unavailable, then close.
 *
 * "Unavailable" is a first-class action, not an error state. The patient still
 * needs somewhere to go, so the visit stays open and the row stays on screen.
 */

import { useState } from "react";

import { ConfirmDialog } from "@/components/ConfirmDialog";
import { QueueTable, StageSummaryBar } from "@/components/QueueTable";
import {
  Button,
  Card,
  ConnectionBanner,
  CountChip,
  ErrorNote,
} from "@/components/ui";
import { useStageQueue } from "@/lib/useStageQueue";

export default function PharmacyPage() {
  const queue = useStageQueue("pharmacy");
  const [confirmClose, setConfirmClose] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <ConnectionBanner state={queue.connection} />
      <ErrorNote message={queue.error} />

      <StageSummaryBar summary={queue.summary} />

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
          Waiting for dispensing
          <CountChip value={queue.visits.length} />
        </h2>
        <QueueTable
          caption="Patients waiting at pharmacy"
          loading={queue.loading}
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
              {/* Closing a visit is the one irreversible action in the
                  system — there is no "reopen". A confirm step is cheap
                  next to a patient whose visit was ended by a mis-tap. */}
              <Button
                accent="bg-role-pharmacy"
                disabled={queue.busyToken === visit.token}
                onClick={() => setConfirmClose(visit.token)}
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

      {confirmClose && (
        <ConfirmDialog
          title={`Close visit ${confirmClose}?`}
          body="This records the medicine as issued and ends the patient's visit. It cannot be undone."
          confirmLabel="Dispense and close"
          onCancel={() => setConfirmClose(null)}
          onConfirm={() => {
            const token = confirmClose;
            setConfirmClose(null);
            queue.act(token, "pharmacy/", { state: "medicine_issued" });
          }}
        />
      )}
    </div>
  );
}
