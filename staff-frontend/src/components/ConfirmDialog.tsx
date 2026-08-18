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

import { Dialog } from "@/components/Dialog";
import { Button } from "@shared/ui/components/ui";

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
  // Focus lands on the dialog itself, not the confirm button — a keyboard user
  // pressing Enter out of habit should not commit the thing being confirmed.
  // That is the Dialog default, so nothing is passed for it here.
  return (
    <Dialog
      role="alertdialog"
      onClose={onCancel}
      labelledBy="confirm-heading"
      describedBy="confirm-body"
      width="max-w-sm"
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
    </Dialog>
  );
}
