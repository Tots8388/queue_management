# Heuristic evaluation

**Evaluator:** Claude (Opus 5), acting as a single expert evaluator
**Date:** 31 July 2026
**Method:** Nielsen's ten usability heuristics, applied to the built interface
**Scope:** patient status view, waiting-room board, and the reception, vital
signs, consultation and pharmacy dashboards

> **A caveat that matters.** This is a *single-evaluator* heuristic inspection
> by the system's own author. Both of those weaken it: the literature suggests
> 3–5 independent evaluators to find most issues, and an author inspecting
> their own work is blind in predictable ways. Treat this as a first pass that
> catches obvious defects before real evaluators are asked to spend their time —
> not as the evaluation the spec requires. That still needs independent
> evaluators and the task-based testing in
> [`usability-test-protocol.md`](./usability-test-protocol.md).

Severity: **0** cosmetic · **1** minor · **2** major · **3** catastrophic
(safety, privacy, or task-blocking).

---

## Findings

### F1 — "Request assistance" did nothing · Severity 3 · FIXED

*Heuristic: match between system and the real world; visibility of system
status.*

The patient view had a prominent "Request assistance" button, taken from the
prototype sheet, which sent nothing anywhere. A patient in difficulty would
press it and wait for help that was never coming. In a clinic that is a safety
defect, not a cosmetic one.

**Fixed.** The button now opens plain guidance: go to the reception desk, this
button does not call anyone, and — stated explicitly — if you feel very unwell,
tell staff straight away rather than waiting for your token. A staff alerting
channel would be the better answer, but it is not in v1, and pretending
otherwise was the actual danger.

### F2 — Closing a visit was irreversible with no confirmation · Severity 2 · FIXED

*Heuristic: error prevention; user control and freedom.*

"Dispense & close" ended a visit on a single tap, with no undo anywhere in the
system. Pharmacy rows sit next to each other and tokens look alike.

**Fixed.** A confirmation step now names the token and says the action cannot
be undone. Deliberately **not** applied to emergency escalation: the spec says
never delay emergency care, and an extra tap between a clinician and an
emergency is precisely the delay it warns about.

### F3 — "View patient history" was in the prototypes but not built · Severity 2 · FIXED

*Heuristic: recognition rather than recall.*

Both prototype sheets show a history control on the clinician and pharmacy
screens. It was not implemented, so a clinician had no way to see that a
patient had already been round consultation once — the exact context the
return-after-tests path depends on, held only in the clinician's memory.

**Fixed.** A history view shows stage timings, priority decisions with their
reasons, and pharmacy outcomes. It states on its face that it holds no clinical
information and that the medical record is elsewhere.

### F4 — Reception search only finds patients at reception · Severity 2 · OPEN

*Heuristic: flexibility and efficiency of use.*

The search box filters the reception queue only. A patient who asks "where am
I?" after moving to vitals cannot be found from the desk they are standing at,
which is where they will ask.

**Recommendation:** a token lookup across all active stages, returning stage and
status. Small backend addition; not done because it is a new capability rather
than a fix, and it should be a deliberate decision.

### F5 — No way to correct a mistaken stage completion · Severity 2 · OPEN

*Heuristic: user control and freedom; error recovery.*

If a nurse completes the wrong token, the patient is moved on and there is no
path back. Staff would have to work around it, and workarounds are where audit
trails stop reflecting reality.

**Recommendation:** a "send back a stage" action for clinical roles, requiring
a logged reason — the same shape as manual reorder. Deferred because it changes
the queue policy surface and deserves a decision, not a quiet addition.

### F6 — The wait range explains itself, but only if you look · Severity 1 · OPEN

*Heuristic: help and documentation.*

"Wait time unavailable" is honest but bare. A patient may read it as the system
being broken rather than cautious.

**Partly addressed:** the tile carries "We cannot give a reliable estimate right
now", and the "Why might someone be seen before me?" panel explains the queue
policy. Whether that lands is a question for the user testing, not for me.

### F7 — Offline state is clear to staff, quieter for patients · Severity 1 · OPEN

*Heuristic: visibility of system status.*

Staff get an explicit red banner naming the paper fallback. The patient view
shows the same connection banner, but a patient has no idea what a "queue
server" is.

**Recommendation:** patient-facing wording along the lines of "This screen may
be out of date — staff are calling tokens out loud." Deferred to user testing,
which will say better than I can whether the current wording worries people.

### F8 — Token format is not validated before submission · Severity 0 · OPEN

Typing `41` instead of `T-041` produces a 404 after a round trip rather than
immediate guidance. The 404 page is clear and offers a retry, so this is minor.

---

## What held up well

Recorded because a heuristic evaluation that only lists faults gives a false
picture of where risk sits.

- **Consistency.** One vocabulary from `shared/contracts.json` means a stage is
  called the same thing on every screen, in every message, in the database.
- **Error prevention on the thing that matters most.** Priority is restricted
  by role at four layers, and reasons are categories rather than free text — so
  a clinical detail cannot be typed into a queue record by accident.
- **Recognition over recall.** The token is the largest element on every screen
  that shows one, and role colour tells staff which station a screen belongs to
  before they read a word.
- **Aesthetic and minimalist design on the public board.** Two fields, and no
  way to add a third.
- **Honest system status.** The connection banner tells staff the queue may be
  stale rather than showing a confident, wrong list.

---

## Summary

| Severity | Found | Fixed | Open |
|---|---|---|---|
| 3 catastrophic | 1 | 1 | 0 |
| 2 major | 3 | 2 | 2 |
| 1 minor | 2 | 0 | 2 |
| 0 cosmetic | 1 | 0 | 1 |

No open finding is a safety or privacy defect. F4 and F5 are the two worth
resolving before the pilot; both are deliberate deferrals awaiting a decision
rather than oversights.
