# Task-based usability test protocol

> **This is an instrument, not a result.** Nobody has run it. It is written so
> that whoever does can run it consistently, and so the numbers that come out
> mean the same thing each time. Any claim about the targets below is unfounded
> until sessions have actually happened with real participants.

---

## Targets (from the spec)

| Target | Measure |
|---|---|
| ≥80% unaided completion of core tasks | Per task, across participants |
| No unresolved critical safety or privacy defect | Severity-3 findings, all closed |
| Mean ease-of-use ≥4 / 5 | Post-task rating, averaged |
| ≥80% correctly explain routine vs emergency priority | Post-session question, scored |

---

## Participants

- **6–8 patient-side participants**: students and university staff. Deliberately
  include people who have not used the system, at least one person without a
  smartphone, and at least one person who would describe themselves as not
  confident with technology. The spec's context-of-use names all three, and a
  sample of confident smartphone users would flatter the design.
- **4 staff-side participants**: one per station role, ideally people who
  actually do that job.

Sessions are ~25 minutes. Fictional data only; no real patient is involved at
any point.

## Setup

1. `start.bat`, then `python manage.py seed_demo --reset` for the staff accounts
   and an empty queue. No patients are seeded, so check about a dozen in at
   reception and advance most of them before the session — a participant should
   meet a queue that is already busy.
2. Patient tasks on a phone; staff tasks on a desktop at the relevant dashboard.
3. Waiting-room board visible on a second screen for tasks 3 and 8.
4. Two facilitators if possible: one runs the session, one records. One
   facilitator doing both reliably misses things.

## Ground rules for the facilitator

- **Do not help until the participant is genuinely stuck.** Record the point at
  which help was given — that is the completion measure.
- Ask them to think aloud, and stay quiet while they do.
- If they say "I'd normally ask someone", record it. That is a finding about
  the interface, not a failure by the participant.
- Never defend the design in the session. Note the objection and move on.

---

## The eight tasks

### Patient tasks

**T1 — Find your place in the queue.**
*You have been given this slip with token K492. Find out how far along you are.*
Completion: reads out their stage and how many are ahead.
Substitute the token actually issued in the session — tokens are random, so
there is no fixed one to print in advance.

**T2 — Find out how long you might wait.**
*Roughly how long do you think you will be waiting?*
Completion: reports a range, or says the system cannot tell them yet.
Also record: does an "unavailable" reading make them think it is broken?

**T3 — Read the waiting-room board.**
*Using the screen on the wall, find K492 and say where that patient is now.*
Completion: names the stage, and the room if one is shown. Record how far away
they stood.
Also record: do they understand that every token on the board is someone
currently in the clinic, rather than a list of people being called? The board
was widened to a tracking board after the first build (see
[tracking-board.md](../design/tracking-board.md)) and whether that reads
correctly to a patient has not been tested.

**T4 — You need to step away.**
*You need the toilet and are worried about losing your place. What would you do?*
Completion: says they would tell a member of staff.
This tests whether the on-screen guidance is noticed at all.

### Staff tasks

**T5 — Register a patient (Reception).**
*A patient has arrived. Register them and give them their token.*
Completion: token issued and read out.

**T6 — Escalate a patient (Nurse or Clinician).**
*A waiting patient has become unwell and needs to be seen immediately.*
Completion: priority set to emergency with a reason, and the patient is now
first in the queue.
Record: did they hesitate at the mandatory reason?

**T7 — Handle unavailable medicine (Pharmacy).**
*The medicine for this patient is out of stock.*
Completion: records medicine unavailable and can say what happens to the
patient's visit.

**T8 — Work through an outage (Reception).**
*The system has just gone down. Handle the next two patients, then enter them
once it is back.*
Completion: uses the paper sheet, records arrival times, and reconciles both
with the correct times afterwards.
This is the rehearsal the spec asks for, run as a task.

---

## After each task

> "How easy or difficult was that?"
> **1 = very difficult · 5 = very easy**

Then: "Was there anything you expected to be able to do and couldn't?"

## End of session

1. *"Some patients may be seen before others. Can you explain how the order is
   decided?"*
   Scored **correct** if they mention both (a) normally the order you arrived
   in, and (b) emergencies or urgent cases can go first. Partial credit is not
   awarded — the target is about understanding both halves.
2. *"Was anything shown to you that you would not want other patients to see?"*
   Any yes is a **severity-3 privacy finding** and stops the clock until
   resolved.
3. *"What one thing would you change?"*

---

## Recording sheet

```text
Participant: ____  Group: patient / staff (role: __________)  Date: ________
Smartphone user: Y / N     Self-described confidence with technology: L / M / H

Task | Completed unaided? | Help given at | Ease (1-5) | Notes
-----+--------------------+---------------+------------+---------------------
 T1  |                    |               |            |
 T2  |                    |               |            |
 T3  |                    |               |            |
 T4  |                    |               |            |
 T5  |                    |               |            |
 T6  |                    |               |            |
 T7  |                    |               |            |
 T8  |                    |               |            |

Priority explanation:  correct / incorrect     Privacy concern raised: Y / N
One thing to change: ______________________________________________
```

---

## Reporting

Report per task: completion rate, mean ease, and the observations behind them.
Report the two end-of-session measures across all participants.

**Report failures plainly.** A task at 60% completion is the most useful result
the session can produce, and softening it wastes the participants' time. UCD is
iterative: findings feed back into requirements, and the spec expects that
rather than treating it as a setback.
