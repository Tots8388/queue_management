"use client";

import { useEffect, useState } from "react";

import { apiUrl } from "@/lib/config";

type Status = "checking" | "online" | "offline";

/**
 * Live indicator for whether the queue server is reachable.
 *
 * This matters operationally, not just cosmetically: when the server is down,
 * staff switch to the documented manual paper fallback (spec FR12), so the
 * state has to be unambiguous and never silently stale.
 */
export function BackendStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const response = await fetch(apiUrl("health/"), { cache: "no-store" });
        if (!cancelled) setStatus(response.ok ? "online" : "offline");
      } catch {
        if (!cancelled) setStatus("offline");
      }
    }

    check();
    const interval = setInterval(check, 15_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const presentation = {
    checking: { dot: "bg-ink-muted", text: "Checking queue server…" },
    online: { dot: "bg-status-complete", text: "Queue server online" },
    offline: {
      dot: "bg-status-missed",
      text: "Queue server unreachable — use the manual fallback",
    },
  }[status];

  return (
    <p
      className="flex items-center gap-2 text-sm text-ink-muted"
      role="status"
      aria-live="polite"
    >
      <span
        className={`inline-block size-2.5 shrink-0 rounded-full ${presentation.dot}`}
        aria-hidden="true"
      />
      {presentation.text}
    </p>
  );
}
