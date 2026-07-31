# Digital Queue & Patient-Flow Management System

Kabarak University Medical Center — outpatient queue and patient-flow prototype
(registration → vital signs → consultation → pharmacy).

> **This is an HCI/UCD design-and-prototype project.** It is not a production
> hospital system, it does not diagnose patients, it does not determine clinical
> urgency, and it does not replace the medical record/EHR. All prototype records
> are fictional. A measured pilot with institutional governance approval is
> required before any real clinical use.

## Source of truth

- **[`spec.md`](./spec.md)** — the full build specification. When anything
  disagrees with the spec, the spec wins.
- **[`TASKS.md`](./TASKS.md)** — the ordered build checklist derived from the spec.
- **[`docs/governance/`](./docs/governance/)** — the governance sign-off gate.
  Tasks tagged `[GOV SIGN-OFF]` in `TASKS.md` are **blocked** until the relevant
  item is approved. See [Governance gate](#governance-gate) below.

## What it does (v1)

| Area | Behaviour |
| --- | --- |
| Token | One anonymous, human-readable token (e.g. `T-041`) per visit, persisting across all four stages. |
| Fairness | Routine patients are served in recorded check-in order **within each stage**. |
| Clinical priority | Only authorised clinical roles (Nurse/Vitals, Clinician) may set emergency/urgent, and every change is logged with role, timestamp and a non-sensitive reason. The system never computes clinical urgency and never delays emergency care. |
| Patient view | Token, current stage, people ahead, a **cautious waiting range** (never a countdown), and last-update time. |
| Public display | Anonymous token + destination only — no names, no priority category, no medical detail. |
| Audit | Identifiable audit trail for accountability actions; de-identified aggregate analytics for reporting. |
| Resilience | Documented manual (paper/verbal) fallback with later reconciliation; core queue runs on the LAN with no cloud/internet dependency. |

## Architecture

```text
frontend/   Next.js / React — patient view, public display, role-based staff dashboards
backend/    Django + Django REST Framework + Django Channels — the single authoritative
            queue state, RBAC, priority policy, stage transitions, audit log
shared/     Contracts shared by both sides (roles, stages, statuses, priorities)
docs/       Governance gate, operations runbooks, decision records
tools/      Deterministic helper scripts (e.g. the governance gate checker)
```

- **Database:** PostgreSQL. SQLite is acceptable **for the local prototype only**.
- **Real-time:** WebSockets via Django Channels (patient view, staff dashboards,
  public display all subscribe to one queue state).
- **Hosting:** local / on-premise on the Medical Center's LAN. No cloud in v1.

## Getting started

Prerequisites: Python 3.12+, Node.js 20+, and PostgreSQL (optional for the
prototype — see below).

```bash
cp .env.example .env      # then fill in local values; never commit .env
```

Then run both services:

```bat
start.bat
```

`stop.bat` shuts them down and is safe to run when nothing is up. Ports are
pinned at the top of each script: backend `8000`, frontend `3000`.

Setup details, including the PostgreSQL vs SQLite decision, are in
[`docs/development.md`](./docs/development.md).

## Running it in the clinic

- **[Manual fallback and reconciliation](./docs/operations/offline-fallback.md)** —
  what staff do when the system is down, and how the paper sheets get entered
  afterwards without anyone losing their place in the queue. **Print this one.**
- [LAN deployment](./docs/operations/lan-deployment.md) — the clinic machine,
  the network, and where secrets live.
- [Backups and recovery](./docs/operations/backup-and-recovery.md) — including
  the restore drill, which is the part that matters.
- [Resilience](./docs/operations/resilience.md) — UPS, the single point of
  failure, and what the recovery path actually is.

## Governance gate

The spec requires institutional (Medical Center / University governance)
sign-off on several decisions **before** the code that depends on them is built —
token ↔ medical-record linkage, audit granularity, the Management vs IT/Support
permission boundary, and the pre-pilot governance checklist.

That gate is not a checkbox anyone can tick past. It is enforced by
[`docs/governance/SIGNOFF.md`](./docs/governance/SIGNOFF.md) and checked by:

```bash
python tools/check_signoff.py
```

The checker exits non-zero while any item is unapproved and names exactly which
build tasks stay blocked. See
[`docs/governance/README.md`](./docs/governance/README.md).

## Secrets

No secret values live in this repo, ever. `.env.example` lists variable **names**
with empty placeholders; real values live in `.env` (git-ignored) or the host
machine's environment / secrets store.
