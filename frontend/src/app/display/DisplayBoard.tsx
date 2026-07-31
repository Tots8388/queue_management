"use client";

/**
 * The waiting-room board (spec FR8).
 *
 * Neither prototype sheet included this screen, so it is designed from the
 * spec: anonymous token and destination only, read across a room, no
 * interaction.
 *
 * The rule it exists to honour is absolute — no names, no priority categories,
 * no diagnoses, no prescriptions. The server sends a two-field payload, and
 * this component renders those two fields and nothing else.
 */

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { DisplayState } from "@/lib/types";
import { useQueueChannel } from "@/lib/useQueueChannel";

export function DisplayBoard() {
  const { data, connection } = useQueueChannel<DisplayState>("/ws/display/");
  const [fallback, setFallback] = useState<DisplayState | null>(null);
  const [clock, setClock] = useState<string>("");

  useEffect(() => {
    api<DisplayState>("display/", { authenticated: false })
      .then(setFallback)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    const tick = () =>
      setClock(
        new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      );
    tick();
    const timer = setInterval(tick, 30_000);
    return () => clearInterval(timer);
  }, []);

  const rows = data?.rows ?? fallback?.rows ?? [];

  return (
    <div className="flex min-h-full flex-col bg-brand-900 text-white">
      <header className="flex items-baseline justify-between px-8 py-6">
        <h1 className="text-2xl font-semibold sm:text-3xl">
          Kabarak University Medical Center
        </h1>
        <p className="text-2xl tabular-nums text-brand-100">{clock}</p>
      </header>

      <main id="main" className="flex-1 px-8 pb-8">
        <div className="grid grid-cols-[1fr_1.4fr] gap-4 border-b border-white/25 pb-3 text-xl uppercase tracking-wide text-brand-100 sm:text-2xl">
          <span>Token</span>
          <span>Please go to</span>
        </div>

        {/* Announced politely: a screen reader in the waiting area should not
            interrupt, but the board does update. */}
        <ul aria-live="polite" className="divide-y divide-white/15">
          {rows.map((row) => (
            <li
              key={row.token}
              className="grid grid-cols-[1fr_1.4fr] items-center gap-4 py-5"
            >
              {/* Deliberately huge: this is read from across a waiting room. */}
              <span className="token-figure text-5xl font-bold sm:text-7xl">
                {row.token}
              </span>
              <span className="text-3xl sm:text-5xl">{row.destination}</span>
            </li>
          ))}
        </ul>

        {rows.length === 0 && (
          <p className="py-16 text-center text-3xl text-brand-100">
            No patients are being called at the moment.
          </p>
        )}
      </main>

      <footer className="border-t border-white/20 px-8 py-4 text-lg text-brand-100">
        {connection === "offline" ? (
          <span className="text-priority-urgent-soft">
            Not connected — this board may be out of date. Please listen for
            staff calling tokens.
          </span>
        ) : (
          <span>
            Please watch for your token. Staff will also call it out.
          </span>
        )}
      </footer>
    </div>
  );
}
