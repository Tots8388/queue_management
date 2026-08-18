# The tracking board, and the random weekly token

Two changes were made together after the first working build, because neither
holds up without the other. This note records what changed, why, and what it
costs — the board publishes strictly more than it used to, and that deserves a
written reason rather than a commit message.

---

## What changed

**Before.** The waiting-room screen was a call-forward list. A patient appeared
on it at the moment staff called their token and vanished again once the call
was answered. Tokens were a per-day sequence — `T-001`, `T-002` — reset each
morning, and a visit was scoped to the day it started.

**After.** The screen is a tracking board. Every patient in the building appears
on it, in a column for the stage they are at — Reception, Vital signs,
Consultation, Pharmacy — from check-in until pharmacy is finished with them.
Tokens are drawn at random (`K492`) and are unique within a **token period**, a
week by default, rather than within a day.

---

## Why the board

The old screen answered one question — *is it my turn?* — and only for the few
seconds it was being asked. Everybody else in the room learned nothing from it,
so they asked at a desk instead, which is the queue the system exists to remove.

The board answers the question people actually have: *where am I, and is
anything happening?* A patient who can see their own token sitting in the
Consultation column knows they have not been forgotten, and does not need to
join a second queue at reception to find out.

It also makes the four stages visible as stages. A patient who did not know that
vitals comes before the clinician can read it off the wall.

## Why random tokens

Because of the board. A sequential token published next to every other token in
the building publishes two things nobody asked to publish:

- **Arrival order.** `T-004` in Consultation and `T-019` in Reception says
  plainly who came first, and by roughly how much. On its own that is harmless;
  next to a small waiting room where people can see each other, it is the sort
  of detail that lets someone reconstruct who is who.
- **Throughput.** The highest token on the board is the clinic's running total
  for the day, readable by anyone who walks past.

Random tokens leak neither. They are drawn with `secrets`, not `random`,
because the token is the only thing standing between a stranger and a patient's
status page.

The alphabet excludes **O, I, L and S**. A token is read off a wall screen and
then said out loud at a desk; those four are the letters that fail at both.

## Why a period rather than a day

A visit no longer ends when the day does — it ends when pharmacy is finished.
A patient still in the clinic at midnight must not lose their token, so
uniqueness cannot be scoped to the day.

The period is a fixed-length window counted from a stored epoch (`TOKEN_EPOCH`),
not the ISO week, so changing `TOKEN_PERIOD_DAYS` does not silently move every
boundary in the past. One week by default; `TOKEN_PERIOD_DAYS=1` reproduces the
old daily behaviour exactly.

With 22 letters and three digits the pool is 22,000 tokens per period. A clinic
holding a few hundred people at once will essentially never collide, and when it
does, the database's unique constraint settles it and check-in draws again —
not a check-then-insert, which is the race several reception terminals would
lose.

---

## What the board still may not show

Unchanged, and non-negotiable (spec FR8):

- no names,
- no priority categories,
- no diagnoses or prescriptions.

The server sends four fields — token, stage, destination, and whether the token
has just been called — and there is no field in the payload that could carry
anything else.

**The columns are in arrival order, deliberately not in service order.** The
queues themselves run emergencies first. A board that published the order people
will actually be seen would let the room work out which patients have been given
a clinical priority, which is the priority category by another name. Arrival
order is the one ordering that discloses nothing, and it is also the order a
patient can verify against their own memory of walking in.

---

## Abandoned visits

A patient now leaves the board only when pharmacy is done. Somebody who goes
home halfway through without telling anyone has nothing to clear them, so
without a rule they would sit in a column indefinitely.

**The rule: reception closes a visit once nothing has happened to it for 24
hours** (`STALE_VISIT_HOURS`). The reception dashboard grows an "Abandoned
visits" panel when there is something in it, listing each stranded visit with
how long it has been idle and a confirm-then-close action.

Four things about it are deliberate:

- **Measured from `last_updated`, not from check-in.** A patient who arrived
  yesterday morning and was seen at vitals last night is mid-journey; one whose
  record has not moved since check-in went home. Check-in time cannot tell
  those apart, and using it would close visits that are simply long.
- **Reception, not a scheduled job.** A visit still open is a patient the
  clinic has lost track of. Somebody at the desk noticing that is worth more
  than a cron entry quietly tidying it away — and reception is the desk that
  knows who walked back out.
- **The threshold is enforced on the server.** Without it the capability reads
  "reception may remove any patient from the queue", which is not a power the
  registration desk should hold. A visit touched within the last 24 hours is
  refused with a 400, whatever the client asks for.
- **The stage is preserved and the clerk is named.** The visit closes where it
  stopped rather than being rewritten to "complete", because "complete" would
  tell the reports that somebody collected medication they never received. And
  the audit entry is an *accountability* one, naming the individual: if the
  judgement was wrong, a patient who was still waiting has been removed from
  every queue.

The token period is still a backstop underneath all of this — the board only
shows the current period, so anything missed falls off within
`TOKEN_PERIOD_DAYS` regardless. The 24-hour rule is what stops it getting that
far.

Closing a stale visit is a queue operation, not data retention: nothing is
deleted, and the visit and its audit trail are kept on their own schedules.
