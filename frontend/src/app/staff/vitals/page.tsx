"use client";

/**
 * Vital signs dashboard — take vitals, set clinical priority, send onward.
 */

import { useState } from "react";

import { PriorityDialog } from "@/components/PriorityDialog";
import { QueueTable, StageSummaryBar } from "@/components/QueueTable";
import { Button, Card, ConnectionBanner, ErrorNote } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { useStageQueue } from "@/lib/useStageQueue";

export default function VitalsPage() {
  const queue = useStageQueue("vitals");
  const { can } = useAuth();
  const [priorityFor, setPriorityFor] = useState<string | null>(null);

  const inProgress = queue.visits.filter(
    (visit) => visit.stage_status === "in_progress",
  );

  return (
    <div className="space-y-6">
      <ConnectionBanner state={queue.connection} />
      <ErrorNote message={queue.error} />

      <StageSummaryBar summary={queue.summary} />

      <section>
        <h2 className="mb-3 text-lg font-semibold">Waiting patients</h2>
        <QueueTable
          caption="Patients waiting for vital signs"
          visits={queue.visits}
          columns={["priority", "presence", "waiting"]}
          emptyMessage="Nobody is waiting for vital signs."
          renderActions={(visit) => (
            <>
              {can("assign_priority") && (
                <Button
                  variant="secondary"
                  onClick={() => setPriorityFor(visit.token)}
                >
                  Priority
                </Button>
              )}
              <Button
                accent="bg-role-nurse"
                disabled={queue.busyToken === visit.token}
                onClick={() => queue.act(visit, "start/")}
              >
                Start
              </Button>
            </>
          )}
        />
      </section>

      <Card>
        <h2 className="font-semibold">After vital signs</h2>
        <p className="mt-1 text-sm text-ink-muted">
          Marking a patient complete moves them to the clinician queue.
        </p>

        {inProgress.length === 0 ? (
          <p className="mt-4 text-ink-muted">
            Start a patient above to complete their vital signs.
          </p>
        ) : (
          <ul className="mt-4 space-y-3">
            {inProgress.map((visit) => (
              <li
                key={visit.token}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-role-nurse-soft px-4 py-3"
              >
                <span className="token-figure text-xl font-semibold">
                  {visit.token}
                </span>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    onClick={() =>
                      queue.act(visit, "presence/", { presence: "missed_turn" })
                    }
                  >
                    Missed turn
                  </Button>
                  <Button
                    accent="bg-role-nurse"
                    disabled={queue.busyToken === visit.token}
                    onClick={() => queue.act(visit, "complete/")}
                  >
                    Complete &amp; send to clinician →
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {priorityFor && (
        <PriorityDialog
          token={priorityFor}
          onClose={() => setPriorityFor(null)}
          onSubmit={(priority, reason) =>
            queue.act(priorityFor, "priority/", { priority, reason })
          }
        />
      )}
    </div>
  );
}
