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

import {
  cx,
  EmptyState,
  PriorityTag,
  StatusPill,
  TableSkeleton,
} from "@/components/ui";
import { presenceLabel } from "@/lib/contracts";
import type { StaffVisit } from "@/lib/types";

export type QueueColumn = "priority" | "stage" | "presence" | "waiting";

export function QueueTable({
  visits,
  columns = ["priority", "presence", "waiting"],
  renderActions,
  emptyMessage = "Nobody is waiting at this stage.",
  caption,
  loading = false,
}: {
  visits: StaffVisit[];
  columns?: QueueColumn[];
  renderActions?: (visit: StaffVisit) => ReactNode;
  emptyMessage?: string;
  caption: string;
  loading?: boolean;
}) {
  // "Nobody is waiting" and "we have not loaded yet" mean very different things
  // to a member of staff deciding whether to call the next patient, so they
  // must not look the same.
  if (loading && visits.length === 0) {
    return <TableSkeleton />;
  }

  if (visits.length === 0) {
    return <EmptyState message={emptyMessage} />;
  }

  return (
    // Wide tables scroll inside their own container rather than pushing the
    // page sideways on a narrow terminal.
    <div className="overflow-x-auto rounded-xl border border-line bg-surface shadow-sm">
      <table className="w-full min-w-[36rem] border-collapse text-left">
        <caption className="sr-only-focusable">{caption}</caption>
        <thead>
          <tr className="border-b border-line bg-surface-muted/70 text-xs uppercase tracking-wide text-ink-muted">
            <th scope="col" className="px-4 py-3 font-semibold">
              Token
            </th>
            {columns.includes("stage") && (
              <th scope="col" className="px-4 py-3 font-semibold">
                Stage
              </th>
            )}
            {columns.includes("priority") && (
              <th scope="col" className="px-4 py-3 font-semibold">
                Priority
              </th>
            )}
            {columns.includes("presence") && (
              <th scope="col" className="px-4 py-3 font-semibold">
                Status
              </th>
            )}
            {columns.includes("waiting") && (
              <th scope="col" className="px-4 py-3 font-semibold">
                Waiting
              </th>
            )}
            {renderActions && (
              <th scope="col" className="px-4 py-3 text-right font-semibold">
                Action
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {visits.map((visit) => {
            const emergency = visit.priority === "emergency";
            return (
              <tr
                key={visit.token}
                className={cx(
                  "border-b border-line transition-colors last:border-0 hover:bg-surface-muted/60",
                  emergency && "bg-priority-emergency-soft/40",
                )}
              >
                <th scope="row" className="px-4 py-3.5 text-left">
                  <span className="flex items-center gap-2">
                    {emergency && (
                      <span
                        aria-hidden="true"
                        className="h-6 w-1 rounded-full bg-priority-emergency"
                      />
                    )}
                    <span className="token-figure text-lg font-semibold">
                      {visit.token}
                    </span>
                    {visit.awaiting_tests && (
                      <span className="rounded-md bg-surface-sunken px-2 py-0.5 text-xs font-medium text-ink-muted">
                        At tests
                      </span>
                    )}
                  </span>
                </th>

                {columns.includes("stage") && (
                  <td className="px-4 py-3.5 text-ink-muted">
                    {visit.stage_label}
                  </td>
                )}

                {columns.includes("priority") && (
                  <td className="px-4 py-3.5">
                    <PriorityTag
                      priority={visit.priority}
                      label={visit.priority_label}
                    />
                  </td>
                )}

                {columns.includes("presence") && (
                  <td className="px-4 py-3.5">
                    <StatusPill
                      status={visit.presence_status}
                      label={presenceLabel(visit.presence_status)}
                    />
                  </td>
                )}

                {columns.includes("waiting") && (
                  <td className="px-4 py-3.5 tabular-nums text-ink-muted">
                    {visit.waiting_minutes} min
                  </td>
                )}

                {renderActions && (
                  <td className="px-4 py-3.5">
                    <div className="flex justify-end gap-2">
                      {renderActions(visit)}
                    </div>
                  </td>
                )}
              </tr>
            );
          })}
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
  const items: Array<{
    label: string;
    value: number;
    tone?: "emergency" | "urgent";
  }> = [
    { label: "Waiting", value: summary.waiting },
    { label: "Being seen", value: summary.in_progress },
    { label: "Stepped away", value: summary.stepped_away },
    { label: "Emergency", value: summary.emergency, tone: "emergency" },
    { label: "Urgent", value: summary.urgent, tone: "urgent" },
  ];

  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      {items.map((item) => {
        const active = !!item.tone && item.value > 0;
        const toneClass =
          item.tone === "emergency"
            ? active
              ? "border-priority-emergency/30 bg-priority-emergency-soft"
              : ""
            : item.tone === "urgent"
              ? active
                ? "border-priority-urgent/30 bg-priority-urgent-soft"
                : ""
              : "";
        const valueTone =
          active && item.tone === "emergency"
            ? "text-priority-emergency"
            : active && item.tone === "urgent"
              ? "text-priority-urgent"
              : "text-ink";

        return (
          <div
            key={item.label}
            className={cx(
              "rounded-xl border border-line bg-surface px-4 py-3 shadow-xs",
              toneClass,
            )}
          >
            <dt className="text-sm font-medium text-ink-muted">{item.label}</dt>
            <dd className={cx("text-2xl font-semibold tabular-nums", valueTone)}>
              {item.value}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
