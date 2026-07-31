"use client";

/**
 * Consultation dashboard — the clinician's queue, priority, tests, pharmacy.
 *
 * The current patient's token is shown as large as it is on the patient's own
 * screen, so a clinician confirming "T-041?" is reading the same thing the
 * patient is holding.
 */

import { useState } from "react";

import { PriorityDialog } from "@/components/PriorityDialog";
import { QueueTable, StageSummaryBar } from "@/components/QueueTable";
import {
  Button,
  Card,
  ConnectionBanner,
  ErrorNote,
  PriorityTag,
  TokenFigure,
} from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { useStageQueue } from "@/lib/useStageQueue";

export default function ConsultationPage() {
  const queue = useStageQueue("consultation");
  const { can } = useAuth();
  const [priorityFor, setPriorityFor] = useState<string | null>(null);

  const current =
    queue.visits.find((visit) => visit.stage_status === "in_progress") ?? null;
  const waiting = queue.visits.filter((visit) => visit !== current);

  return (
    <div className="space-y-6">
      <ConnectionBanner state={queue.connection} />
      <ErrorNote message={queue.error} />

      <StageSummaryBar summary={queue.summary} />

      <Card className="border-role-clinician">
        <h2 className="text-sm font-medium uppercase tracking-wide text-ink-muted">
          Current patient
        </h2>

        {!current ? (
          <p className="mt-4 text-ink-muted">
            No patient in consultation. Start one from the queue below.
          </p>
        ) : (
          <>
            <p className="mt-2">
              <TokenFigure token={current.token} size="medium" />
            </p>

            <dl className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-sm text-ink-muted">Priority</dt>
                <dd className="mt-1">
                  <PriorityTag
                    priority={current.priority}
                    label={current.priority_label}
                  />
                </dd>
              </div>
              <div>
                <dt className="text-sm text-ink-muted">Stage</dt>
                <dd className="mt-1 font-medium">
                  {current.awaiting_tests
                    ? "Awaiting laboratory tests"
                    : "Vital signs completed"}
                </dd>
              </div>
            </dl>

            <div className="mt-6 space-y-3">
              <Button
                fullWidth
                accent="bg-role-clinician"
                disabled={queue.busyToken === current.token}
                onClick={() => queue.act(current, "complete/")}
              >
                Consultation complete &amp; send to pharmacy →
              </Button>

              <div className="flex flex-wrap gap-3">
                {can("assign_priority") && (
                  <Button
                    variant="secondary"
                    onClick={() => setPriorityFor(current.token)}
                  >
                    Set priority
                  </Button>
                )}
                {current.awaiting_tests ? (
                  <Button
                    variant="secondary"
                    onClick={() => queue.act(current, "return-after-tests/")}
                  >
                    Patient returned from tests
                  </Button>
                ) : (
                  <Button
                    variant="secondary"
                    onClick={() => queue.act(current, "send-for-tests/")}
                  >
                    Send for laboratory tests
                  </Button>
                )}
              </div>
            </div>
          </>
        )}
      </Card>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Waiting for consultation</h2>
        <QueueTable
          caption="Patients waiting for the clinician"
          visits={waiting}
          columns={["priority", "presence", "waiting"]}
          emptyMessage="Nobody is waiting for consultation."
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
                accent="bg-role-clinician"
                disabled={queue.busyToken === visit.token}
                onClick={() => queue.act(visit, "start/")}
              >
                Start
              </Button>
            </>
          )}
        />
      </section>

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
