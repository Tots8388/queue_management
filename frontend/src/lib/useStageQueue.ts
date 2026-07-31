"use client";

/**
 * A staff dashboard's view of one stage.
 *
 * The socket is the live path; the HTTP fetch is what fills the screen if the
 * socket cannot open at all. Actions post to REST and then rely on the
 * broadcast to bring the new state back, so every terminal sees the same queue
 * rather than each one guessing locally.
 */

import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "./api";
import type { StaffQueueState, StaffVisit } from "./types";
import { useQueueChannel } from "./useQueueChannel";

export function useStageQueue(stage: string) {
  const { data, connection, setData } = useQueueChannel<StaffQueueState>(
    `/ws/staff/${stage}/`,
    { authenticated: true },
  );
  const [error, setError] = useState<string | null>(null);
  const [busyToken, setBusyToken] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api<StaffQueueState>(`queue/${stage}/`));
    } catch (caught) {
      setError(
        caught instanceof ApiError && caught.isOffline
          ? "Cannot reach the queue server. Use the paper fallback until it returns."
          : "Could not load the queue.",
      );
    }
  }, [stage, setData]);

  // First paint. The socket normally delivers state on connect; this covers the
  // case where the socket cannot open at all, so a dashboard is never blank
  // just because WebSockets are blocked on the network.
  useEffect(() => {
    let cancelled = false;

    api<StaffQueueState>(`queue/${stage}/`)
      .then((state) => {
        if (!cancelled) setData(state);
      })
      .catch((caught) => {
        if (cancelled) return;
        setError(
          caught instanceof ApiError && caught.isOffline
            ? "Cannot reach the queue server. Use the paper fallback until it returns."
            : "Could not load the queue.",
        );
      });

    return () => {
      cancelled = true;
    };
  }, [stage, setData]);

  /**
   * Run an action against one visit.
   *
   * Errors are surfaced rather than swallowed: a member of staff who thinks
   * they marked a patient complete, and did not, is a worse outcome than an
   * error message.
   */
  const act = useCallback(
    async (visit: StaffVisit | string, path: string, body?: unknown) => {
      const token = typeof visit === "string" ? visit : visit.token;
      setBusyToken(token);
      setError(null);

      try {
        await api(`visits/${encodeURIComponent(token)}/${path}`, {
          method: "POST",
          body: body ?? {},
        });
        // The broadcast normally updates every terminal. Refetch anyway so the
        // person who acted is never left looking at a stale row.
        await load();
        return true;
      } catch (caught) {
        setError(
          caught instanceof Error ? caught.message : "That action did not work.",
        );
        return false;
      } finally {
        setBusyToken(null);
      }
    },
    [load],
  );

  return {
    // Derived from state that already existed — nothing here changes when or
    // how the queue is fetched, it just lets a table show a skeleton instead of
    // an "empty queue" message before the first response has arrived.
    loading: data === null && error === null,
    visits: data?.visits ?? [],
    summary:
      data?.summary ?? {
        stage,
        waiting: 0,
        in_progress: 0,
        stepped_away: 0,
        emergency: 0,
        urgent: 0,
      },
    connection,
    error,
    setError,
    busyToken,
    act,
    reload: load,
  };
}
