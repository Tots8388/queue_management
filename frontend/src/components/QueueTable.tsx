"use client";

/**
 * The token-first queue table used by every staff dashboard.
 *
 * Column order is token → state → action, matching the approved prototypes, so
 * the eye travels from who, to where they are, to what to do.
 *
 * Priority is shown here because these are staff screens. The same data must
 * never reach the patient view or the waiting-room board (spec FR8).
 */

import type { ReactNode } from "react";

import { EmptyState, PriorityTag, StatusPill } from "@/components/ui";
import { presenceLabel } from "@/lib/contracts";
import type { StaffVisit } from "@/lib/types";

export type QueueColumn = "priority" | "stage" | "presence" | "waiting";

export function QueueTable({
  visits,
  columns = ["priority", "presence", "waiting"],
  renderActions,
  emptyMessage = "Nobody is waiting at this stage.",
  caption,
}: {
  visits: StaffVisit[];
  columns?: QueueColumn[];
  renderActions?: (visit: StaffVisit) => ReactNode;
  emptyMessage?: string;
  caption: string;
}) {
  if (visits.length === 0) {
    return <EmptyState message={emptyMessage} />;
  }

  return (
    // Wide tables scroll inside their own container rather than pushing the
    // page sideways on a narrow terminal.
    <div className="overflow-x-auto rounded-xl border border-line bg-surface">
      <table className="w-full min-w-[36rem] border-collapse text-left">
        <caption className="sr-only-focusable">{caption}</caption>
        <thead>
          <tr className="border-b border-line text-sm text-ink-muted">
            <th scope="col" className="px-4 py-3 font-medium">
              Token
            </th>
            {columns.includes("stage") && (
              <th scope="col" className="px-4 py-3 font-medium">
                Stage
              </th>
            )}
            {columns.includes("priority") && (
              <th scope="col" className="px-4 py-3 font-medium">
                Priority
              </th>
            )}
            {columns.includes("presence") && (
              <th scope="col" className="px-4 py-3 font-medium">
                Status
              </th>
            )}
            {columns.includes("waiting") && (
              <th scope="col" className="px-4 py-3 font-medium">
                Waiting
              </th>
            )}
            {renderActions && (
              <th scope="col" className="px-4 py-3 text-right font-medium">
                Action
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {visits.map((visit) => (
            <tr key={visit.token} className="border-b border-line last:border-0">
              <th scope="row" className="px-4 py-3 text-left">
                <span className="token-figure text-lg font-semibold">
                  {visit.token}
                </span>
                {visit.awaiting_tests && (
                  <span className="ml-2 rounded bg-surface-muted px-2 py-0.5 text-xs text-ink-muted">
                    At tests
                  </span>
                )}
              </th>

              {columns.includes("stage") && (
                <td className="px-4 py-3">{visit.stage_label}</td>
              )}

              {columns.includes("priority") && (
                <td className="px-4 py-3">
                  <PriorityTag
                    priority={visit.priority}
                    label={visit.priority_label}
                  />
                </td>
              )}

              {columns.includes("presence") && (
                <td className="px-4 py-3">
                  <StatusPill
                    status={visit.presence_status}
                    label={presenceLabel(visit.presence_status)}
                  />
                </td>
              )}

              {columns.includes("waiting") && (
                <td className="px-4 py-3 tabular-nums text-ink-muted">
                  {visit.waiting_minutes} min
                </td>
              )}

              {renderActions && (
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    {renderActions(visit)}
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function StageSummaryBar({
  summary,
}: {
  summary: {
    waiting: number;
    in_progress: number;
    stepped_away: number;
    emergency: number;
    urgent: number;
  };
}) {
  const items = [
    { label: "Waiting", value: summary.waiting },
    { label: "Being seen", value: summary.in_progress },
    { label: "Stepped away", value: summary.stepped_away },
    { label: "Emergency", value: summary.emergency },
    { label: "Urgent", value: summary.urgent },
  ];

  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      {items.map((item) => (
        <div
          key={item.label}
          className="rounded-lg border border-line bg-surface px-4 py-3"
        >
          <dt className="text-sm text-ink-muted">{item.label}</dt>
          <dd className="text-2xl font-semibold tabular-nums">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
