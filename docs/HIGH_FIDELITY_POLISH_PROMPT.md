# High-Fidelity UI Polish — Build / Handoff Prompt

Reusable prompt that reproduces the high-fidelity visual polish applied to the Queue Management frontend, and serves as a record of what changed. It is a **visual/UX layer only** — no backend, API, data-hook, auth, or color-token changes.

---

## Goal

Elevate the existing **Next.js 16 / React 19 / Tailwind 4** frontend into a cohesive, screenshot-ready **high-fidelity clinical prototype**. Improve elevation, motion, iconography, and per-screen layout while keeping the **Kabarak GREEN** identity. Do **not** change backend contracts, API, data hooks, auth, or the existing color tokens.

---

## Constraints (do not violate)

- Visual/UX layer only — no changes to data-fetching hook **behavior** or auth.
- Do **not** alter the `contracts.ts` / `contracts.json` vocabulary.
- Keep the existing color tokens; keep the **Kabarak GREEN** identity (contrast-checked in `docs/design/reference-prototypes.md`). Do **not** introduce maroon.
- Preserve all focus-ring, touch-target, and **WCAG-AA contrast** rules.
- Never expose patient priority on patient-facing screens (**FR8**).
- Public display shows **anonymous token + destination only**.
- Keep the **"fictional data / not for clinical use"** disclaimer.
- No heavy UI library; no new stack/hosting/SMS decisions.
- Gated **Supervisor / IT** roles untouched (`dashboard: null`, governance hold **G4**).
- Crest is a **placeholder** until the official Kabarak asset is supplied.
- Respect reduced-motion preferences for all animations.

---

## Design System (`globals.css`, `components/ui.tsx`)

Add foundational primitives and shared components:

- **Elevation / shadow scale** and a **radius scale**.
- **Brand** and **board** gradients; a faint **dot-grid** app background.
- **Animations:** reduced-motion-safe skeleton **shimmer**, a **"live" pulse**, and a **fade-rise** entrance.
- **Shared components:** `Crest` / `Brand` marks, `Spinner`, `Skeleton` / `TableSkeleton`, `CountChip`.
- **Button:** add a `ghost` variant, size options, shadows, and active states.
- Preserve all focus-ring, touch-target, and WCAG-AA contrast rules throughout.

---

## Per-Screen Changes

**Home hub** — gradient header + crest; icon-led entry cards that lift on hover; a connected, numbered patient-journey stepper.

**Login** — elevated centered card; green focus rings; invalid-input styling; inline submit spinner; disclaimer footer.

**Patient entry** — gradient background + crest; large centered token input with a focus halo.

**Patient status** — four-stage progress stepper (Registration → Vitals → Consultation → Pharmacy) with done / current / upcoming states; gradient token card; icon tiles; loading skeletons; a refined not-found card. Never expose priority (**FR8**); include disclaimer footer.

**Public display** — fully viewport-scaled (`clamp()` / `vw`) for a wall screen; pulsing **Live** chip + clock; highlighted now-serving row; graceful empty state. Show anonymous token + destination only.

**Staff shell** — role-colored sidebar with crest and grouped nav; sticky translucent top bar with avatar chip; spinner loading state.

**Queue table** — tinted uppercase header; hover + emergency-row tint / accent bar; summary tiles that emphasize **Emergency / Urgent** in status colors when non-zero.

**Priority dialog** — backdrop blur; entrance animation; selectable, color-coded priority cards; spinner on save.

**Dashboards (reception / vitals / consultation / pharmacy)** — reception gets selectable preference chips, a stronger issued-token card, and focus rings; all four get count chips on section headers.

---

## Verification

- Run `npm run lint` — must pass.
- Run `npm run build` — must pass.
- Both verified on **Windows**.
