"use client";

/**
 * Shared interface pieces.
 *
 * Two accessibility rules run through all of them, both from WCAG 2.2 and both
 * non-negotiable in a busy clinic:
 *
 *   - colour is never the only signal; every coloured dot or tag has a text
 *     label beside it;
 *   - anything interactive clears the 44px minimum target set in globals.css.
 */

import type { ReactNode } from "react";

import type { ConnectionState } from "@/lib/useQueueChannel";

/** The anonymous visit token — the largest thing on any screen showing it. */
export function TokenFigure({
  token,
  size = "large",
}: {
  token: string;
  size?: "large" | "medium" | "small";
}) {
  const scale = {
    large: "text-6xl sm:text-7xl",
    medium: "text-4xl",
    small: "text-2xl",
  }[size];

  return (
    <span className={`token-figure font-semibold tabular-nums ${scale}`}>
      {token}
    </span>
  );
}

/**
 * Priority tag — STAFF SCREENS ONLY.
 *
 * The patient view and the public display must never render this. Spec FR8:
 * urgency categories are not exposed publicly.
 */
export function PriorityTag({
  priority,
  label,
}: {
  priority: string;
  label: string;
}) {
  const style =
    {
      emergency:
        "bg-priority-emergency-soft text-priority-emergency border-priority-emergency",
      urgent: "bg-priority-urgent-soft text-priority-urgent border-priority-urgent",
      routine:
        "bg-priority-routine-soft text-priority-routine border-priority-routine",
    }[priority] ?? "bg-surface-muted text-ink-muted border-line";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-sm font-medium ${style}`}
    >
      {/* Decoration only — the label beside it carries the meaning. */}
      <span
        aria-hidden="true"
        className="inline-block size-2 rounded-full bg-current"
      />
      {label}
    </span>
  );
}

export function StatusPill({
  status,
  label,
}: {
  status: string;
  label: string;
}) {
  const tone =
    {
      waiting: "text-status-waiting",
      called: "text-status-in-progress",
      recalled: "text-status-in-progress",
      resumed: "text-status-complete",
      complete: "text-status-complete",
      in_progress: "text-status-in-progress",
      temporarily_away: "text-status-waiting",
      missed_turn: "text-status-missed",
    }[status] ?? "text-ink-muted";

  return (
    <span className={`inline-flex items-center gap-2 text-sm ${tone}`}>
      <span
        aria-hidden="true"
        className="inline-block size-2.5 rounded-full bg-current"
      />
      {label}
    </span>
  );
}

export function Button({
  children,
  onClick,
  variant = "primary",
  type = "button",
  disabled,
  fullWidth,
  accent,
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "danger";
  type?: "button" | "submit";
  disabled?: boolean;
  fullWidth?: boolean;
  /** Role colour, so a dashboard's primary action matches its station. */
  accent?: string;
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 " +
    "font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

  const styles = {
    primary: accent
      ? `${accent} text-white hover:brightness-110`
      : "bg-brand-600 text-white hover:bg-brand-700",
    secondary: "border border-line bg-surface text-ink hover:bg-surface-muted",
    danger: "bg-priority-emergency text-white hover:brightness-110",
  }[variant];

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${base} ${styles} ${fullWidth ? "w-full" : ""}`}
    >
      {children}
    </button>
  );
}

/**
 * Connection state, stated plainly.
 *
 * "The screen might be out of date" is operational information: it is the
 * trigger for the manual paper fallback, so it is never hidden or softened.
 */
export function ConnectionBanner({ state }: { state: ConnectionState }) {
  if (state === "live") return null;

  const offline = state === "offline";

  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex items-center gap-2 border-l-4 px-4 py-3 text-sm ${
        offline
          ? "border-status-missed bg-priority-emergency-soft text-priority-emergency"
          : "border-status-waiting bg-priority-urgent-soft text-priority-urgent"
      }`}
    >
      <span aria-hidden="true" className="inline-block size-2.5 rounded-full bg-current" />
      {offline
        ? "Not connected to the queue server. This list may be out of date — use the paper fallback if it does not reconnect."
        : "Connecting to the queue server…"}
    </div>
  );
}

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-xl border border-line bg-surface p-5 ${className}`}>
      {children}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <p className="rounded-lg border border-dashed border-line px-4 py-10 text-center text-ink-muted">
      {message}
    </p>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p
      role="alert"
      className="rounded-lg border-l-4 border-priority-emergency bg-priority-emergency-soft px-4 py-3 text-sm text-priority-emergency"
    >
      {message}
    </p>
  );
}
