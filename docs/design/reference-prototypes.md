# Reference prototypes — the design the frontend must match

Two approved prototype sheets are the visual reference for Phase 5. Save the
image files alongside this document as:

- `medium-fidelity-wireframes.png` — "MEDIUM-FIDELITY PROTOTYPES (WIREFRAMES)"
- `high-fidelity-prototypes.png` — "HIGH-FIDELITY PROTOTYPES"

Both sheets show the same five screens. The wireframes fix **layout and
information hierarchy**; the high-fidelity sheet fixes **colour, chrome and
navigation**. Where they differ, the high-fidelity sheet wins, because it is the
later artefact — except where the spec overrides both (see
[Deviations](#deviations-from-the-prototypes) at the end, which is not
optional).

---

## 1. Patient status view (mobile)

The only screen designed phone-first. Everything else is a desk terminal.

| Region | Content |
| --- | --- |
| Header | Kabarak crest + "Kabarak Medical Center", dark green, menu affordance on the right |
| Token card | "Your Queue Token" label above a very large token, on a green card. The dominant element on the screen. |
| Current stage | Row with a green check icon and the stage name, e.g. "Registration Completed" |
| Next stage | Row with the upcoming stage, e.g. "Vital Signs" |
| Two tiles | "Your Position" (a number, with a people icon) and "Estimated Waiting" (a **range**, e.g. "10 – 15 Minutes") side by side |
| Status | Amber dot + word, e.g. "Waiting" |
| Actions | Full-width "Refresh", then "Request Assistance" |
| Footer | "Thank you for your patience." |

Notes:

- The waiting figure is rendered as a range with an en dash and the unit spelled
  out — never a single number and never a live countdown.
- No priority category, no clinical information, no other patient's data appears
  anywhere on this screen.
- "Request Assistance" is the visible route into the missed-turn / recall
  recovery path and the manual fallback.

## 2. Reception dashboard

| Region | Content |
| --- | --- |
| Sidebar | Dark green, crest at top, items: Dashboard, Queue, Patients, Reports, Settings, Logout |
| Top bar | "Reception Dashboard" left, role name + avatar right |
| Search | "Enter token…" field with a green "Search" button |
| Queue table | Columns: Token, Stage, Priority, Waiting Time, Action |
| Row actions | A primary green ▶ button per row; the urgent row instead shows a red call/recall button |
| Bottom actions | "+ Register Patient" (outline) and "Send to Vital Signs" (filled green) |

Priority renders as text in the row — "Routine" in normal ink, "Urgent" in red.

## 3. Vital signs (nurse) dashboard

| Region | Content |
| --- | --- |
| Sidebar / top bar | Blue |
| Heading | "Waiting Patients" |
| Table | Token, Priority (coloured dot + word), Action ("Start" button per row) |
| Section | "After Vital Signs" — a single wide primary button, "Complete & Send to Clinician" |

## 4. Consultation (clinician) dashboard

| Region | Content |
| --- | --- |
| Sidebar / top bar | Purple |
| Current patient | "Current Patient" label above a very large token — mirrors the patient's own screen |
| Fields | "Priority" and "Stage" shown as read-style boxes, e.g. "Routine", "Vital Signs Completed" |
| Primary action | Wide button, "Consultation Complete & Send to Pharmacy" |
| Secondary | "View Patient History" (outline) — the return-after-tests route |

## 5. Pharmacy dashboard

| Region | Content |
| --- | --- |
| Sidebar / top bar | Amber / orange |
| Heading | "Waiting for Dispensing" |
| Table | Token, Status ("Medication Ready" green, "Preparing" amber), Action ("Dispense" button per row) |
| Secondary | "View Dispensed History" (outline) |

---

## Design system extracted from the sheets

Implemented in [`../../frontend/src/app/globals.css`](../../frontend/src/app/globals.css).

| Token | Value | Used by |
| --- | --- | --- |
| `--color-brand-700` | `#0f4a2e` | Patient header, reception sidebar |
| `--color-role-reception` | `#16653f` | Reception |
| `--color-role-nurse` | `#2c5aa8` | Vital signs |
| `--color-role-clinician` | `#5b2d90` | Consultation |
| `--color-role-pharmacy` | `#b26a06` | Pharmacy |
| `--color-priority-emergency` | `#b3261e` | Staff screens only |
| `--color-priority-urgent` | `#a55a00` | Staff screens only |

The sheet's role colours were darkened where needed to clear WCAG 2.2 AA
contrast against white text — the prototype's amber in particular failed as a
button fill at its original lightness.

Structural rules taken from the sheets:

- **Each staff dashboard is colour-coded by role.** A member of staff can tell
  which station a screen belongs to from across the room. The colour is
  decoration on top of a text label, never the only signal.
- **The token is always the largest element** on both the patient view and the
  clinician's current-patient panel. It is the one thing shouted across a
  waiting room.
- **One primary action per screen**, full width, at the bottom of the working
  area: "Complete & Send to Clinician", "Consultation Complete & Send to
  Pharmacy". Spec's minimal-step requirement, made visual.
- **Tables are token-first**, with the action as the last column, so the eye
  travels token → state → action.

## Deviations from the prototypes

These are required; the spec outranks the sheets.

1. **Token format.** The sheets show `A017`; the spec's example is `T-041`. The
   format is configurable — see the open question in the Phase 0 summary. Until
   it is decided, treat the token as an opaque short string and never assume its
   shape in layout code.
2. **Priority is never shown to patients.** The sheets do not violate this, but
   note it explicitly: the patient view and the public display carry no priority
   colour, tag or category, even though staff tables do.
3. **A public waiting-room display screen is missing from both sheets.** The
   spec requires one (FR8): anonymous token + destination only, e.g.
   "T-041 → Consultation". It will be designed in Phase 5 using these tokens —
   large type, high contrast, readable across the room, no interaction.
4. **"Estimated Waiting" must degrade.** The sheets always show a range. When
   there is too little data for a reliable median the tile shows "wait time
   unavailable" instead (spec, Phase 6). The layout must not assume a number is
   always present.
5. **Accessibility additions.** Visible keyboard focus, a skip link, 44px
   minimum targets, and text labels beside every colour-coded dot — none appear
   in the sheets, all are required by WCAG 2.2.

## High-fidelity polish pass

A visual refinement pass was applied over the approved system — elevation and
radius scales, brand/board gradients, a dot-grid app background, reduced-motion-
safe animations, and shared `Crest`/`Brand`/`Spinner`/`Skeleton`/`CountChip`
pieces. It is depth layered on the approved design, **not a recolour**: the
Kabarak green identity and every contrast, focus and target rule are unchanged.
The brief is [`../../HIGH_FIDELITY_POLISH_PROMPT.md`](../../HIGH_FIDELITY_POLISH_PROMPT.md);
captured figures are in [`screenshots/`](./screenshots/).

Two things surfaced during that pass that were **not** cosmetic, and were fixed
as functional changes rather than styling:

- **The waiting-room board did not fill the screen.** It used a percentage
  height with no ancestor height to resolve against, so it collapsed to its
  content — leaving a pale band across a 1920×1080 wall display, worst when the
  queue was empty and there was least content to hide it. Now `min-h-dvh`.
- **The font was fetched from Google Fonts at build time.** The clinic machine
  is on the LAN with no internet dependency by design, so a build there would
  have failed on a font. Inter is now self-hosted in the repo, which also means
  no request leaves the building to render a page. Verified by building with
  all outbound traffic blackholed.
