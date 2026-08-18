"use client";

/**
 * The clinic tracking board (spec FR8).
 *
 * Not a call-forward list: every patient currently in the building appears
 * here, grouped under the stage they are at, from check-in until pharmacy is
 * finished with them. A patient can find their own token and see how far along
 * they are without asking at a desk.
 *
 * The rule it exists to honour is absolute — no names, no priority categories,
 * no diagnoses, no prescriptions. The server sends token, stage and
 * destination, and this component renders those and nothing else. The columns
 * are in arrival order rather than service order for the same reason: a list
 * ordered by who is next would let the room infer who has been given a
 * clinical priority.
 *
 * Everything scales with the viewport (clamp / vw-relative sizes) so the same
 * page fills a 55" wall screen and still holds together on a laptop.
 */

import { useEffect, useState } from "react";

import { Crest, HomeLink } from "@shared/ui/components/ui";
import { api } from "@shared/ui/lib/api";
import { contracts } from "@shared/ui/lib/contracts";
import type { DisplayRow, DisplayState } from "@shared/ui/lib/types";
import { useQueueChannel } from "@shared/ui/lib/useQueueChannel";

/**
 * The stages that are places in the clinic. "complete" is not one — a patient
 * who has finished has left, and the board drops them.
 */
const COLUMNS = contracts.stages.filter((stage) => stage.key !== "complete");

/**
 * How many tokens a column shows before it stops and counts the rest.
 *
 * A column that kept growing would shrink its own text until nobody across the
 * room could read any of it, which fails everybody rather than just the
 * overflow. Better to stay legible and say plainly how many are not shown.
 */
const PER_COLUMN = 8;

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
              Everyone in the clinic, and where they are
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
        {rows.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
            <span className="grid size-[clamp(3.5rem,6vw,6rem)] place-items-center rounded-full bg-white/10">
              <Crest className="size-[clamp(2rem,3.5vw,3.5rem)]" />
            </span>
            <p className="text-[clamp(1.4rem,2.4vw,2.5rem)] text-brand-100">
              Nobody is in the clinic at the moment.
            </p>
          </div>
        ) : (
          /* Announced politely: a screen reader in the waiting area should not
             interrupt, but the board does update. */
          <div
            aria-live="polite"
            className="grid flex-1 auto-rows-fr gap-[1.5vw] sm:grid-cols-2 lg:grid-cols-4"
          >
            {COLUMNS.map((column) => (
              <StageColumn
                key={column.key}
                label={column.label}
                rows={rows.filter((row) => row.stage === column.key)}
              />
            ))}
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
          <span>
            Find your token to see where you are. A highlighted token is being
            called now — staff will also call it out.
          </span>
        )}

        {/* Kept small and in the footer: this screen is a wall display, and
            the way out matters to whoever set it up, not to the waiting room. */}
        <HomeLink className="shrink-0 text-base" />
      </footer>
    </div>
  );
}

/**
 * One place in the clinic, and the tokens currently there.
 *
 * The heading carries the count even when the list is truncated, so a column
 * never understates how many people are at a stage — the number is the honest
 * part, the list is the part that has to fit on a screen.
 */
function StageColumn({ label, rows }: { label: string; rows: DisplayRow[] }) {
  const shown = rows.slice(0, PER_COLUMN);
  const hidden = rows.length - shown.length;

  return (
    <section className="flex min-w-0 flex-col rounded-2xl bg-white/[0.06] p-[1.2vw] ring-1 ring-white/10">
      <h2 className="flex items-baseline justify-between gap-2 border-b border-white/15 pb-[1vh] text-[clamp(0.95rem,1.5vw,1.6rem)] font-medium uppercase tracking-[0.1em] text-brand-100">
        <span className="truncate">{label}</span>
        <span
          className="shrink-0 tabular-nums"
          aria-label={`${rows.length} ${rows.length === 1 ? "patient" : "patients"} at ${label}`}
        >
          {rows.length}
        </span>
      </h2>

      {rows.length === 0 ? (
        <p className="flex flex-1 items-center justify-center text-[clamp(0.9rem,1.2vw,1.25rem)] text-brand-100/60">
          Nobody here
        </p>
      ) : (
        <ul className="mt-[1vh] flex-1 space-y-[0.8vh]">
          {shown.map((row) => (
            <li
              key={row.token}
              /* A token that has just been called is lifted out of the column.
                 It is the only state the board emphasises, and it is why
                 someone looks up at it in the first place. */
              className={`rounded-xl px-[0.8vw] py-[0.7vh] ${
                row.called ? "bg-white text-brand-900" : ""
              }`}
            >
              {/* Never wrapped. The token is the one thing a patient scans the
                  wall for, and a token broken across two lines is a token they
                  have to reassemble before they can recognise it. */}
              <span className="token-figure block whitespace-nowrap text-[clamp(1.5rem,2.8vw,3rem)] font-bold leading-none">
                {row.token}
              </span>
              {/* The desk or room, shown only once it says more than the
                  column heading already does — a patient waiting for vitals is
                  just "at vitals", but one called to a specific window needs to
                  know which.

                  On its own line rather than beside the token: a column is
                  narrow, and "Consultation Roo…" is worse than no room at all
                  when there are two consultation rooms to choose between. */}
              {row.destination !== label && (
                <span
                  className={`mt-[0.3vh] block text-[clamp(0.8rem,1.15vw,1.2rem)] font-medium ${
                    row.called ? "text-brand-700" : "text-brand-100/80"
                  }`}
                >
                  {row.destination}
                </span>
              )}
            </li>
          ))}

          {hidden > 0 && (
            <li className="px-[0.8vw] pt-[0.5vh] text-[clamp(0.85rem,1.15vw,1.2rem)] text-brand-100/70">
              +{hidden} more
            </li>
          )}
        </ul>
      )}
    </section>
  );
}
