"use client";

/**
 * "View patient history" from the approved prototypes.
 *
 * Shows the queue's own history — stage timings, priority decisions, pharmacy
 * outcomes — and no clinical record, because the queue database holds none.
 * A clinician seeing that a patient checked in at 08:10 and has already been
 * through consultation once has the context the return-after-tests path needs.
 */

import { useEffect, useRef, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { Button, ErrorNote, Skeleton } from "@shared/ui/components/ui";
import { api } from "@shared/ui/lib/api";

type StageRow = {
  stage: string;
  stage_label: string;
  entered_at: string;
  completed_at: string | null;
  completed_by_role: string;
  minutes: number | null;
};

type History = {
  token: string;
  check_in_time: string;
  priority_label: string;
  awaiting_tests: boolean;
  stages: StageRow[];
  priority_changes: Array<{
    timestamp: string;
    from: string;
    to: string;
    by_role: string;
    reason: string;
  }>;
  pharmacy: Array<{ state_label: string; timestamp: string; by_role: string }>;
};

const time = (value: string) =>
  new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

export function VisitHistoryDialog({
  token,
  onClose,
}: {
  token: string;
  onClose: () => void;
}) {
  const [history, setHistory] = useState<History | null>(null);
  const [error, setError] = useState<string | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let cancelled = false;

    api<History>(`visits/${encodeURIComponent(token)}/history/`)
      .then((data) => {
        if (!cancelled) setHistory(data);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load this patient's history.");
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <Dialog
      onClose={onClose}
      labelledBy="history-heading"
      initialFocus={headingRef}
      width="max-w-lg"
    >
      <h2
        id="history-heading"
        ref={headingRef}
        tabIndex={-1}
        className="text-lg font-semibold"
      >
        History for {token}
      </h2>

      <ErrorNote message={error} />

      {!history ? (
        !error && (
          <div className="mt-4 space-y-2">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        )
      ) : (
        <div className="mt-4 space-y-6">
          <p className="text-sm text-ink-muted">
            Checked in at {time(history.check_in_time)}
            {history.awaiting_tests && " · currently at laboratory tests"}
          </p>

          <section>
            <h3 className="font-medium">Stages</h3>
            <ol className="mt-2 space-y-2">
              {history.stages.map((stage, index) => (
                <li
                  key={`${stage.stage}-${index}`}
                  className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg border border-line px-3 py-2"
                >
                  <span className="font-medium">{stage.stage_label}</span>
                  <span className="text-sm text-ink-muted">
                    {time(stage.entered_at)}
                    {stage.completed_at
                      ? ` → ${time(stage.completed_at)} (${stage.minutes} min)`
                      : " → in progress"}
                  </span>
                </li>
              ))}
            </ol>
          </section>

          {history.priority_changes.length > 0 && (
            <section>
              <h3 className="font-medium">Priority decisions</h3>
              <ul className="mt-2 space-y-2">
                {history.priority_changes.map((change, index) => (
                  <li
                    key={index}
                    className="rounded-lg border border-line px-3 py-2 text-sm"
                  >
                    <span className="font-medium">
                      {change.from} → {change.to}
                    </span>{" "}
                    <span className="text-ink-muted">
                      at {time(change.timestamp)} by {change.by_role}
                    </span>
                    <p className="text-ink-muted">{change.reason}</p>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {history.pharmacy.length > 0 && (
            <section>
              <h3 className="font-medium">Pharmacy</h3>
              <ul className="mt-2 space-y-2">
                {history.pharmacy.map((outcome, index) => (
                  <li
                    key={index}
                    className="rounded-lg border border-line px-3 py-2 text-sm"
                  >
                    {outcome.state_label}{" "}
                    <span className="text-ink-muted">
                      at {time(outcome.timestamp)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <p className="text-sm text-ink-muted">
            This is the queue record only. It holds no clinical information —
            consult the medical record for that.
          </p>
        </div>
      )}

      <div className="mt-6 flex justify-end">
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      </div>
    </Dialog>
  );
}
