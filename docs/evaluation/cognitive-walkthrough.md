# Cognitive walkthrough

**Method:** Wharton et al. — for each step, ask the four questions:

1. Will the user try to achieve the right effect?
2. Will they notice the correct action is available?
3. Will they associate the correct action with the effect they want?
4. If the correct action is performed, will they see progress towards their goal?

Two tasks are walked through here: the one a first-time patient under stress
has to complete, and the one a clinician performs under time pressure. Both are
chosen because failure in them is costly rather than annoying.

> Same caveat as the heuristic evaluation: this is the author walking through
> their own design. It predicts where users will struggle; it does not
> substitute for watching them.

---

## Task A — A first-time patient checks their place in the queue

**User:** a student, first visit, mild anxiety, using their own phone. They have
a printed slip reading `T-041`.

### A1. Open the patient view

1. **Right effect?** Yes — they want to know how long they will wait. That is
   why they took out their phone.
2. **Action visible?** ⚠️ **Weak point.** Nothing on the printed slip has been
   designed yet. The patient must be told the address by staff or a poster.
   **Recommendation:** print the URL and a QR code on the token slip. This is
   the single largest adoption risk in the patient journey and it sits outside
   the software.
3. **Association?** Yes, once they have the address.
4. **Progress visible?** Yes — the token entry screen names the Medical Center
   and asks for the token on their slip, in those words.

### A2. Enter the token

1. **Right effect?** Yes.
2. **Action visible?** Yes. One field, one large button, and the field's hint
   repeats where the token came from.
3. **Association?** Yes. The placeholder shows `T-041`, matching the slip.
4. **Progress visible?** Yes, and a mistyped token produces an explanation
   rather than a dead end — it says tokens are issued fresh each day and offers
   a retry.

### A3. Understand where they are

1. **Right effect?** Yes.
2. **Action visible?** No action needed — this is the screen's whole purpose.
3. **Association?** Yes. The token is the largest thing on the screen; the
   stage progress bar shows the whole journey rather than a single label.
4. **Progress visible?** Yes.

### A4. Understand how long they will wait

1. **Right effect?** Yes — this is what they actually came for.
2. **Action visible?** Yes; the tile is one of two side by side.
3. **Association?** ⚠️ **Weak point.** Early in the day the tile reads "Wait
   time unavailable". A patient may read that as the system being broken rather
   than as honesty about thin data. The supporting line — "We cannot give a
   reliable estimate right now" — is the mitigation, and whether it lands is
   exactly what the user testing must measure.
4. **Progress visible?** Yes when a range is shown; "about 10–20 minutes" reads
   as a guide, and the caption says so.

### A5. Understand why someone else went first

1. **Right effect?** ⚠️ Only if they wonder. Most will.
2. **Action visible?** ⚠️ **Weak point.** The explanation sits behind a
   collapsed "Why might someone be seen before me?" panel. A frustrated patient
   may not open it — and this is the one thing the evaluation explicitly
   measures (≥80% able to explain routine vs emergency order).
   **Recommendation:** if the testing shows under 80%, expand this panel by
   default rather than rewording it.
3. **Association?** Yes — the question is phrased as the patient would ask it.
4. **Progress visible?** Yes; the answer is three short paragraphs in plain
   language, and it says a nurse or doctor makes that decision, never the
   system.

---

## Task B — A clinician escalates a deteriorating patient to emergency

**User:** clinical officer, mid-consultation, a waiting patient has deteriorated.
Under time pressure and being watched.

### B1. Find the patient

1. **Right effect?** Yes.
2. **Action visible?** Yes — the consultation queue lists waiting tokens.
3. **Association?** Yes, if they know the token. ⚠️ If the patient is at another
   stage, the clinician cannot search for them from this screen (heuristic
   finding F4).
4. **Progress visible?** Yes.

### B2. Open the priority control

1. **Right effect?** Yes.
2. **Action visible?** Yes — a "Priority" button on every row, shown only to
   roles permitted to use it, so it is never a dead control.
3. **Association?** Yes. "Priority" is the word the spec and the staff use.
4. **Progress visible?** Yes — a dialog opens naming the token.

### B3. Choose emergency and give a reason

1. **Right effect?** Yes.
2. **Action visible?** Yes. Emergency is the first option, described as
   "immediate clinical attention".
3. **Association?** Yes. ⚠️ **Minor friction:** a reason is mandatory. Under
   pressure that is one more step — but it is the requirement (FR5), and the
   reasons are pre-written categories rather than a text box, so it is one tap.
   The dialog says up front that role, time and reason are recorded.
4. **Progress visible?** Yes — the button changes to "Saving…", then the row
   updates.

### B4. Confirm the patient is now first

1. **Right effect?** Yes — under pressure a clinician wants to *see* it worked.
2. **Action visible?** No action needed; the queue reorders itself.
3. **Association?** Yes. The row moves to the top and the emergency row carries
   a red bar and tag.
4. **Progress visible?** Yes, and every other terminal updates at the same
   moment, so a nurse looking at another screen sees the same thing.

### B5. Be confident it was recorded

1. **Right effect?** ⚠️ They may not think to check, which is fine.
2. **Action visible?** ⚠️ **Weak point.** There is no on-screen confirmation
   that the decision was written to the audit trail — the clinician is told
   beforehand in the dialog, but not afterwards. Given that the trail exists to
   protect them as much as the patient, a brief "Recorded" acknowledgement
   would be reassurance worth having.
   **Recommendation:** a short confirmation toast naming what was recorded.
   Deferred; it is an addition, not a defect.

---

## What the walkthroughs predict

| Weak point | Where | Suggested response |
|---|---|---|
| Patient cannot find the URL | Outside the software | Print URL + QR on the token slip — the biggest adoption risk |
| "Wait time unavailable" may read as broken | Patient view | Measure in testing before rewording |
| Priority explanation is collapsed | Patient view | Expand by default if testing falls below 80% |
| Cannot search a token at another stage | Staff dashboards | Heuristic finding F4 |
| No acknowledgement that an override was recorded | Clinician | Confirmation toast |

None of these blocks task completion. All five are worth putting in front of
real users before deciding anything, which is what the protocol in
[`usability-test-protocol.md`](./usability-test-protocol.md) is for.
