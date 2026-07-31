# Manual fallback and reconciliation

**Print this. Keep a paper copy at the reception desk.** A procedure that only
exists on the screen that just went down is not a procedure.

This is the documented offline fallback the spec requires (FR12). It applies
whenever the queue system is unavailable — server down, network down, power
cut, or the screens frozen.

---

## The rule that overrides everything on this page

**Clinical care does not wait for the queue system.** If a patient needs
immediate attention, they receive it. The system exists to record and
communicate order; it has never been what authorises treatment. Nothing in this
procedure may be read as a reason to delay a patient.

---

## 1. Recognising an outage

You are in an outage if any of these is true:

- A dashboard shows the red banner: *"Not connected to the queue server."*
- The waiting-room board has stopped changing and shows the same message.
- `http://<server>:8000/api/health/` does not respond.

A dashboard that is merely slow is **not** an outage. Wait 30 seconds and
refresh once before switching to paper.

**Announce it.** Tell the other stations verbally. Two stations working from
different sources of truth is worse than everyone working from paper.

---

## 2. Switching to paper

Reception takes the **fallback sheet** (template at the end of this document)
and continues issuing numbers by hand.

1. **Keep the sequence going.** Write the next number after the last one the
   system issued. If nobody can see the last token, start a new sheet with the
   prefix `P` — `P-01`, `P-02` — so the paper numbers are obviously not system
   tokens.
2. **Record the arrival time for every patient, to the minute.** This is the
   single most important thing on the sheet. It is what restores each person's
   place in the queue when the system returns; without it, everyone who waited
   through the outage is pushed to the back.
3. **Hand the patient the slip** with their number written on it, and tell
   them plainly: *"Our screens are down. Keep this slip; we are calling numbers
   out loud."*
4. **Call numbers out loud** at each station. Do not rely on any screen.
5. **Write nothing clinical on the sheet.** Number, arrival time, stage, and a
   mark for urgent. No names, no symptoms, no diagnoses. The sheet is a queue
   record, not a medical record.

### Clinical priority during an outage

Unchanged: only a nurse/triage or a clinician may decide a patient is urgent or
an emergency. Mark it on the sheet with **U** or **E** and the initials of the
person who decided, so the decision can be entered with the right attribution
afterwards. Reception does not make that mark on its own authority.

---

## 3. While on paper

- Each station keeps its own section of the sheet or its own sheet. Do not
  maintain two copies of the same queue.
- If a patient steps away, write **AWAY** and the time beside their number.
  They keep their place, exactly as they would in the system.
- Do not start typing into the system as it comes back mid-queue. Finish the
  patients in front of you on paper, then reconcile.

---

## 4. Reconciliation, once the system returns

Do this **the same day**, before the sheets are put away. Reception does it;
the system will not accept an arrival time more than 24 hours old.

1. Sign in and open the **Reception** dashboard.
2. For each line on the sheet, use **Enter from paper fallback**:
   - **Arrival time** — the time written on the sheet, *not* the time now.
     This is the whole point of the exercise.
   - **Sheet reference** — e.g. `Sheet 2, line 7`, so the paper and the record
     can be matched later.
   - **Stage** — where the patient had actually reached on paper.
3. The system issues each patient a normal token. **Give the patient their new
   token** if they are still in the building, and explain that the paper number
   is no longer being called.
4. Enter any priority decisions from the sheet, through the usual priority
   control, with the reason recorded. Marks made by a nurse or clinician on
   paper should be entered while that person is available to confirm them.
5. Patients whose visit finished during the outage still get entered, then
   completed through to the end, so the day's record is whole.

Every reconciled entry is written to the audit trail as
`fallback_reconciliation`, so what was added afterwards is always
distinguishable from what the system recorded live.

### If the sheets are lost or unreadable

Do not invent arrival times. Enter the patients you can account for, and record
in the audit detail that the sheet was incomplete. A gap that is visible is far
better than a record that looks complete and is wrong.

---

## 5. Afterwards

- File the paper sheets with the day's records; they are the evidence behind
  the reconciled entries.
- Note the outage in the operations log: when it started, when it ended, roughly
  how many patients were handled on paper.
- If the outage lasted more than an hour or recurred, raise it with the system
  owner — see [`resilience.md`](./resilience.md).

---

## Fallback sheet template

Copy this onto a sheet of paper. Keep blank copies in the reception drawer.

```text
KABARAK UNIVERSITY MEDICAL CENTER — QUEUE FALLBACK SHEET

Date: ____________   Sheet no: ____   Started: ______  Ended: ______
Staff running fallback: ______________________________

 No.  | Arrived | Stage reached           | U/E | By  | Away | Notes
      | (hh:mm) | Reg / Vitals / Cons / Ph|     |     |      |
------+---------+-------------------------+-----+-----+------+---------
 P-01 |         |                         |     |     |      |
 P-02 |         |                         |     |     |      |
 P-03 |         |                         |     |     |      |
 P-04 |         |                         |     |     |      |
 P-05 |         |                         |     |     |      |
 P-06 |         |                         |     |     |      |
 P-07 |         |                         |     |     |      |
 P-08 |         |                         |     |     |      |
 P-09 |         |                         |     |     |      |
 P-10 |         |                         |     |     |      |

U/E = Urgent / Emergency. Only a nurse or clinician may mark this.
By   = initials of the nurse or clinician who decided.
NO NAMES. NO SYMPTOMS. NO DIAGNOSES. This is a queue record only.

Reconciled into the system by: ______________  Date/time: ____________
```
