# Queue Management System — Build Spec

**System:** Digital Queue and Patient-Flow Management System for Kabarak University Medical Center
**Source brief:** `Kabarak_HCI_Digital_Queue_Full_Academic_Report_2026.docx` (Downloads, downloaded 30 July 2026)
**Spec status:** v1 build spec derived entirely from the source brief. Points the brief does not state are resolved as **Decisions (proposed defaults — confirm before build)**; where a default touches governance or clinical policy it is flagged as requiring institutional sign-off.

> Scope note from the brief: this is an HCI/UCD design-and-prototype project. The brief explicitly does **not** claim production deployment and states a larger pilot with governance approval is required before real clinical use. This spec is written to build the prototype the brief specifies (registration → vitals → consultation → pharmacy queue with clinical priority, progress visibility, privacy and a manual fallback), not a full hospital information system.

---

## Purpose & scope

**What the system is.** A user-centred digital queue and patient-flow management system for outpatient visits at Kabarak University Medical Center. It gives each visit a single anonymous token that persists across every service stage, makes routine check-in order visible and traceable, lets authorised clinical staff override routine order for emergency/urgent cases, communicates progress to patients privately, keeps an audit trail, and stays usable during technical disruption through a documented manual fallback.

**What it must do (from the brief).** Cover the outpatient journey end to end: identification and registration, vital signs, clinical consultation, and medication collection. Record check-in time and issue an anonymous token; order routine patients by check-in time within each stage; support authorised clinical prioritisation (emergency / urgent / routine); track the visit through all stages; show patients their token, stage, people-ahead count and a cautious waiting range; display anonymous tokens publicly without names or medical detail; support call / recall / temporarily-away / missed-turn / resumed states; let staff mark stage completions and pharmacy outcomes; provide screen, printed-token and optional SMS/phone channels; support return-to-clinician after lab tests; and provide role-based dashboards plus an audit log.

**Out of scope / explicitly excluded (from the brief).** The system does not diagnose patients, does not automatically determine clinical urgency, does not replace the medical record/EHR, does not prescribe medicine, and does not claim production deployment. A purely first-come-first-served rule is rejected as clinically inappropriate.

**Future / not in v1 (from the brief).** Integration with student identity services and with OpenMRS/EHR is a design goal for interoperability but is **not** required for the prototype. A measured pilot precedes any procurement or production decision.

---

## Users & roles

Derived from the brief's context-of-use table and use-case model, which separates patient information needs from staff actions and restricts priority assignment to clinical roles.

**Primary users — patients (students and university staff).** Seek care, including first-time and repeat visitors, people under stress, users with disabilities, and users without smartphones. They can: present identification, confirm details, receive a token, view their own token / current stage / people-ahead / waiting range / last update, and receive notifications. Patients do not see other patients' identities or any medical detail.

**Operational users — clinic staff.**
- *Reception / records personnel:* register a patient, capture check-in time, issue a token, operate the manual fallback and later reconciliation, and close visits abandoned for 24 hours (see *Queue policy → Abandoned visits*).
- *Nurse / vital-signs (triage) staff:* view priority and current stage, mark vitals complete, recall/skip, transfer the token to consultation; may assign clinical priority (authorised clinical role).
- *Doctor / clinical officer:* view priority queue, conduct consultation, assign emergency/urgent priority with a logged reason, return a patient after lab tests, transfer to pharmacy.
- *Pharmacy personnel:* view the pharmacy queue, mark medicine ready / issued / unavailable, close the visit.

**Supporting users.** Medical Center management (review dashboards and audit log) and authorised IT/support personnel.

> **Decision (proposed default — confirm before build):** Separate the two supporting roles by least-privilege boundary. **Management / Supervisor** = de-identified analytics, staffing views, queue configuration, and emergency-override oversight — with **no** system or user administration. **IT / Support** = system configuration, user/account management, deployments and monitoring, plus system-health (not clinical) analytics — with **no** clinical-override capability and no access to clinical analytics. Neither role can assign clinical priority. *This boundary defines who can see accountability/oversight data, so it requires institutional (Medical Center / University governance) sign-off before build.*

**Priority-assignment restriction.** Only authorised clinical roles (nurse/triage, doctor/clinical officer) may set emergency or urgent priority. Reception and pharmacy cannot. Every priority change records role, timestamp and a non-sensitive category/reason.

---

## Core features & flows

### v1 features (from the brief's functional requirements FR1–FR14)

- **FR1** Record check-in time and issue an anonymous visit token.
- **FR2** Place routine patients in check-in order within the relevant service stage.
- **FR3** Allow only authorised clinical roles to assign emergency or urgent priority.
- **FR4** Move an emergency case immediately to the appropriate clinical service without waiting for the routine queue.
- **FR5** Record the user role, timestamp and non-sensitive category for each priority change.
- **FR6** Track the visit through registration, vital signs, consultation, pharmacy and completion.
- **FR7** Show patients their token, current stage, people ahead, waiting range and last update.
- **FR8** Display anonymous tokens and destinations publicly without names, diagnoses or prescriptions.
  > **Widened in build (v1).** The brief's requirement is a floor, not a ceiling: the public screen shows anonymous tokens and destinations, and the build shows *every* patient currently in the clinic under the stage they are at, not only those being called forward. The prohibitions are unchanged and absolute — no names, no priority categories, no diagnoses, no prescriptions. Rationale and the privacy analysis are in [`docs/design/tracking-board.md`](docs/design/tracking-board.md).
- **FR9** Support call, recall, temporarily-away, missed-turn and resumed statuses.
- **FR10** Allow staff to mark vital signs complete, consultation complete, medicine ready, medicine issued or unavailable.
- **FR11** Provide screen, printed-token and optional SMS/phone channels.
- **FR12** Provide a documented manual fallback and later reconciliation after technical failure.
- **FR13** Support return to the clinician after laboratory tests or treatment.
- **FR14** Provide role-based dashboards and an audit log for authorised management review.

### Queue policy (from the brief)

Three priority levels. The digital interface supports but never makes the clinical decision, and must never delay emergency care.

| Priority | Service rule | Who may set it | Patient-facing message |
|---|---|---|---|
| Emergency | Immediate clinical attention | Qualified nurse/triage, doctor or clinical officer | "Emergency cases may be served immediately." |
| Urgent | Next appropriate clinical slot | Authorised clinical staff | "Urgent cases may be served before routine cases." |
| Routine | Order by recorded check-in time within the stage | System order; staff changes require a logged reason | Token, stage, people ahead, waiting range |

#### Abandoned visits (build decision, not from the brief)

A visit ends when pharmacy is finished with the patient, not when the day ends. That is what lets the tracking board be honest about who is in the building, and it is also what leaves a visit open when somebody goes home without telling anyone — nothing in the clinical flow will ever close it.

| Rule | Value |
|---|---|
| A visit is **stale** when | nothing has happened to it for **24 hours** (`STALE_VISIT_HOURS`) |
| Measured from | `last_updated` — the last thing that actually happened to the visit, not check-in time. A patient seen at vitals last night is mid-journey; one whose record has not moved since check-in went home. |
| Who closes it | **Reception.** It is the desk that knows who walked back out. |
| How | By hand, from a list on the reception dashboard — deliberately not a scheduled job. A visit left open is a patient the clinic has lost track of, and somebody noticing that is worth more than a cron entry quietly tidying it away. |
| Guard | The 24-hour threshold is enforced **on the server**. The capability is "close what has clearly been abandoned", never "remove a patient from the queue". |
| Recorded as | An **accountability action** in the audit log, naming the individual clerk — if the judgement was wrong, somebody who was still waiting has been removed from every queue. |
| Effect | The visit is closed at the stage it stopped at. It is *not* rewritten to "complete": that would tell the reports somebody collected medication they never received. |

Closing a stale visit is an operational action on the queue. It is **not** data retention — the visit record and its audit trail are retained on their own schedules (see *Decisions & constraints*).

### Main flows

**Patient happy path.** Present student/staff card at reception → details confirmed, check-in time recorded, anonymous token issued (screen + optional printed token) → wait for vitals (status: *waiting for vitals*) → vitals taken, staff marks *vitals complete* → wait for clinician (*waiting for clinician*) → consultation, clinician marks *consultation complete* → pharmacy (*medicine ready* when prepared) → medicine issued → visit complete. Throughout, the patient can view token, current stage, people ahead, cautious waiting range and last-update time; optional SMS/phone alerts on stage change.

**Public waiting-room display (the tracking board).** One column per place in the clinic — Reception, Vital signs, Consultation, Pharmacy — each listing the anonymous tokens currently there, with the desk or room beside a token that has just been called (e.g. "K492 → Consultation Room 1"). A patient appears from check-in and leaves only when pharmacy is finished with them, so anyone in the building can find their own token and see how far along they are without asking at a desk. Never shows names, priority category, diagnoses or prescriptions.

Columns are ordered by **arrival, not service order**. The queues themselves run emergencies first; publishing that order would let the room infer which patients have been given a clinical priority, which is the priority category disclosed by another route.

**Emergency/urgent override.** An authorised clinical user marks a token emergency or urgent → the case moves immediately to the appropriate clinical service ahead of the routine queue → system records role, timestamp and non-sensitive reason to the audit log → public display still shows only anonymous tokens (urgency category is not exposed publicly).

**Exceptional paths the interface must support (from the brief's HTA).**
- *Emergency interruption* — see override flow above.
- *Temporarily away / missed turn* — statuses call → recall → temporarily-away → missed-turn → resumed; patient can recover their place via a defined recall/fallback route.
- *Return after laboratory tests* — patient returns to the clinician without losing prior stage history (FR13).
- *Medicine unavailable* — pharmacy records the unavailable-medicine status and the visit state reflects it.
- *Technical failure* — documented manual fallback (paper/verbal) operates, with later reconciliation into the system (FR12).

### Prototype build (from the brief, section 4.9)

Two low-fidelity alternatives (patient status view + role-based staff dashboard) precede one high-fidelity clickable prototype. The high-fidelity prototype must cover: registration and token issue; patient progress; anonymous waiting-room display; vitals completion; authorised priority; consultation transfer; pharmacy readiness; missed-turn recovery; return after tests; medicine-unavailable status; and offline fallback messaging. Visual priority tags may appear on staff screens only; public screens must not expose urgency categories or health details. **All prototype records must be fictional.**

---

## Stack + why

> **The brief does not specify a technology stack.** It refers only to "established web, notification and queue technologies," a "lightweight application service layer so that patient channels and staff dashboards share one queue state," free/educational tooling, and OpenMRS O3 as a future integration route. The stack must be confirmed against those constraints before build.
>
> **TODO — confirm: technology stack (frontend, backend, database, real-time transport) — not yet decided.** A specific stack was previously proposed here from prior research/assumptions that had not been cleared; it has been returned to an open item pending the user's explicit go-ahead. Surface the options when relevant; do not bake one in.

- **Frontend (patient view, staff dashboards, public display):** a single web application (responsive, browser-based) so patients on phones, staff on clinic computers, and a shared waiting-room screen all use one codebase. *Why:* the brief calls for screen-based patient/public views and role-based staff dashboards sharing one queue state, and for WCAG 2.2-compliant, non-smartphone-friendly interfaces. **TODO — confirm: frontend framework — not yet decided** (part of the open technology-stack item above).
- **Backend / application service layer:** a lightweight HTTP API service holding the single authoritative queue state and enforcing role-based access and the priority policy. **TODO — confirm: backend framework — not yet decided** (part of the open technology-stack item above).
- **Real-time updates:** push stage/priority changes to patient views, staff dashboards and the public display promptly (brief's Performance NFR). **TODO — confirm: real-time transport — not yet decided** (part of the open technology-stack item above).
- **Database:** a relational store for visits, stages, priority changes and the audit log (structured, auditable, supports ordering by timestamp). **TODO — confirm: database — not yet decided** (part of the open technology-stack item above). *Why a relational store:* the audit and accountability NFRs need durable, queryable, timestamped records.
- **Notifications:** screen + printed token are core; SMS/phone is optional. **TODO — confirm: SMS provider for the optional notification channel.** An SMS gateway sits behind a small notification module (see External dependencies); the provider is not yet decided (previously proposed from uncleared prior research). Credentials live in environment variables, never in the repo.
- **Accessibility:** implement to WCAG 2.2 (readable text, sufficient contrast, visible keyboard focus, adequate target sizes, clear errors, non-smartphone alternatives) — this **is** a brief requirement, not a proposal.

---

## Architecture & data model

### Components (from the brief's proposed architecture)

A lightweight application service layer holds one shared queue state consumed by multiple channels:

- **Patient channel** — personal status view (token, stage, people ahead, waiting range, last update) + optional SMS/phone alerts.
- **Public display channel** — the tracking board: for every patient in the clinic, an anonymous token, the stage they are at, the desk or room if one has been named, and whether they are being called. Nothing else, and no field in the payload that could carry anything else.
- **Staff dashboards** — role-based views for reception, nurse/triage, clinician and pharmacy, each exposing only the actions and information that role needs.
- **Application service layer** — enforces routine ordering, the priority policy, role-based access, stage transitions and audit logging; single source of truth for queue state.
- **Data store** — visits, stages, priority/reason records, audit log.
- **Manual fallback + reconciliation** — documented offline procedure and a path to reconcile paper records back into the system after failure.
- **Optional/future integrations** — student identity services and OpenMRS O3 / EHR (not required for v1).

### Data entities (derived from FR1–FR14 and the policy/HTA)

- **Visit** — key fields: `token` (anonymous, human-readable e.g. K492), `token_period` (the window the token is reserved for; the token is unique within it, not for all time), `check_in_time`, `last_updated`, `closed_at`, `current_stage` (registration | vitals | consultation | pharmacy | complete), `stage_status` (waiting | in-progress | complete for the stage; plus waiting-for-vitals / vitals-complete / waiting-for-clinician / consultation-complete / medicine-ready etc.), `priority` (emergency | urgent | routine), `presence_status` (called | recalled | temporarily-away | missed-turn | resumed), `notification_preference` (screen | printed | SMS/phone). No names, diagnoses, symptoms or prescriptions stored in the queue system (privacy requirement).
  > **Token generation (build decision).** Tokens are drawn at **random** — one letter then three digits, from an alphabet excluding O, I, L and S — rather than issued in sequence, and are unique within a **token period** (one week by default) rather than within a day. Both follow from the tracking board: a sequential token published next to every other token in the building would disclose arrival order and the clinic's running total, and a visit that ends at pharmacy rather than at midnight cannot have a token scoped to the day. See [`docs/design/tracking-board.md`](docs/design/tracking-board.md).
  > **Decision (proposed default — confirm before build):** Keep the queue token and the medical record **decoupled**. The queue stores an internal `visit_id`; the public/patient-facing token is anonymous. The queue database holds **no** clinical or medical-record data and does not replace the medical record. Authorised staff at a station can map token → patient via a **station-side lookup**, kept outside the queue DB. *This linkage model governs how patient identity is (not) held, so it requires institutional (Medical Center / University governance) sign-off before build.*
- **Stage / StageEvent** — `visit_token`, `stage`, `entered_at`, `completed_at`, `completed_by_role`. Supports FR6 tracking and FR13 return-after-tests (prior stage history preserved).
- **PriorityChange** — `visit_token`, `new_priority`, `changed_by_role`, `timestamp`, `non_sensitive_reason/category`. Restricted to authorised clinical roles (FR3, FR5).
- **PharmacyOutcome** — `visit_token`, `state` (medicine-ready | issued | unavailable), `by_role`, `timestamp` (FR10).
- **AuditLogEntry** — `actor_staff_user`, `actor_role`, `action` (priority change, manual reorder, key completion), `timestamp`, `visit_token`, `non_sensitive_detail`. Supports accountability NFR and FR14.
  > **Decision (proposed default — confirm before build):** Use **two layers**. (1) An **identifiable audit trail** stores the specific staff user + role and a reason for accountability actions such as emergency overrides and manual reorders. (2) All **analytics and reporting are de-identified and aggregate** — no individual actor is exposed in reports. This reconciles the brief's accountability requirement with its emphasis on non-identifying reporting. *Because it determines what identifiable staff data is retained, it requires institutional (Medical Center / University governance) sign-off before build.*
- **StaffUser / Role** — `role` (Registration Clerk | Nurse/Vitals | Clinician | Pharmacist | Supervisor/Admin | IT/Support), authentication credentials, permissions.
  > **Decision (proposed default — confirm before build):** Authenticate with **Django auth** using **JWT (`djangorestframework-simplejwt`) or server-side sessions**, with **role-based access control** across the six roles above (Registration Clerk, Nurse/Vitals, Clinician, Pharmacist, Supervisor/Admin, IT/Support), applying **least privilege** per role. Credentials/signing keys live in environment variables, never in the repo.

**Relationships:** one Visit has many StageEvents, many PriorityChanges, one-or-more PharmacyOutcomes, and generates many AuditLogEntries. Each staff action is attributed to a Role and, for accountability actions, an identifiable StaffUser (see the audit-granularity Decision above).

---

## External dependencies & where secrets live

The brief references these third-party/external elements by name only. **No secret values appear in this spec or repo.**

- **SMS / phone notification gateway** — optional channel (FR11). The brief mentions "SMS testing" in the pilot budget but names **no provider**. **TODO — confirm: SMS provider for the optional notification channel.** Not yet decided; a provider was previously proposed here from prior research/assumptions that had not been cleared, so it is returned to an open item. Any provider is referenced by name only. Credentials (API key/secret, sender ID) live in **environment variables / a secrets manager**, never in source control. Provide a `.env.example` with key *names* only.
- **Hosting** — the brief budgets for "pilot web hosting" but names no host. **TODO — confirm: hosting/deployment approach.** Not yet decided; a specific hosting setup was previously proposed here from prior research/assumptions that had not been cleared, so it is returned to an open item.
  > **User preference:** v1 is hosted LOCALLY / on-premise; exact setup to be decided.

  *If the local/on-premise direction is confirmed*, note the operational needs it implies: a reliable always-on local machine/server (its availability is load-bearing — a single box is a single point of failure, so plan power/UPS and a spare or recovery path); the LAN/Wi-Fi that the screens and terminals depend on; regular local backups; and, only if outbound SMS notifications are used, internet access for that one outbound call. Any credentials live in the machine's environment / a secrets store, not in the repo.
- **OpenMRS O3 / EHR integration (future, optional)** — reference: OpenMRS O3 patient-management and service-queue modules. Not required for v1. When implemented, any integration credentials live in environment/secret storage.
- **Student identity services (future, optional)** — for identity confirmation at registration; not required for v1. Credentials, if ever used, live in environment/secret storage.

Rule for the build: all API keys, tokens, database URLs and SMS credentials are referenced by environment-variable name and stored in a secrets manager or the host's environment. The repo contains only a `.env.example` listing variable names with placeholder/empty values.

---

## Decisions & constraints

**Key design decisions (from the brief).**
- One anonymous token persists across all four stages (a single visit identity, not per-stage tickets). *Build detail: the token is random rather than sequential and reserved for a week rather than a day — see* Data entities → Visit.
- A visit ends when pharmacy is finished with the patient, not at the end of the day. *Build consequence: one abandoned halfway is closed by reception after 24 hours of inactivity — see* Queue policy → Abandoned visits.
- Routine fairness = serve by recorded check-in time *within the correct stage*; clinical urgency can override time order, but only via an authorised, logged clinical decision.
- The system communicates and records priority; it never computes clinical urgency and never delays emergency care.
- Public information is anonymous and minimal; sensitive/priority information is restricted to the relevant staff role.
- The system must remain usable offline via a documented manual fallback with later reconciliation.
- Waiting information is a *cautious range plus stage*, not a precise time promise (literature showed exact estimates don't reliably improve satisfaction).
  > **Decision (proposed default — confirm before build):** Compute a cautious **range**, never a single countdown. Base estimate = `position-in-stage × rolling median service time for that stage`, where the median is taken over the last N completed services at that stage. Widen the estimate by a buffer (e.g. **±30%**) and round to a **coarse band** (e.g. "about 10–20 min"). When data is thin (too few completed services to form a reliable median), degrade to **"wait time unavailable"** rather than guessing. Always show a range; never over-promise.

**Constraints (from the brief's context-of-use and NFRs).**
- Environment can be busy, noisy and interrupted by emergencies.
- Limited staff at some stages; peak traffic; possible power/network failure; varied digital confidence; users without smartphones.
- Legal/privacy: Kenya's Health Act (health information confidential), Data Protection Act (health data = sensitive personal data), Digital Health Act (confidentiality, role-based access, audit trails, reliability, accessibility, interoperability). WCAG 2.2 for accessibility.
- Non-functional targets: usability (minimal-step staff actions, plain patient language), privacy, safety, accessibility, reliability (consistent saves, backup/recovery), performance (prompt updates for real-time decisions), accountability (traceable priority/reorder/completion), interoperability (future EHR/identity integration without requiring it now).

**Assumptions.**
- Prototype uses fictional tokens and data only (brief requirement).
- A live pilot would require institutional approval, a defined data controller, secure authentication, audit trail, retention rules and a documented incident-response process — none of which are the prototype's job to finalise.
  > **Decision (proposed default — confirm before build):** Pre-pilot governance defaults, **all requiring Medical Center / University governance approval** before any real-data pilot:
  > - **Data controller:** Kabarak University Medical Center.
  > - **Retention:** live queue tokens purged at end of day (or within 24–48h); audit logs retained ~12 months; aggregate/de-identified analytics may be kept longer. *Note: this is separate from closing an abandoned visit after 24 hours, which is a queue operation and deletes nothing. A token is also now reserved for a week rather than a day, so "purged at end of day" needs restating against the token period before it can be signed off.*
  > - **Incident response:** a named system owner, a documented breach-notification step, and a defined rollback to the manual offline fallback.
  >
  > These are proposed starting points, not settled policy; each touches data-protection and clinical governance and **must be reviewed and signed off by Medical Center / University governance** before real patient data is handled.

---

## Build-from-zero steps

1. **Initialise the repo.** Create the project structure (frontend, backend/service, shared types, docs). Add `.gitignore` and a `.env.example` containing only environment-variable *names* (SMS, DB, hosting) — no values. Add this `spec.md`.
2. **Confirm the decisions and open items** in the *Decisions & open items* section below with the team (technology stack, hosting approach, SMS provider, waiting-range method, auth method), and secure institutional sign-off on the governance/clinical-policy items, before writing feature code.
3. **Model the data.** Implement the schema for Visit, StageEvent, PriorityChange, PharmacyOutcome, AuditLogEntry, StaffUser/Role. Seed with fictional data only.
4. **Build the application service layer.** Single authoritative queue state; endpoints for check-in/token issue (FR1), routine ordering within a stage (FR2), stage transitions (FR6, FR10, FR13), priority changes restricted to clinical roles (FR3, FR4, FR5), presence statuses (FR9), and audit logging (FR14). Enforce role-based access.
5. **Implement the priority policy** exactly as the three-tier table specifies, with logged reasons for routine reordering and immediate routing for emergencies. Never block emergency actions on system state.
6. **Build the patient status view** (FR7): token, current stage, people ahead, cautious waiting range, last update — plain, accessible language.
7. **Build the public display** (FR8): the tracking board — every patient in the clinic, in a column for the stage they are at, with the room beside a token that has been called. Arrival order, never service order. No names, categories or medical detail.
8. **Build role-based staff dashboards** (reception, nurse/triage, clinician, pharmacy) with minimal-step actions per role; priority tags visible on staff screens only.
9. **Add notifications** (FR11): screen and printed-token first; wire the optional SMS/phone module behind env-based credentials once the provider is confirmed.
10. **Implement exceptional paths** (HTA): emergency interruption, temporarily-away/missed-turn/recall recovery, return-after-tests with preserved history, medicine-unavailable, and the manual fallback + reconciliation (FR12).
11. **Apply accessibility (WCAG 2.2)** and reliability (consistent saves, backup/recovery) across all views.
12. **Produce low-fidelity wireframes → high-fidelity clickable prototype** covering all items in the brief's section 4.9 list, using fictional data.
13. **Evaluate** per the brief's plan: heuristic evaluation, cognitive walkthrough, then task-based usability testing against the eight evaluation tasks. Targets: ≥80% unaided completion of core tasks, no unresolved critical safety/privacy defect, mean ease-of-use ≥4/5, ≥80% correctly explain routine vs emergency priority.
14. **Refine** based on evaluation findings (UCD is iterative — evaluation may send you back to requirements).

---

## Decisions & open items (proposed defaults / TODOs — confirm before build)

Each item below covers a point where the brief is silent or defers a decision. Some carry a **proposed default** to unblock the corresponding build step; others have been returned to an open **TODO — confirm** because they were proposed from prior research/assumptions that had not been cleared (stack, hosting, SMS provider). Proposed defaults are not final sign-off — confirm each with the team, and where noted, obtain institutional (Medical Center / University governance) approval before any real-data pilot. Open TODOs need an explicit decision before build.

- **Stack — TODO — confirm: technology stack (frontend, backend, database, real-time transport) — not yet decided.** Previously proposed from prior research/assumptions that had not been cleared; returned to an open item pending explicit go-ahead. (See *Stack + why*.)
- **SMS provider — TODO — confirm: SMS provider for the optional notification channel.** Not yet decided; previously proposed from prior research/assumptions that had not been cleared; returned to an open item. Credentials in env/secrets, not the repo. (See *External dependencies*.)
- **Hosting environment — TODO — confirm: hosting/deployment approach.** Not yet decided; previously proposed from prior research/assumptions that had not been cleared; returned to an open item. *User preference: v1 is hosted LOCALLY / on-premise; exact setup to be decided.* (See *External dependencies*.)
- **Waiting-range method — Decision (proposed default — confirm before build):** `position-in-stage × rolling median service time` over the last N completed services, widened by a buffer (e.g. ±30%) and rounded to a coarse band (e.g. "about 10–20 min"); degrade to "wait time unavailable" when data is thin. Always a range, never a countdown. (See *Decisions & constraints*.)
- **Authentication method — Decision (proposed default — confirm before build):** Django auth with JWT (`djangorestframework-simplejwt`) or server sessions; role-based access with least privilege across Registration Clerk, Nurse/Vitals, Clinician, Pharmacist, Supervisor/Admin, IT/Support. (See *Architecture & data model*.)
- **Audit granularity — Decision (proposed default — confirm before build):** Two layers — an identifiable audit trail (staff user + role + reason) for accountability actions, and de-identified, aggregate analytics/reporting. Requires governance sign-off. (See *Architecture & data model*.)
- **Token ↔ medical record linkage — Decision (proposed default — confirm before build):** Keep decoupled. Queue stores an internal `visit_id`; the patient-facing token is anonymous; no clinical data in the queue DB; authorised staff map token → patient via a station-side lookup. Does not replace the medical record. Requires governance sign-off. (See *Architecture & data model*.)
- **Management vs IT/support permissions — Decision (proposed default — confirm before build):** Management/Supervisor = analytics, staffing, queue config, override oversight (no system/user admin); IT/Support = system config, user/account management, deployments, monitoring, system-health analytics (no clinical override, no clinical analytics). Requires governance sign-off. (See *Users & roles*.)
- **Pre-pilot governance — Decision (proposed default — confirm before build):** Data controller = Kabarak University Medical Center; retention = live tokens purged end-of-day (or 24–48h), audit logs ~12 months, aggregate analytics longer; incident response = named system owner + documented breach-notification + rollback to manual fallback. **All requires Medical Center / University governance approval before any real-data pilot.** (See *Decisions & constraints → Assumptions*.)
- **Interoperability scope/timing — Decision (proposed default — confirm before build):** OpenMRS O3 and student-identity integration are **out of v1 scope — Phase 2 (post-pilot), via API integration**. v1 ships standalone. (See *Purpose & scope* and *Architecture & data model*.)
