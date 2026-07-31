"use client";

/**
 * A patient's own status (spec FR7).
 *
 * What this screen shows: token, current stage, next stage, people ahead, a
 * cautious waiting range, presence, and when it last updated.
 *
 * What it must never show: the patient's priority category, anyone else's
 * token, or any clinical detail. The server does not send priority on this
 * channel; this component does not ask for it either.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button, ConnectionBanner, StatusPill, TokenFigure } from "@/components/ui";
import { api } from "@/lib/api";
import { presenceLabel } from "@/lib/contracts";
import type { PatientStatus } from "@/lib/types";
import { useQueueChannel } from "@/lib/useQueueChannel";

function CheckIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      className="size-5 shrink-0 fill-current"
    >
      <path d="M8.2 13.6 4.6 10l-1.2 1.2 4.8 4.8 9-9L16 5.8z" />
    </svg>
  );
}

function PeopleIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5 fill-current">
      <path d="M16 11a3 3 0 1 0-3-3 3 3 0 0 0 3 3Zm-8 0a3 3 0 1 0-3-3 3 3 0 0 0 3 3Zm0 2c-2.3 0-7 1.2-7 3.5V19h9v-2.5c0-.9.4-1.7 1-2.3A12 12 0 0 0 8 13Zm8 0c-.7 0-1.5.1-2.3.3a4 4 0 0 1 1.3 2.9V19h8v-2.5C23 14.2 18.3 13 16 13Z" />
    </svg>
  );
}

export function PatientStatusView({ token }: { token: string }) {
  const { data, connection, resync } = useQueueChannel<PatientStatus>(
    `/ws/patient/${encodeURIComponent(token)}/`,
  );
  const [fallback, setFallback] = useState<PatientStatus | null>(null);
  const [notFound, setNotFound] = useState(false);

  // The socket is the live path, but a patient on a weak connection should
  // still see something. Fetch once over HTTP as well.
  useEffect(() => {
    let cancelled = false;

    api<PatientStatus>(`patient/${encodeURIComponent(token)}/`, {
      authenticated: false,
    })
      .then((status) => !cancelled && setFallback(status))
      .catch((error) => {
        if (!cancelled && error?.status === 404) setNotFound(true);
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  const status = data ?? fallback;

  if (notFound && !status) {
    return (
      <div className="flex min-h-full flex-col">
        <PatientHeader />
        <main id="main" className="mx-auto w-full max-w-md flex-1 px-6 py-10">
          <h1 className="text-xl font-semibold">We could not find that token</h1>
          <p className="mt-3 text-ink-muted">
            Tokens are issued fresh each day, so a token from a previous visit
            will not work. Please check the slip you were given today, or ask at
            the reception desk.
          </p>
          <div className="mt-6">
            <Link
              href="/patient"
              className="inline-flex min-h-target items-center rounded-lg border border-line px-4 py-2.5 font-medium"
            >
              Try another token
            </Link>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-full flex-col">
      <PatientHeader />
      <ConnectionBanner state={connection} />

      <main id="main" className="mx-auto w-full max-w-md flex-1 px-4 py-6">
        {/* The token is the largest thing on the screen — it is what a patient
            is asked for and what they listen for. */}
        <section className="rounded-xl bg-brand-600 px-6 py-8 text-center text-white">
          <h1 className="text-sm font-medium uppercase tracking-wide text-brand-100">
            Your queue token
          </h1>
          <p className="mt-2">
            <TokenFigure token={status?.token ?? token} />
          </p>
        </section>

        {/* Live region: a patient watching the screen is told when their stage
            changes without having to notice it themselves. */}
        <div aria-live="polite" aria-atomic="true">
          <section className="mt-4 space-y-3">
            <div className="flex items-center gap-3 rounded-xl border border-line bg-surface px-4 py-4">
              <span className="text-status-complete">
                <CheckIcon />
              </span>
              <div>
                <p className="text-sm text-ink-muted">Current stage</p>
                <p className="font-semibold">{status?.stage_label ?? "—"}</p>
              </div>
            </div>

            {status?.next_stage_label && (
              <div className="flex items-center gap-3 rounded-xl border border-line bg-surface px-4 py-4">
                <span
                  aria-hidden="true"
                  className="size-5 shrink-0 rounded-full border-2 border-line"
                />
                <div>
                  <p className="text-sm text-ink-muted">Next stage</p>
                  <p className="font-semibold">{status.next_stage_label}</p>
                </div>
              </div>
            )}
          </section>

          <section className="mt-4 grid grid-cols-2 gap-3">
            <div className="rounded-xl border border-line bg-surface px-4 py-4 text-center">
              <p className="text-sm text-ink-muted">Your position</p>
              <p className="mt-1 flex items-center justify-center gap-2 text-3xl font-semibold">
                {status?.people_ahead === null || status?.people_ahead === undefined
                  ? "—"
                  : status.people_ahead + 1}
                <span aria-hidden="true" className="text-ink-muted">
                  <PeopleIcon />
                </span>
              </p>
              <p className="mt-1 text-sm text-ink-muted">
                {status?.people_ahead === 0
                  ? "You are next"
                  : status?.people_ahead
                    ? `${status.people_ahead} ahead of you`
                    : " "}
              </p>
            </div>

            <div className="rounded-xl border border-line bg-surface px-4 py-4 text-center">
              <p className="text-sm text-ink-muted">Estimated waiting</p>
              {/* Always a range or an honest "unavailable" — never a countdown,
                  and never a promise. */}
              <p className="mt-1 text-2xl font-semibold">
                {status?.wait_range?.available
                  ? status.wait_range.text
                  : "Unavailable"}
              </p>
              <p className="mt-1 text-sm text-ink-muted">
                {status?.wait_range?.available
                  ? "This is a guide, not a promise"
                  : "Not enough information yet"}
              </p>
            </div>
          </section>

          <section className="mt-4 rounded-xl border border-line bg-surface px-4 py-4">
            <p className="text-sm text-ink-muted">Status</p>
            <p className="mt-1">
              <StatusPill
                status={status?.presence_status ?? "waiting"}
                label={presenceLabel(status?.presence_status ?? "waiting")}
              />
            </p>
            {status?.last_updated && (
              <p className="mt-3 text-sm text-ink-muted">
                Last updated{" "}
                {new Date(status.last_updated).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </p>
            )}
          </section>
        </div>

        <div className="mt-6 space-y-3">
          <Button onClick={resync} fullWidth>
            Refresh
          </Button>
          <Button variant="secondary" fullWidth>
            Request assistance
          </Button>
        </div>

        <p className="mt-6 text-center text-sm text-ink-muted">
          If you need to step away, please tell a member of staff so you keep
          your place.
        </p>
      </main>

      <footer className="px-6 py-6 text-center text-sm text-ink-muted">
        Thank you for your patience.
      </footer>
    </div>
  );
}

function PatientHeader() {
  return (
    <header className="bg-brand-700 px-4 py-4 text-white">
      <div className="mx-auto flex max-w-md items-center">
        <span className="font-semibold">Kabarak Medical Center</span>
      </div>
    </header>
  );
}
