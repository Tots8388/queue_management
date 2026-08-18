"use client";

/**
 * A patient's own status (spec FR7).
 *
 * What this screen shows: token, current stage, next stage, people ahead, a
 * cautious waiting range, presence, a whole-journey progress indicator, and
 * when it last updated.
 *
 * What it must never show: the patient's priority category, anyone else's
 * token, or any clinical detail. The server does not send priority on this
 * channel; this component does not ask for it either.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  Brand,
  Button,
  ConnectionBanner,
  HomeLink,
  Skeleton,
  StatusPill,
  TokenFigure,
} from "@shared/ui/components/ui";
import { api } from "@shared/ui/lib/api";
import { contracts, presenceLabel } from "@shared/ui/lib/contracts";
import type { PatientStatus } from "@shared/ui/lib/types";
import { useQueueChannel } from "@shared/ui/lib/useQueueChannel";

/** The four service stages a patient passes through, in order. */
const JOURNEY = contracts.stages.filter((stage) => stage.order <= 4);

function CheckIcon({ className = "size-5" }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      className={`${className} shrink-0 fill-current`}
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

function ClockIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5 fill-current">
      <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm0 18a8 8 0 1 1 0-16 8 8 0 0 1 0 16Zm1-13h-2v6l5 3 1-1.7-4-2.3V7Z" />
    </svg>
  );
}

/**
 * The whole-journey progress bar. Reassurance by design: a patient can see how
 * far along they are, not just the single stage they are in.
 */
function StageProgress({ currentStage }: { currentStage: string | undefined }) {
  const currentOrder =
    contracts.stages.find((s) => s.key === currentStage)?.order ??
    (currentStage === "complete" ? 5 : 1);

  return (
    <ol className="flex items-start">
      {JOURNEY.map((stage, index) => {
        const done = stage.order < currentOrder;
        const active = stage.order === currentOrder;
        const state = done ? "done" : active ? "active" : "upcoming";

        return (
          <li
            key={stage.key}
            className="flex flex-1 flex-col items-center text-center"
          >
            <div className="flex w-full items-center">
              {/* left connector */}
              <span
                aria-hidden="true"
                className={`h-1 flex-1 rounded-full ${
                  index === 0
                    ? "opacity-0"
                    : done || active
                      ? "bg-brand-500"
                      : "bg-line"
                }`}
              />
              <span
                aria-hidden="true"
                className={`grid size-8 shrink-0 place-items-center rounded-full text-sm font-semibold ${
                  state === "done"
                    ? "bg-brand-600 text-white"
                    : state === "active"
                      ? "bg-brand-600 text-white ring-4 ring-brand-100"
                      : "border-2 border-line bg-surface text-ink-subtle"
                }`}
              >
                {state === "done" ? (
                  <CheckIcon className="size-4" />
                ) : (
                  stage.order
                )}
              </span>
              {/* right connector */}
              <span
                aria-hidden="true"
                className={`h-1 flex-1 rounded-full ${
                  index === JOURNEY.length - 1
                    ? "opacity-0"
                    : done
                      ? "bg-brand-500"
                      : "bg-line"
                }`}
              />
            </div>
            <span
              className={`mt-2 text-xs leading-tight ${
                active
                  ? "font-semibold text-brand-700"
                  : done
                    ? "text-ink-muted"
                    : "text-ink-subtle"
              }`}
            >
              {stage.label}
            </span>
            <span className="sr-only-focusable">
              {done ? "completed" : active ? "current stage" : "upcoming"}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export function PatientStatusView({ token }: { token: string }) {
  const { data, connection, resync } = useQueueChannel<PatientStatus>(
    `/ws/patient/${encodeURIComponent(token)}/`,
  );
  const [fallback, setFallback] = useState<PatientStatus | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [showHelp, setShowHelp] = useState(false);

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
  const loading = !status && !notFound;

  if (notFound && !status) {
    return (
      <div className="flex min-h-dvh flex-col bg-app">
        <PatientHeader />
        <main id="main" className="mx-auto w-full max-w-md flex-1 px-6 py-10">
          <div className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
            <span className="grid size-12 place-items-center rounded-full bg-priority-emergency-soft text-priority-emergency">
              <svg viewBox="0 0 24 24" className="size-6 fill-current" aria-hidden="true">
                <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 15h-2v-2h2v2Zm0-4h-2V7h2v6Z" />
              </svg>
            </span>
            <h1 className="mt-4 text-xl font-semibold">
              We could not find that token
            </h1>
            <p className="mt-2 text-ink-muted">
              A token belongs to the visit it was issued for, so one from an
              earlier visit will not work. Please check the slip you were given
              at reception, or ask at the desk.
            </p>
            <div className="mt-6">
              <Link
                href="/patient"
                className="inline-flex min-h-target items-center gap-2 rounded-lg border border-line bg-surface px-4 py-2.5 font-medium shadow-xs hover:bg-surface-muted"
              >
                ← Try another token
              </Link>
            </div>
          </div>
        </main>
        <PatientFooter />
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh flex-col bg-app">
      <PatientHeader />
      <div className="mx-auto w-full max-w-md px-4">
        <div className="mt-4">
          <ConnectionBanner state={connection} />
        </div>
      </div>

      <main id="main" className="mx-auto w-full max-w-md flex-1 px-4 py-4">
        {/* The token is the largest thing on the screen — it is what a patient
            is asked for and what they listen for. */}
        <section className="animate-fade-rise overflow-hidden rounded-2xl bg-brand-gradient px-6 py-8 text-center text-white shadow-brand">
          <h1 className="text-sm font-medium uppercase tracking-wide text-brand-100">
            Your queue token
          </h1>
          <p className="mt-2">
            <TokenFigure token={status?.token ?? token} />
          </p>
        </section>

        {/* Whole-journey progress — reassurance that they are moving forward. */}
        <section
          aria-label="Your progress through the clinic"
          className="mt-4 rounded-2xl border border-line bg-surface px-4 py-5 shadow-sm"
        >
          <StageProgress currentStage={status?.current_stage} />
        </section>

        {/* Live region: a patient watching the screen is told when their stage
            changes without having to notice it themselves. */}
        <div aria-live="polite" aria-atomic="true">
          <section className="mt-4 space-y-3">
            <div className="flex items-center gap-3 rounded-2xl border border-line bg-surface px-4 py-4 shadow-sm">
              <span className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-50 text-status-complete">
                <CheckIcon />
              </span>
              <div>
                <p className="text-sm text-ink-muted">Current stage</p>
                {loading ? (
                  <Skeleton className="mt-1 h-5 w-32" />
                ) : (
                  <p className="font-semibold">{status?.stage_label ?? "—"}</p>
                )}
              </div>
            </div>

            {status?.next_stage_label && (
              <div className="flex items-center gap-3 rounded-2xl border border-line bg-surface px-4 py-4 shadow-sm">
                <span
                  aria-hidden="true"
                  className="grid size-9 shrink-0 place-items-center rounded-full border-2 border-dashed border-line text-ink-subtle"
                >
                  →
                </span>
                <div>
                  <p className="text-sm text-ink-muted">Next stage</p>
                  <p className="font-semibold">{status.next_stage_label}</p>
                </div>
              </div>
            )}
          </section>

          <section className="mt-3 grid grid-cols-2 gap-3">
            <div className="rounded-2xl border border-line bg-surface px-4 py-4 text-center shadow-sm">
              <p className="text-sm text-ink-muted">Your position</p>
              {loading ? (
                <Skeleton className="mx-auto mt-2 h-9 w-16" />
              ) : (
                <p className="mt-1 flex items-center justify-center gap-2 text-3xl font-semibold">
                  {status?.people_ahead === null ||
                  status?.people_ahead === undefined
                    ? "—"
                    : status.people_ahead + 1}
                  <span aria-hidden="true" className="text-ink-subtle">
                    <PeopleIcon />
                  </span>
                </p>
              )}
              <p className="mt-1 text-sm text-ink-muted">
                {status?.people_ahead === 0
                  ? "You are next"
                  : status?.people_ahead
                    ? `${status.people_ahead} ahead of you`
                    : " "}
              </p>
            </div>

            <div className="rounded-2xl border border-line bg-surface px-4 py-4 text-center shadow-sm">
              <p className="text-sm text-ink-muted">Estimated waiting</p>
              {/* Always a range or an honest message — never a countdown, and
                  never a single figure that could read as a promise. The server
                  decides which; this only renders what it was told. */}
              {loading ? (
                <Skeleton className="mx-auto mt-2 h-8 w-24" />
              ) : (
                <p
                  className={`mt-1 font-semibold ${
                    status?.wait_range?.available ? "text-2xl" : "text-lg"
                  }`}
                >
                  {status?.wait_range?.text ?? "Wait time unavailable"}
                </p>
              )}
              <p className="mt-1 text-sm text-ink-muted">
                {status?.wait_range?.available
                  ? "A guide only — it may change"
                  : "We cannot give a reliable estimate right now"}
              </p>
            </div>
          </section>

          <section className="mt-3 rounded-2xl border border-line bg-surface px-4 py-4 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm text-ink-muted">Status</p>
                <p className="mt-1">
                  <StatusPill
                    status={status?.presence_status ?? "waiting"}
                    label={presenceLabel(status?.presence_status ?? "waiting")}
                  />
                </p>
              </div>
              {status?.last_updated && (
                <p className="flex items-center gap-1.5 text-sm text-ink-subtle">
                  <ClockIcon />
                  {new Date(status.last_updated).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </p>
              )}
            </div>
          </section>
        </div>

        <div className="mt-6 space-y-3">
          <Button onClick={resync} fullWidth size="lg">
            Refresh
          </Button>
          {/*
            The prototypes show a "Request assistance" button. It deliberately
            does not send anything: there is no staff alerting channel in v1,
            and a button that silently does nothing is worse than no button —
            a patient in difficulty would press it and wait. So it opens plain
            guidance towards the help that actually exists, the reception desk.
          */}
          <Button
            variant="secondary"
            fullWidth
            size="lg"
            onClick={() => setShowHelp((open) => !open)}
          >
            Request assistance
          </Button>

          {showHelp && (
            <div
              role="status"
              className="rounded-xl border border-line bg-surface px-4 py-4 text-sm"
            >
              <p className="font-medium">Please speak to a member of staff.</p>
              <p className="mt-2 text-ink-muted">
                Go to the reception desk and show them your token. This button
                does not call anyone — staff are not alerted by this screen.
              </p>
              <p className="mt-2 text-ink-muted">
                If you feel very unwell or your condition worsens, tell a member
                of staff straight away. Do not wait for your token to be called.
              </p>
            </div>
          )}
        </div>

        <p className="mt-6 text-center text-sm text-ink-muted">
          If you need to step away, please tell a member of staff so you keep
          your place.
        </p>

        {/*
          The spec gives each priority level a patient-facing message, and the
          evaluation asks whether patients can explain routine versus emergency
          order. This is shown identically to every patient, so it teaches the
          policy without disclosing anybody's own category.
        */}
        <details className="group mt-6 rounded-2xl border border-line bg-surface px-4 py-1 shadow-sm">
          <summary className="flex min-h-target cursor-pointer list-none items-center justify-between py-2 font-medium">
            Why might someone be seen before me?
            <span
              aria-hidden="true"
              className="text-ink-subtle transition-transform group-open:rotate-180"
            >
              ⌄
            </span>
          </summary>
          <div className="space-y-2 pb-3 text-sm text-ink-muted">
            <p>
              Within each stage, patients are normally seen in the order they
              checked in.
            </p>
            <p>
              Emergency cases may be served immediately, and urgent cases may be
              served before routine ones. A nurse or doctor makes that decision,
              never the system, and every such decision is recorded.
            </p>
            <p>
              This means the queue can move at different speeds at different
              times of day.
            </p>
          </div>
        </details>
      </main>

      <PatientFooter />
    </div>
  );
}

function PatientHeader() {
  return (
    <header className="bg-brand-gradient px-4 py-4 text-white shadow-brand">
      <div className="mx-auto flex max-w-md items-center justify-between gap-3">
        <Brand compact />
        <HomeLink />
      </div>
    </header>
  );
}

function PatientFooter() {
  return (
    <footer className="mt-2 space-y-1 px-6 py-6 text-center text-sm text-ink-muted">
      <p>Thank you for your patience.</p>
      <p className="text-ink-subtle">
        Prototype with fictional data only. Not for clinical use.
      </p>
    </footer>
  );
}
