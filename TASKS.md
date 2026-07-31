# TASKS — Digital Queue & Patient-Flow Management System

> **Source of truth:** [`spec.md`](./spec.md) in this folder. Every task below derives from the spec's *Build-from-zero steps*, FR1–FR14, the data model, and the *Resolved decisions*. When spec and this list disagree, spec wins. Governance-dependent tasks are tagged **[GOV SIGN-OFF]** — they must not proceed to real-data use until Medical Center / University governance approves the relevant item (see spec *Resolved decisions* and *Assumptions*). No secret values appear here or in the repo — only env-variable *names*.

---

## Phase 0 — Project setup

- [x] Create repo structure: `frontend/`, `backend/`, `docs/`, shared types/config
- [x] Add `.gitignore` (Python, Node, env files, build artifacts)
- [x] Copy `spec.md` into the repo and reference it from the README
- [x] Add `.env.example` with variable **names only** (DB URL, Django secret key, JWT signing key, SMS API key/secret, SMS sender ID, hosting host/port) — no values
- [x] Scaffold Django project + Django REST Framework backend
- [x] Add and configure PostgreSQL; document local prototype fallback to SQLite (prototype only)
- [x] Add Django Channels + ASGI server config (real-time transport groundwork)
- [x] Scaffold Next.js / React frontend app with accessible component baseline
- [x] Set up environment/config loading (env-var based; no secrets committed)
- [x] **[GOV SIGN-OFF] (G1)** Confirm proposed-default decisions with the team (stack, SMS provider, waiting-range method, auth method) and secure institutional sign-off on governance/clinical-policy items **before writing feature code** (spec step 2) — approved for **academic-prototype scope, fictional data only**; see G1 in [`docs/governance/SIGNOFF.md`](./docs/governance/SIGNOFF.md). Enforced by the pre-commit gate, not by this checkbox.

## Phase 1 — Data models & migrations

- [x] Define `StaffUser` / `Role` model with the six roles (Registration Clerk, Nurse/Vitals, Clinician, Pharmacist, Supervisor/Admin, IT/Support)
- [x] Define `Visit` model: internal `visit_id`, anonymous `token`, `check_in_time`, `current_stage`, `stage_status`, `priority`, `presence_status`, `notification_preference` — no names/diagnoses/prescriptions
- [x] Define `StageEvent` model: `visit`, `stage`, `entered_at`, `completed_at`, `completed_by_role` (preserves stage history for return-after-tests)
- [x] Define `PriorityChange` model: `visit`, `new_priority`, `changed_by_role`, `timestamp`, `non_sensitive_reason`
- [x] Define `PharmacyOutcome` model: `visit`, `state` (ready / issued / unavailable), `by_role`, `timestamp`
- [x] Define `AuditLogEntry` model: `actor_staff_user`, `actor_role`, `action`, `timestamp`, `visit_token`, `non_sensitive_detail` — table only; nothing writes to it until G3 (Phase 8)
- [x] Wire relationships (Visit → many StageEvents, PriorityChanges, PharmacyOutcomes, AuditLogEntries)
- [x] **[GOV SIGN-OFF] (G2)** Enforce token ↔ medical-record decoupling: queue DB holds no clinical data; station-side lookup stays outside the queue DB (depends on linkage sign-off)
- [x] Generate and apply migrations
- [x] Create a fictional-data seed script (spec: prototype records must be fictional)

## Phase 2 — Auth & RBAC

- [x] Configure Django auth with JWT (`djangorestframework-simplejwt`) or server sessions; keys from env
- [x] Implement role-based permission classes for all six roles, least privilege
- [x] Restrict priority assignment to clinical roles only (Nurse/Vitals, Clinician); block Reception and Pharmacy (FR3)
- [ ] **[GOV SIGN-OFF] (G4)** Implement Management/Supervisor vs IT/Support permission boundary (analytics/oversight vs system/user admin; neither assigns clinical priority) — **BLOCKED**. Effect while pending: `oversight.py` does not exist, so both roles authenticate and hold **no** capabilities and no dashboard.
- [x] Add login/logout endpoints and per-role dashboard authorization guards
- [x] Write access-control tests: each role can only reach its permitted actions

## Phase 3 — Queue engine (application service layer)

- [x] Implement check-in endpoint: record `check_in_time`, issue anonymous human-readable token e.g. `T-041` (FR1)
- [x] Implement routine ordering by check-in time **within each stage** (FR2)
- [x] Implement stage transitions: registration → vitals → consultation → pharmacy → complete (FR6)
- [x] Implement stage-completion actions: vitals complete, consultation complete, medicine ready/issued/unavailable (FR10)
- [x] Implement priority-change endpoint restricted to clinical roles; record role, timestamp, non-sensitive category (FR3, FR5)
- [x] Implement emergency override: route case immediately to appropriate clinical service ahead of routine queue; never block on system state (FR4)
- [x] Implement urgent priority: next appropriate clinical slot
- [x] Implement manual routine-reorder requiring a logged reason
- [x] Implement presence statuses: called → recalled → temporarily-away → missed-turn → resumed, with recall/recovery route (FR9)
- [x] Implement return-to-clinician after lab tests without losing prior stage history (FR13)
- [ ] Write audit-log entries for every priority change, manual reorder, and key completion (FR14) — **BLOCKED by G3**. The engine emits every accountability event to an audit seam; `queueapp/audit.py` (the write path) is gated, so the events are currently discarded and a warning says so at startup.
- [x] Establish single authoritative queue state as source of truth for all channels
- [x] Write unit tests for ordering, override precedence, and stage-transition correctness

## Phase 4 — Real-time (Django Channels / WebSockets)

- [x] Configure Channels consumers and channel layer
- [x] Push queue-state changes to the patient status view
- [x] Push queue-state changes to staff dashboards
- [x] Push queue-state changes to the public display board
- [x] Ensure public-channel payloads carry anonymous token + destination only (no names/category/medical detail)
- [x] Handle reconnection/state resync so a reconnecting client gets current state
- [x] Test real-time propagation across patient / staff / public channels

## Phase 5 — Frontends

- [x] Build patient status view: token, current stage, people-ahead count, cautious waiting range, last-update time — plain accessible language (FR7)
- [x] Build public display board: anonymous token + destination only, e.g. "T-041 → Consultation" (FR8)
- [x] Build Reception dashboard: register patient, capture check-in, issue token, operate manual fallback
- [x] Build Nurse/Vitals dashboard: view priority + stage, mark vitals complete, recall/skip, transfer to consultation, assign clinical priority
- [x] Build Clinician dashboard: priority queue, consultation complete, assign emergency/urgent with logged reason, return-after-tests, transfer to pharmacy
- [x] Build Pharmacy dashboard: pharmacy queue, mark medicine ready/issued/unavailable, close visit
- [x] Show priority tags on staff screens only; never expose urgency category or health detail on public/patient screens
- [x] Apply WCAG 2.2 across all views (contrast, keyboard focus, target sizes, clear errors, non-smartphone-friendly alternatives) — reviewed by construction; an assistive-technology pass belongs with the Phase 10 evaluation

## Phase 6 — Wait-range calculation

- [ ] Compute rolling median service time per stage over the last N completed services
- [ ] Compute base estimate = position-in-stage × rolling median
- [ ] Apply ±30% buffer and round to a coarse band (e.g. "about 10–20 min")
- [ ] Degrade to "wait time unavailable" when data is thin (too few completed services for a reliable median)
- [ ] Always present a range, never a single countdown; surface in patient view
- [ ] Test range output and the thin-data unavailable path

## Phase 7 — SMS notifications (optional channel)

- [ ] Build a notification module abstraction; screen + printed token are core, SMS/phone optional (FR11)
- [ ] Integrate Africa's Talking SMS behind env-based credentials (Twilio as alternative interface)
- [ ] Send optional stage-change alerts per patient `notification_preference`
- [ ] Ensure SMS is the only component needing outbound internet; core queue works without it
- [ ] Test with SMS disabled to confirm core flow is unaffected

## Phase 8 — Audit log & de-identified reporting

- [ ] **[GOV SIGN-OFF] (G3)** Implement identifiable audit trail (staff user + role + reason) for accountability actions — overrides, manual reorders, key completions (depends on audit-granularity sign-off)
- [ ] Build de-identified, aggregate analytics/reporting exposing no individual actor
- [ ] Build management review view over the audit log for authorised roles (FR14)
- [ ] Verify no clinical or identifying patient data leaks into reports

## Phase 9 — Local / LAN deployment

- [ ] Package backend (Django + DRF + PostgreSQL + Channels) to run on an always-on local machine
- [ ] Configure LAN access for staff terminals, patient view, and public-display screens (no cloud dependency for core operation)
- [ ] Set up regular local database backups and a documented recovery path
- [ ] Document power/UPS and single-point-of-failure mitigation (spare box / recovery path)
- [ ] Write the manual offline fallback procedure (paper/verbal) and later-reconciliation steps (FR12)
- [ ] Store any credentials in the machine's environment / secrets store, never in the repo

## Phase 10 — Testing & pilot readiness

- [ ] Complete unit tests (queue ordering, priority policy, wait-range, RBAC)
- [ ] Complete integration tests across queue engine + real-time + frontends
- [ ] Test exceptional paths: emergency interruption, temporarily-away/missed-turn/recall recovery, return-after-tests, medicine-unavailable
- [ ] Rehearse the manual offline fallback and reconciliation end-to-end
- [ ] Produce low-fidelity wireframes → high-fidelity clickable prototype covering all spec §4.9 items (fictional data only)
- [ ] Run evaluation: heuristic evaluation, cognitive walkthrough, task-based usability testing (targets: ≥80% unaided core-task completion, no unresolved critical safety/privacy defect, mean ease-of-use ≥4/5, ≥80% correctly explain routine vs emergency priority)
- [ ] **[GOV SIGN-OFF] (G5)** Complete pre-pilot governance checklist: data controller, retention rules, incident response / breach notification, rollback to manual fallback — all approved before any real-data pilot (spec *Assumptions*)
- [ ] Refine based on evaluation findings (UCD is iterative)
