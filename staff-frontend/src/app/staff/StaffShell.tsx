"use client";

/**
 * The staff dashboard shell — role-coloured sidebar, top bar, sign-out.
 *
 * Each station has its own colour, taken from the approved prototypes, so a
 * member of staff can tell from across the room which screen belongs to which
 * station. Colour is never the only signal: the role name is written out in the
 * top bar as well.
 *
 * The guard here keeps people out of the wrong dashboard, but it is convenience
 * and clarity, not security — every action is authorised again on the server.
 */

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore } from "react";

import { Button, Crest, Spinner } from "@shared/ui/components/ui";
import { patientAppUrl } from "@shared/ui/lib/config";
import { useAuth } from "@/lib/auth";
import type { RoleKey } from "@shared/ui/lib/contracts";

// The patient app's address never changes while the page is open, so there is
// nothing to subscribe to — this exists only to satisfy useSyncExternalStore.
const subscribeToNothing = () => () => {};

type Theme = {
  sidebar: string;
  accent: string;
  soft: string;
};

export const ROLE_THEME: Record<string, Theme> = {
  registration_clerk: {
    sidebar: "bg-role-reception",
    accent: "bg-role-reception",
    soft: "bg-role-reception-soft",
  },
  nurse_vitals: {
    sidebar: "bg-role-nurse",
    accent: "bg-role-nurse",
    soft: "bg-role-nurse-soft",
  },
  clinician: {
    sidebar: "bg-role-clinician",
    accent: "bg-role-clinician",
    soft: "bg-role-clinician-soft",
  },
  pharmacist: {
    sidebar: "bg-role-pharmacy",
    accent: "bg-role-pharmacy",
    soft: "bg-role-pharmacy-soft",
  },
};

const FALLBACK_THEME: Theme = {
  sidebar: "bg-brand-700",
  accent: "bg-brand-600",
  soft: "bg-brand-50",
};

export function themeFor(role: RoleKey | undefined): Theme {
  return (role && ROLE_THEME[role]) || FALLBACK_THEME;
}

export function StaffShell({ children }: { children: React.ReactNode }) {
  const { user, loading, offline, retry, signOut } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  // The patient app's address is read from window.location, so the server has
  // no way to render it correctly. Subscribing to nothing and returning null
  // on the server is how a browser-only value is read without the markup
  // disagreeing at hydration.
  const boardUrl = useSyncExternalStore(
    subscribeToNothing,
    () => patientAppUrl(),
    () => null,
  );

  useEffect(() => {
    if (loading) return;
    // Being unable to reach the server is not being signed out. Sending staff
    // to the sign-in screen here would read as a rejected password and send
    // them hunting for the wrong problem.
    if (offline) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    // Someone who followed a bookmark to another station's dashboard is sent to
    // their own rather than shown a wall of refusals.
    if (user.dashboard && !pathname.startsWith(user.dashboard)) {
      router.replace(user.dashboard);
    }
  }, [user, loading, offline, pathname, router]);

  // The server is unreachable but the session is still good. Say so, and say
  // what to do about it — this is the trigger for the paper fallback, and it is
  // the one screen that must never be mistaken for "your password was wrong".
  if (!loading && offline && !user) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-app px-6 text-center">
        <div
          role="alert"
          className="max-w-md rounded-xl border-l-4 border-status-missed bg-priority-emergency-soft px-5 py-4 text-priority-emergency"
        >
          <p className="font-semibold">Cannot reach the queue server</p>
          <p className="mt-1 text-sm">
            You are still signed in. Use the paper fallback and keep each
            patient&apos;s arrival time, then reconcile the sheet when the
            server returns.
          </p>
        </div>
        <Button variant="secondary" onClick={retry}>
          Try again
        </Button>
      </div>
    );
  }

  if (loading || !user) {
    return (
      <div
        role="status"
        className="flex min-h-dvh flex-col items-center justify-center gap-3 bg-app text-ink-muted"
      >
        <span className="text-brand-600">
          <Spinner className="size-7" />
        </span>
        <p>Loading your dashboard…</p>
      </div>
    );
  }

  const theme = themeFor(user.role);
  const initials = (user.first_name || user.username || "?")
    .slice(0, 1)
    .toUpperCase();

  return (
    // min-h-dvh, not min-h-full: without an ancestor of resolved height a
    // percentage min-height collapses to the content, which on a tall terminal
    // cuts the station sidebar off midway down the screen.
    <div className="flex min-h-dvh bg-app">
      <nav
        aria-label="Station"
        className={`hidden w-60 shrink-0 flex-col justify-between px-4 py-6 text-white shadow-lg sm:flex ${theme.sidebar}`}
      >
        <div>
          <div className="flex items-center gap-3 px-2">
            <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-white/15 ring-1 ring-white/25">
              <Crest className="size-7" />
            </span>
            <div className="leading-tight">
              <p className="text-sm font-semibold">Kabarak</p>
              <p className="text-xs opacity-80">Medical Center</p>
            </div>
          </div>

          <p className="mt-8 px-2 text-xs font-semibold uppercase tracking-wider opacity-70">
            Your station
          </p>
          <ul className="mt-2 space-y-1">
            <li>
              <span className="flex items-center gap-2 rounded-lg bg-white/15 px-3 py-2.5 font-medium ring-1 ring-inset ring-white/15">
                <span aria-hidden="true" className="size-2 rounded-full bg-white" />
                {user.role_label}
              </span>
            </li>
          </ul>

          <p className="mt-6 px-2 text-xs font-semibold uppercase tracking-wider opacity-70">
            Shortcuts
          </p>
          <ul className="mt-2 space-y-1">
            {/* The board belongs to the patient app on its own port, so this is
                a full URL rather than a path — and it is only rendered once
                mounted, because the address is read from the browser. There is
                no "Home" beside it any more: this application starts at the
                sign-in screen and the patient app is not somewhere staff are
                being sent. */}
            {boardUrl && (
              <li>
                <a
                  href={`${boardUrl}/display`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-between rounded-lg px-3 py-2.5 hover:bg-white/10"
                >
                  Waiting-room board
                  <span aria-hidden="true" className="opacity-70">
                    ↗
                  </span>
                </a>
              </li>
            )}
          </ul>
        </div>

        <button
          type="button"
          onClick={signOut}
          className="flex items-center gap-2 rounded-lg px-3 py-2.5 text-left font-medium hover:bg-white/10"
        >
          <svg viewBox="0 0 24 24" className="size-5 shrink-0" fill="none" aria-hidden="true">
            <path
              d="M15 12H4m0 0 3.5-3.5M4 12l3.5 3.5M14 5h3a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-3"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Sign out
        </button>
      </nav>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex flex-wrap items-center justify-between gap-3 border-b border-line bg-surface/95 px-6 py-3.5 shadow-xs backdrop-blur">
          <div className="flex items-center gap-3">
            <span
              aria-hidden="true"
              className={`grid size-9 place-items-center rounded-lg text-white sm:hidden ${theme.accent}`}
            >
              <Crest className="size-6" />
            </span>
            <div>
              <h1 className="text-lg font-semibold leading-tight">
                {stationTitle(user.role)}
              </h1>
              {user.default_counter && (
                <p className="text-sm text-ink-muted">
                  {user.default_counter.name}
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden items-center gap-2.5 sm:flex">
              <span
                aria-hidden="true"
                className={`grid size-8 place-items-center rounded-full text-sm font-semibold text-white ${theme.accent}`}
              >
                {initials}
              </span>
              <span className="text-sm">
                <span className="font-medium">
                  {user.first_name || user.username}
                </span>
                <span className="text-ink-muted"> · {user.role_label}</span>
              </span>
            </span>
            <button
              type="button"
              onClick={signOut}
              className="rounded-lg border border-line px-3 py-2 text-sm font-medium shadow-xs hover:bg-surface-muted sm:hidden"
            >
              Sign out
            </button>
          </div>
        </header>

        <main id="main" className="flex-1 px-6 py-6">
          {children}
        </main>

        <footer className="border-t border-line px-6 py-4 text-sm text-ink-subtle">
          Prototype with fictional data only. Not for clinical use.
        </footer>
      </div>
    </div>
  );
}

function stationTitle(role: RoleKey): string {
  return (
    {
      registration_clerk: "Reception Dashboard",
      nurse_vitals: "Vital Signs Dashboard",
      clinician: "Consultation Dashboard",
      pharmacist: "Pharmacy Dashboard",
    }[role] ?? "Dashboard"
  );
}
