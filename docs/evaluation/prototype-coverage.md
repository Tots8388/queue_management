# High-fidelity prototype — coverage and demonstration

The spec (§4.9) lists eleven things the high-fidelity prototype must cover. The
working application is that prototype: it is clickable, it runs on fictional
data, and every item below is a real path through it rather than a mock-up of
one.

**Fidelity ladder, honestly stated.** The low- and medium-fidelity artefacts
are the two prototype sheets supplied at the start of this build, recorded in
[`../design/reference-prototypes.md`](../design/reference-prototypes.md). I did
not produce new wireframes — they already existed and the build followed them.
What this document adds is the mapping from that sheet to working software, and
the five places the software deliberately departs from it.

---

## Coverage of spec §4.9

| # | Required | Where it lives | Status |
|---|---|---|---|
| 1 | Registration and token issue | Reception dashboard → *Register patient* | ✅ |
| 2 | Patient progress | `/patient/<token>` — stage bar, people ahead, wait range | ✅ |
| 3 | Anonymous waiting-room display | `/display` — the tracking board: everyone in the clinic, by stage, token + room only | ✅ |
| 4 | Vitals completion | Vital signs dashboard → *Complete & send to clinician* | ✅ |
| 5 | Authorised priority | Priority dialog, clinical roles only, reason required | ✅ |
| 6 | Consultation transfer | Consultation dashboard → *Complete & send to pharmacy* | ✅ |
| 7 | Pharmacy readiness | Pharmacy dashboard → *Ready* / *Dispense & close* | ✅ |
| 8 | Missed-turn recovery | Presence controls: called → missed turn → resumed | ✅ |
| 9 | Return after tests | Consultation → *Send for laboratory tests* / *Patient returned* | ✅ |
| 10 | Medicine-unavailable status | Pharmacy → *not available*, visit stays open | ✅ |
| 11 | Offline fallback messaging | Connection banner + reception fallback panel + reconciliation | ✅ |
| 12 | Abandoned-visit closure | Reception dashboard → *Abandoned visits*, after 24h idle | ✅ |

Two things the sheets did not include, added because the spec requires them:
the **public display screen** (FR8 has no prototype in either sheet) and a
**wait range that can degrade to unavailable** rather than always showing a
number.

Row 12 is not in spec §4.9 either. It follows from a build decision the sheets
predate — a visit now ends when pharmacy is finished rather than at the end of
the day, which leaves nothing to close a visit the patient walked away from.
See [Queue policy → Abandoned visits](../../spec.md#queue-policy-from-the-brief).

---

## Demonstration script

About 12 minutes. Fictional data throughout — say so at the start, because an
audience watching a queue system should never be left wondering whose data it is.

**Setup**

```bat
start.bat
```
```bash
cd backend && .venv\Scripts\python manage.py seed_demo --reset
```

Open four windows: the waiting-room board (`/display`), a patient view, a staff
dashboard, and one spare browser for a second role. Sign in with the seeded
accounts (`reception1`, `nurse1`, `clinician1`, `pharmacy1`, password
`prototype-demo-only`).

The queue starts empty — no patients are seeded. Before the audience arrives,
check about a dozen in at reception and walk most of them through the stages, so
each dashboard has a queue and the wait range has completed services to work
from. Every one of those visits is then real use of the system, which is the
point.

### 1. One token, four stages (2 min) — items 1, 2, 4, 6

Register a patient at reception. Read the token aloud. Open it in the patient
view. Complete each stage in turn, letting the audience watch the patient
screen change **without anyone refreshing it** — that is the single queue state
doing its job.

### 2. Fairness, then urgency (3 min) — item 5

Show three routine patients waiting in check-in order. Then escalate the last
of them to emergency, with a reason.

Point out three things:
- they move to the front, and the change appears on every open screen at once;
- the **patient's own screen never says "emergency"** — it says they will be
  seen as soon as possible;
- the **public board never says it either** — token and destination only.

Then try the same escalation signed in as reception. It is refused. The refusal
is the feature.

### 3. Privacy in public (1 min) — item 3

Put the board on the big screen. Four columns, everyone in the building, each
under the stage they are at — a patient can find their own token and see how
far along they are without asking at a desk.

Nothing on it identifies anyone: no name, no priority, no clinical detail, by
construction rather than by policy. Two details worth naming aloud, because
both are decisions rather than accidents:

- The emergency patient from the previous section is **still in arrival
  order** on the board. A board sorted by who is next would tell the room who
  has been given a clinical priority.
- The tokens are **random**, so the board publishes neither the order people
  arrived in nor how many the clinic has seen today.

### 3b. The patient who went home (1 min) — item 12

A patient leaves the board only when pharmacy is finished with them, so
somebody who leaves halfway through would sit there for good. Strand a visit
(the one-liner in [`../test-accounts.md`](../test-accounts.md) does it), and an
**Abandoned visits** panel appears on the reception dashboard.

Close it, and say why it works this way: the 24-hour threshold is enforced on
the server, so the capability is "close what has clearly been abandoned", not
"remove a patient from the queue" — and the clerk who did it is named in the
audit log, because if the judgement was wrong, somebody still waiting has just
been taken off every screen.

### 4. When things go sideways (3 min) — items 8, 9, 10

- Mark a called patient as **missed turn**, then **resumed** — they keep their
  place, and the person behind them was never told they were ahead.
- **Send a patient for tests**, then bring them back — the history shows two
  consultations, and the first one is intact.
- Mark medicine **not available** — the visit stays open, because the patient
  still needs somewhere to go.

### 5. When the system goes down (3 min) — item 11

Stop the backend (`stop.bat`, or just the backend service).

- Every dashboard turns to the red banner naming the paper fallback.
- The patient view and the board say so too.
- Show the printed fallback sheet from
  [`../operations/offline-fallback.md`](../operations/offline-fallback.md).

Start the backend again. Enter two patients from the sheet with **their
recorded arrival times**, and show that they land ahead of the walk-in who
arrived during the outage. That is the point of the whole procedure: a patient
who waited is not punished for it.

Finish on the audit trail: the escalation from step 2 is attributable to the
clinician who made it, with the reason they gave.

---

## What a demonstration must not claim

- That this is production-ready. It is a prototype, on fictional data, and the
  spec is explicit that a governed pilot comes first.
- That the accessibility work has been verified. It is built to WCAG 2.2, and
  it has not been through a screen reader or a contrast audit.
- That the usability targets have been met. The protocol exists; no session has
  been run.
- That Management or IT/Support dashboards work. They are deliberately
  withheld pending governance item G4, and a demonstration should say so rather
  than avoid the question.
