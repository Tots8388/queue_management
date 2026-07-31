"use client";

/**
 * Confirmation for an action that cannot be undone.
 *
 * Used sparingly and on purpose. Confirming everything trains staff to click
 * through without reading, which makes the prompt worse than useless — so this
 * appears only where the system has no way back, such as closing a visit.
 *
 * It is deliberately **not** used on emergency escalation: the spec says never
 * delay emergency care, and an extra tap between a clinician and an emergency
 * is exactly the delay it warns about.
 */

import { useEffect, useRef } from "react";

import { Button } from "@/components/ui";

export function ConfirmDialog({
  title,
  body,
  confirmLabel = "Confirm",
  onConfirm,
  onCancel,
  destructive = false,
}: {
  title: string;
  body: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  destructive?: boolean;
}) {
  const cancelRef = useRef<HTMLDivElement>(null);

  // Focus lands on the dialog, not the confirm button — a keyboard user
  // pressing Enter out of habit should not commit the thing being confirmed.
  useEffect(() => {
    cancelRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel]);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 px-4 py-4 backdrop-blur-sm sm:items-center">
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-heading"
        aria-describedby="confirm-body"
        ref={cancelRef}
        tabIndex={-1}
        className="animate-fade-rise w-full max-w-sm rounded-2xl bg-surface p-6 shadow-lg"
      >
        <h2 id="confirm-heading" className="text-lg font-semibold">
          {title}
        </h2>
        <p id="confirm-body" className="mt-2 text-ink-muted">
          {body}
        </p>

        <div className="mt-6 flex justify-end gap-3">
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            variant={destructive ? "danger" : "primary"}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
