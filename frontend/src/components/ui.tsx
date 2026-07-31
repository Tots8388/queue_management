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
 *
 * The visual language is deliberately restrained: soft elevation, one calm
 * Kabarak-green accent, generous type. Depth and motion are there to make the
 * product feel real and cared-for, never to decorate.
 */

import Link from "next/link";
import type { ReactNode } from "react";

import type { ConnectionState } from "@/lib/useQueueChannel";

/** Tiny className joiner — avoids a dependency for a one-line need. */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/**
 * Kabarak crest mark.
 *
 * A stylised shield with a medical cross — a clean, scalable stand-in that
 * inherits `currentColor`, so it sits correctly on the green headers, the
 * coloured staff sidebars and on white. Not the official university crest;
 * swap in the real asset when it is available (see report notes).
 */
export function Crest({ className = "size-8" }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 32 32"
      className={className}
      fill="none"
    >
      <path
        d="M16 2.5 27 6.2v9.1c0 6.9-4.6 12-11 14.2-6.4-2.2-11-7.3-11-14.2V6.2L16 2.5Z"
        fill="currentColor"
        opacity="0.16"
      />
      <path
        d="M16 2.5 27 6.2v9.1c0 6.9-4.6 12-11 14.2-6.4-2.2-11-7.3-11-14.2V6.2L16 2.5Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M16 10v10M11 15h10"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Wordmark lockup used in headers and sidebars. */
export function Brand({
  subtitle,
  compact = false,
  className = "",
}: {
  subtitle?: string;
  compact?: boolean;
  className?: string;
}) {
  return (
    <span className={cx("flex items-center gap-3", className)}>
      <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-white/15 ring-1 ring-white/25">
        <Crest className="size-6" />
      </span>
      <span className="flex flex-col leading-tight">
        <span className={cx("font-semibold", compact ? "text-sm" : "text-base")}>
          Kabarak {compact ? "" : "University "}Medical Center
        </span>
        {subtitle && (
          <span className="text-xs font-medium uppercase tracking-wide opacity-80">
            {subtitle}
          </span>
        )}
      </span>
    </span>
  );
}

/**
 * "Home" — the way back to the entry page, from anywhere.
 *
 * Present on every screen a patient or visitor can reach, because someone who
 * arrives on the wrong one should never have to know a URL to get out of it.
 *
 * `tone="light"` for the coloured headers (patient view, board, sign-in);
 * `tone="dark"` for pages on a pale background.
 */
export function HomeLink({
  tone = "light",
  label = "Home",
  className = "",
}: {
  tone?: "light" | "dark";
  label?: string;
  className?: string;
}) {
  const styles =
    tone === "light"
      ? "text-white/85 hover:bg-white/10 hover:text-white"
      : "text-ink-muted hover:bg-surface-muted hover:text-ink";

  return (
    <Link
      href="/"
      className={cx(
        "inline-flex min-h-target items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium",
        styles,
        className,
      )}
    >
      <span aria-hidden="true">←</span>
      {label}
    </Link>
  );
}

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
        "bg-priority-emergency-soft text-priority-emergency ring-priority-emergency/25",
      urgent:
        "bg-priority-urgent-soft text-priority-urgent ring-priority-urgent/25",
      routine:
        "bg-priority-routine-soft text-priority-routine ring-priority-routine/20",
    }[priority] ?? "bg-surface-muted text-ink-muted ring-line";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-sm font-medium ring-1 ring-inset ${style}`}
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

  // "In progress" states get a soft pulse so a glance across a busy dashboard
  // catches what is live right now.
  const live = status === "called" || status === "in_progress" || status === "recalled";

  return (
    <span className={`inline-flex items-center gap-2 text-sm font-medium ${tone}`}>
      <span
        aria-hidden="true"
        className={cx(
          "inline-block size-2.5 rounded-full bg-current",
          live && "pulse-dot",
        )}
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
  size = "md",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "danger" | "ghost";
  type?: "button" | "submit";
  disabled?: boolean;
  fullWidth?: boolean;
  /** Role colour, so a dashboard's primary action matches its station. */
  accent?: string;
  size?: "sm" | "md" | "lg";
}) {
  const base =
    "relative inline-flex items-center justify-center gap-2 rounded-lg font-medium " +
    "transition-[background-color,box-shadow,transform,filter] duration-150 " +
    "active:translate-y-px disabled:pointer-events-none disabled:opacity-50 " +
    "focus-visible:outline-none";

  const sizing = {
    sm: "px-3 py-2 text-sm",
    md: "px-4 py-2.5",
    lg: "px-5 py-3 text-lg",
  }[size];

  const styles = {
    primary: accent
      ? `${accent} text-white shadow-sm hover:brightness-110 hover:shadow-md`
      : "bg-brand-600 text-white shadow-sm hover:bg-brand-700 hover:shadow-md",
    secondary:
      "border border-line bg-surface text-ink shadow-xs hover:bg-surface-muted hover:border-line-strong",
    danger:
      "bg-priority-emergency text-white shadow-sm hover:brightness-110 hover:shadow-md",
    ghost: "text-ink hover:bg-surface-muted",
  }[variant];

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={cx(base, sizing, styles, fullWidth && "w-full")}
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
      className={cx(
        "flex items-center gap-2.5 rounded-lg border-l-4 px-4 py-3 text-sm font-medium shadow-xs",
        offline
          ? "border-status-missed bg-priority-emergency-soft text-priority-emergency"
          : "border-status-waiting bg-priority-urgent-soft text-priority-urgent",
      )}
    >
      <span
        aria-hidden="true"
        className={cx(
          "inline-block size-2.5 shrink-0 rounded-full bg-current",
          !offline && "pulse-dot",
        )}
      />
      {offline
        ? "Not connected to the queue server. This list may be out of date — use the paper fallback if it does not reconnect."
        : "Connecting to the queue server…"}
    </div>
  );
}

export function Card({
  children,
  className = "",
  interactive = false,
}: {
  children: ReactNode;
  className?: string;
  interactive?: boolean;
}) {
  return (
    <div
      className={cx(
        "rounded-xl border border-line bg-surface p-5 shadow-sm",
        interactive && "card-interactive",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function EmptyState({
  message,
  icon,
}: {
  message: string;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-line-strong bg-surface-muted/60 px-4 py-12 text-center">
      <span aria-hidden="true" className="text-ink-subtle">
        {icon ?? <InboxIcon />}
      </span>
      <p className="text-ink-muted">{message}</p>
    </div>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p
      role="alert"
      className="flex items-start gap-2.5 rounded-lg border-l-4 border-priority-emergency bg-priority-emergency-soft px-4 py-3 text-sm font-medium text-priority-emergency shadow-xs"
    >
      <AlertIcon />
      <span>{message}</span>
    </p>
  );
}

/** A single skeleton bar/block. Composed into loading states below. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <span className={cx("skeleton block", className)} aria-hidden="true" />;
}

/** Loading placeholder for a queue table — matches its rhythm. */
export function TableSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div
      role="status"
      aria-label="Loading the queue"
      className="overflow-hidden rounded-xl border border-line bg-surface shadow-sm"
    >
      <div className="flex items-center gap-4 border-b border-line px-4 py-3.5">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-20" />
        <Skeleton className="ml-auto h-4 w-24" />
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-4 border-b border-line px-4 py-4 last:border-0"
        >
          <Skeleton className="h-6 w-20" />
          <Skeleton className="h-5 w-24" />
          <Skeleton className="ml-auto h-9 w-40 rounded-lg" />
        </div>
      ))}
    </div>
  );
}

/** Inline spinner for busy buttons and inline waits. */
export function Spinner({ className = "size-4" }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className={cx("animate-spin", className)}
      fill="none"
    >
      <circle
        cx="12"
        cy="12"
        r="9"
        stroke="currentColor"
        strokeWidth="3"
        opacity="0.25"
      />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** A quiet count chip for section headings ("Waiting · 6"). */
export function CountChip({ value }: { value: number | string }) {
  return (
    <span className="inline-flex min-w-6 items-center justify-center rounded-full bg-surface-sunken px-2 py-0.5 text-sm font-semibold tabular-nums text-ink-muted">
      {value}
    </span>
  );
}

function InboxIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-8" fill="none">
      <path
        d="M3 13.5 5.2 6a2 2 0 0 1 1.9-1.4h9.8A2 2 0 0 1 18.8 6L21 13.5M3 13.5V18a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-4.5M3 13.5h5l1.2 2h5.6l1.2-2H21"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function AlertIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      className="mt-0.5 size-4 shrink-0 fill-current"
    >
      <path d="M10 1.6 19 17H1L10 1.6Zm-.9 5.4v5h1.8v-5H9.1Zm0 6.4v1.8h1.8v-1.8H9.1Z" />
    </svg>
  );
}
