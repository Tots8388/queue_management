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
 *
 * Everything scales with the viewport (clamp / vw-relative sizes) so the same
 * page fills a 55" wall screen and still holds together on a laptop.
 */

import { useEffect, useState } from "react";

import { Crest, HomeLink } from "@/components/ui";
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
  const offline = connection === "offline";

  return (
    // min-h-dvh, not min-h-full: a percentage height needs an ancestor with a
    // resolved height, and without one the board collapses to its content —
    // leaving a pale band below it on a wall screen, worst of all when the
    // queue is empty and there is least content to fill it.
    <div className="flex min-h-dvh flex-col bg-brand-900 bg-board-gradient text-white">
      <header className="flex items-center justify-between border-b border-white/15 px-[3vw] py-[2.2vh]">
        <div className="flex items-center gap-4">
          <span className="grid size-[clamp(2.5rem,4vw,4rem)] place-items-center rounded-xl bg-white/10 ring-1 ring-white/25">
            <Crest className="size-[clamp(1.6rem,2.6vw,2.6rem)]" />
          </span>
          <div className="leading-tight">
            <h1 className="text-[clamp(1.5rem,2.6vw,2.75rem)] font-semibold">
              Kabarak University Medical Center
            </h1>
            <p className="text-[clamp(0.9rem,1.3vw,1.4rem)] text-brand-100">
              Waiting-room display
            </p>
          </div>
        </div>
        <div className="flex items-center gap-[2vw]">
          <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-1.5 text-[clamp(0.8rem,1.1vw,1.15rem)] font-medium">
            <span
              aria-hidden="true"
              className={`inline-block size-3 rounded-full ${
                offline ? "bg-status-missed" : "bg-status-complete pulse-dot"
              }`}
            />
            {offline ? "Offline" : "Live"}
          </span>
          <p className="text-[clamp(1.4rem,2.4vw,2.75rem)] font-semibold tabular-nums text-brand-100">
            {clock}
          </p>
        </div>
      </header>

      <main id="main" className="flex flex-1 flex-col px-[3vw] pb-[2.5vh] pt-[2vh]">
        <div className="grid grid-cols-[1fr_1.5fr] gap-4 border-b border-white/25 pb-[1.4vh] text-[clamp(1rem,1.6vw,1.75rem)] font-medium uppercase tracking-[0.12em] text-brand-100">
          <span>Token</span>
          <span>Please proceed to</span>
        </div>

        {/* Announced politely: a screen reader in the waiting area should not
            interrupt, but the board does update. */}
        <ul aria-live="polite" className="flex-1">
          {rows.map((row, index) => (
            <li
              key={row.token}
              className={`grid grid-cols-[1fr_1.5fr] items-center gap-4 border-b border-white/10 py-[1.6vh] ${
                index === 0 ? "-mx-[1.5vw] rounded-2xl bg-white/[0.06] px-[1.5vw]" : ""
              }`}
            >
              {/* Deliberately huge: this is read from across a waiting room. */}
              <span className="token-figure text-[clamp(2.5rem,6vw,6.5rem)] font-bold leading-none">
                {row.token}
              </span>
              <span className="flex items-center gap-[1.2vw] text-[clamp(1.6rem,4vw,4.5rem)] font-medium leading-none">
                <span aria-hidden="true" className="text-brand-100/70">
                  →
                </span>
                {row.destination}
              </span>
            </li>
          ))}
        </ul>

        {rows.length === 0 && (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
            <span className="grid size-[clamp(3.5rem,6vw,6rem)] place-items-center rounded-full bg-white/10">
              <Crest className="size-[clamp(2rem,3.5vw,3.5rem)]" />
            </span>
            <p className="text-[clamp(1.4rem,2.4vw,2.5rem)] text-brand-100">
              No patients are being called at the moment.
            </p>
          </div>
        )}
      </main>

      <footer className="flex items-center justify-between gap-4 border-t border-white/20 px-[3vw] py-[1.6vh] text-[clamp(0.9rem,1.3vw,1.4rem)] text-brand-100">
        {offline ? (
          <span className="text-priority-urgent-soft">
            Not connected — this board may be out of date. Please listen for
            staff calling tokens.
          </span>
        ) : (
          <span>Please watch for your token. Staff will also call it out.</span>
        )}

        {/* Kept small and in the footer: this screen is a wall display, and
            the way out matters to whoever set it up, not to the waiting room. */}
        <HomeLink className="shrink-0 text-base" />
      </footer>
    </div>
  );
}
