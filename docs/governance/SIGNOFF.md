# Governance sign-off register

**Status: PARTIAL — approved for academic-prototype development on fictional
data only. G3, G4 and G5 remain PENDING, and no real patient data may be
handled under any circumstances.**

This register is the authoritative record of institutional sign-off for the
Digital Queue & Patient-Flow Management System. Items below are the decisions
that [`spec.md`](../../spec.md) flags as requiring Medical Center / University
governance approval, and that [`TASKS.md`](../../TASKS.md) tags
`[GOV SIGN-OFF]`.

It is machine-read by [`tools/check_signoff.py`](../../tools/check_signoff.py),
which the pre-commit hook runs. While an item is `PENDING`, commits that touch
its blocked paths are refused, and ticking its task in `TASKS.md` fails the
check. See [`README.md`](./README.md) for how to record an approval.

**Do not edit the `Status:` line of an item unless you are recording a real
decision made by the named approving body.** Marking an item `APPROVED` is an
assertion that the approval happened, is minuted, and that the evidence link
below points at it.

---

## G1 — Build authorisation

```yaml
id: build-authorisation
status: APPROVED
approver: Joshua Tuitoek (project lead), academic-prototype scope
approval_date: 2026-07-30
evidence: Project-lead authorisation, 30 July 2026 — NOT a governance-committee minute. Scope limited to prototype development on fictional data.
```

> **Scope of this approval.** It confirms the team's technical defaults (Django +
> DRF + PostgreSQL + Channels, Next.js, Africa's Talking, the position ×
> rolling-median wait range, JWT auth) and authorises prototype development on
> **fictional data only**, as the HCI/UCD coursework the brief describes. It is
> **not** a Medical Center / University governance decision, and it does not
> approve G3, G4 or G5. Any move toward a real-data pilot requires those items
> approved by the actual governance body and re-recorded here.

**What must be approved:** that the proposed-default decisions in the spec's
*Resolved decisions* section are confirmed by the team (stack, SMS provider,
waiting-range method, auth method), and that the governance and clinical-policy
items G2–G5 have been put to the Medical Center / University governance body.

**Why it gates:** [`spec.md`](../../spec.md) *Build-from-zero steps*, step 2 —
confirmation and sign-off happen **before writing feature code**.

**Approving body:** Project team (technical defaults) + Medical Center /
University governance (policy items).

**Blocks tasks:** Phase 0 — "Confirm proposed-default decisions … before writing
feature code".

**Blocks paths:**

- `backend/queueapp/models.py`
- `backend/queueapp/serializers.py`
- `backend/queueapp/permissions.py`
- `backend/queueapp/services/`
- `backend/queueapp/consumers.py`

---

## G2 — Token ↔ medical-record linkage

```yaml
id: record-linkage
status: APPROVED
approver: Joshua Tuitoek (project lead), academic-prototype scope
approval_date: 2026-07-30
evidence: Project-lead authorisation, 30 July 2026 — NOT a governance-committee minute. Approves the decoupled design for a fictional-data prototype.
```

> **Scope of this approval.** It authorises building the **decoupled** design —
> anonymous token, internal `visit_id`, no clinical data in the queue database,
> station-side lookup kept outside it. That is the minimal-data option, so
> building it now cannot over-collect: a later governance decision could only
> ever narrow it further or leave it as is. It does **not** authorise holding
> real patient identity in any form; that needs G5 and the real governance body.

**What must be approved:** that the queue token and the medical record stay
**decoupled** — the queue stores an internal `visit_id`, the patient-facing
token is anonymous, the queue database holds **no** clinical or medical-record
data, and authorised staff map token → patient through a station-side lookup
kept outside the queue database. The system does not replace the medical record.

**Why it gates:** this determines how patient identity is (and is not) held, and
so falls under the Data Protection Act's treatment of health data as sensitive
personal data.

**Approving body:** Medical Center / University governance, with the named data
controller.

**Blocks tasks:** Phase 1 — "Enforce token ↔ medical-record decoupling".

**Blocks paths:**

- `backend/queueapp/models.py`

---

## G3 — Audit granularity

```yaml
id: audit-granularity
status: PENDING
approver:
approval_date:
evidence:
```

**What must be approved:** the two-layer model — (1) an **identifiable** audit
trail recording the specific staff user, role and reason for accountability
actions such as emergency overrides and manual reorders; (2) **de-identified,
aggregate** analytics and reporting that expose no individual actor.

**Why it gates:** it determines what identifiable staff data is retained and for
how long, and it is the point where the accountability requirement and the
non-identifying-reporting requirement have to be reconciled.

**Approving body:** Medical Center / University governance, with staff
representation — this is monitoring of named employees.

**Blocks tasks:** Phase 8 — "Implement identifiable audit trail".

**Blocks paths:**

- `backend/queueapp/audit.py`
- `backend/queueapp/reporting.py`

---

## G4 — Management vs IT/Support permission boundary

```yaml
id: permissions-boundary
status: PENDING
approver:
approval_date:
evidence:
```

**What must be approved:** that **Management/Supervisor** gets de-identified
analytics, staffing views, queue configuration and emergency-override oversight
with **no** system or user administration; that **IT/Support** gets system
configuration, user/account management, deployment and monitoring plus
system-health analytics with **no** clinical-override capability and **no**
access to clinical analytics; and that neither role may assign clinical
priority.

**Why it gates:** this boundary decides who can see accountability and oversight
data about named clinical staff.

**Approving body:** Medical Center / University governance.

**Blocks tasks:** Phase 2 — "Implement Management/Supervisor vs IT/Support
permission boundary".

**Blocks paths:**

- `backend/queueapp/oversight.py`

> **Why this path and not `permissions.py`.** This item originally blocked the
> whole permissions module, which was too coarse: the six roles' least-privilege
> rules and the FR3 clinical-priority restriction come from the spec's
> functional requirements, not from a governance decision, and blocking them
> stalled work this item does not govern. What G4 actually decides is *who may
> see oversight and accountability data* — so the gate now sits on
> `oversight.py`, the module that would grant Supervisor and IT/Support their
> capabilities.
>
> The effect while this item is `PENDING` is that `oversight.py` does not exist,
> and `permissions.py` therefore grants Supervisor and IT/Support **no
> capabilities at all**. The gate fails closed: it withholds access rather than
> merely delaying a file.

---

## G5 — Pre-pilot governance

```yaml
id: pre-pilot-governance
status: PENDING
approver:
approval_date:
evidence:
```

**What must be approved, before any real patient data is handled:**

- **Data controller** — proposed: Kabarak University Medical Center.
- **Retention** — proposed: live queue tokens purged at end of day (or within
  24–48h); audit logs retained ~12 months; aggregate de-identified analytics
  may be kept longer.
- **Patient phone numbers** — proposed: purged with the visit at end of day.
  A phone number given for SMS alerts (FR11) is the only identifying field in
  the queue database, held in its own `NotificationContact` table so it can be
  purged on its own schedule. Its retention was not covered when this item was
  first drafted and is added here for the same approval.
- **Incident response** — proposed: a named system owner, a documented
  breach-notification step, and a defined rollback to the manual offline
  fallback.

**Why it gates:** these are the conditions under which the spec permits a
real-data pilot at all. Until they are approved, the system runs on **fictional
data only**.

**Approving body:** Medical Center / University governance.

**Blocks tasks:** Phase 10 — "Complete pre-pilot governance checklist".

**Blocks paths:**

- `deploy/production/`

---

## Standing constraint

Regardless of the items above, and not waivable by this register: the prototype
uses **fictional records only**. Any use of real patient data requires G5
approved *and* a separate, explicit decision to begin a pilot.
