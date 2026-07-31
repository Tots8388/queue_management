"use client";

/**
 * Subscribes to a queue channel over WebSocket.
 *
 * The server sends the whole of a channel's view in every message, including
 * on connect, so there is nothing to replay after a dropped connection —
 * reconnecting *is* the resync.
 *
 * Connection state is surfaced rather than hidden. When the socket is down,
 * staff need to know they may be looking at a stale queue, because that is the
 * moment the manual paper fallback exists for.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { tokens } from "./api";
import { wsBaseUrl } from "./config";

export type ConnectionState = "connecting" | "live" | "offline";

const MAX_RETRY_DELAY_MS = 15_000;

export function useQueueChannel<T>(
  path: string | null,
  { authenticated = false }: { authenticated?: boolean } = {},
) {
  const [data, setData] = useState<T | null>(null);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!path) return;

    // The reconnect loop is defined inside the effect so it can call itself and
    // still be torn down cleanly by the returned cleanup.
    let attempt = 0;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let stopped = false;

    const open = () => {
      if (stopped) return;

      const query =
        authenticated && tokens.access ? `?token=${tokens.access}` : "";
      const socket = new WebSocket(`${wsBaseUrl()}${path}${query}`);
      socketRef.current = socket;

      socket.onopen = () => {
        attempt = 0;
        setConnection("live");
      };

      socket.onmessage = (event) => {
        try {
          setData(JSON.parse(event.data) as T);
        } catch {
          // A malformed frame is not worth tearing the connection down for;
          // the next update carries the full state again.
        }
      };

      socket.onclose = () => {
        if (stopped) return;
        setConnection("offline");

        // Back off, but keep trying: a display screen left on overnight should
        // recover by itself when the server comes back.
        const delay = Math.min(1000 * 2 ** attempt, MAX_RETRY_DELAY_MS);
        attempt += 1;
        timer = setTimeout(open, delay);
      };

      socket.onerror = () => socket.close();
    };

    open();

    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      socketRef.current?.close();
    };
  }, [path, authenticated]);

  /** Ask for the current state — used after a tab wakes from sleep. */
  const resync = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ action: "resync" }));
    }
  }, []);

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") resync();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [resync]);

  return { data, connection, resync, setData };
}
