"use client";

/**
 * The one modal surface in the system.
 *
 * It exists because there were three of them. Confirm, priority and visit
 * history each carried their own copy of the overlay classes, the focus-on-open
 * effect and the Escape listener, and they had already drifted — only one had
 * grown a scroll container, so the other two spilled off the top of a short
 * clinic terminal with no way to reach the heading.
 *
 * Three behaviours belong to every modal and are therefore settled here rather
 * than per dialog:
 *
 *   - **focus goes in on open and comes back on close.** Pharmacy staff close
 *     visits one after another; without the return trip, focus falls to the top
 *     of the document and the whole page has to be re-tabbed between patients.
 *   - **Tab stays inside.** `aria-modal="true"` tells a screen reader the rest
 *     of the page is inert, so letting Tab walk out into the queue table behind
 *     it makes the announcement a lie.
 *   - **the panel scrolls.** On the bottom-sheet layout a tall dialog is pinned
 *     to the bottom of the viewport, so anything that overflows goes off the top
 *     of the screen — where there is nothing to scroll.
 */

import { useEffect, useRef, type ReactNode, type RefObject } from "react";

import { cx } from "@shared/ui/components/ui";

const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

export function Dialog({
  onClose,
  labelledBy,
  describedBy,
  role = "dialog",
  width = "max-w-md",
  initialFocus,
  children,
}: {
  onClose: () => void;
  labelledBy: string;
  describedBy?: string;
  /** `alertdialog` for a destructive confirmation, `dialog` otherwise. */
  role?: "dialog" | "alertdialog";
  width?: string;
  /**
   * Where focus should land. Defaults to the panel itself, which is the safe
   * choice: focusing a control means a keyboard user pressing Enter out of
   * habit can commit the very thing the dialog is asking about.
   */
  initialFocus?: RefObject<HTMLElement | null>;
  children: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    (initialFocus?.current ?? panelRef.current)?.focus();

    return () => {
      // The trigger may have gone with the row it lived on — a closed visit
      // disappears from the queue — in which case focus falls back to the
      // document, which is the best available answer.
      previouslyFocused?.focus?.();
    };
    // Intentionally on mount/unmount only: re-running this would steal focus
    // back to the top of the dialog on every parent re-render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      const panel = panelRef.current;
      if (!panel) return;

      const focusable = Array.from(
        panel.querySelectorAll<HTMLElement>(FOCUSABLE),
      ).filter((element) => element.getClientRects().length > 0);

      if (focusable.length === 0) {
        event.preventDefault();
        panel.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;

      if (!panel.contains(active)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      } else if (event.shiftKey && (active === first || active === panel)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 px-4 py-4 backdrop-blur-sm sm:items-center">
      <div
        ref={panelRef}
        role={role}
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        tabIndex={-1}
        className={cx(
          "animate-fade-rise w-full rounded-2xl bg-surface p-6 shadow-lg",
          "max-h-[85dvh] overflow-y-auto",
          width,
        )}
      >
        {children}
      </div>
    </div>
  );
}
