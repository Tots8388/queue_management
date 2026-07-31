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

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth";
import type { RoleKey } from "@/lib/contracts";

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
  const { user, loading, signOut } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    // Someone who followed a bookmark to another station's dashboard is sent to
    // their own rather than shown a wall of refusals.
    if (user.dashboard && !pathname.startsWith(user.dashboard)) {
      router.replace(user.dashboard);
    }
  }, [user, loading, pathname, router]);

  if (loading || !user) {
    return (
      <div className="flex min-h-full items-center justify-center">
        <p role="status" className="text-ink-muted">
          Loading your dashboard…
        </p>
      </div>
    );
  }

  const theme = themeFor(user.role);

  return (
    <div className="flex min-h-full">
      <nav
        aria-label="Station"
        className={`hidden w-56 shrink-0 flex-col justify-between px-4 py-6 text-white sm:flex ${theme.sidebar}`}
      >
        <div>
          <p className="px-2 text-sm font-semibold uppercase tracking-wide">
            Kabarak
          </p>
          <p className="px-2 text-sm opacity-90">Medical Center</p>

          <ul className="mt-8 space-y-1">
            <li>
              <span className="block rounded-lg bg-white/15 px-3 py-2.5 font-medium">
                {user.role_label}
              </span>
            </li>
            <li>
              <Link
                href="/display"
                target="_blank"
                className="block rounded-lg px-3 py-2.5 hover:bg-white/10"
              >
                Waiting-room board
              </Link>
            </li>
          </ul>
        </div>

        <button
          type="button"
          onClick={signOut}
          className="rounded-lg px-3 py-2.5 text-left hover:bg-white/10"
        >
          Sign out
        </button>
      </nav>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-surface px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold">{stationTitle(user.role)}</h1>
            {user.default_counter && (
              <p className="text-sm text-ink-muted">
                {user.default_counter.name}
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-ink-muted">
              {user.first_name || user.username} · {user.role_label}
            </span>
            <button
              type="button"
              onClick={signOut}
              className="rounded-lg border border-line px-3 py-2 text-sm sm:hidden"
            >
              Sign out
            </button>
          </div>
        </header>

        <main id="main" className="flex-1 px-6 py-6">
          {children}
        </main>
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
