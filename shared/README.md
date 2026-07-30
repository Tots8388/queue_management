# Shared contracts

[`contracts.json`](./contracts.json) is the single source of truth for the queue
vocabulary — roles, stages, stage statuses, priorities, presence statuses,
pharmacy states, notification preferences, and the public-display privacy rule.

Both sides read this file rather than redeclaring the strings:

- **Backend** — `backend/queueapp/contracts.py` loads it and derives Django model
  choices from it.
- **Frontend** — `frontend/src/lib/contracts.ts` imports it and derives its
  TypeScript unions from it.

Changing a key here changes it everywhere, which is the point: a stage or role
that exists on one side but not the other is a class of bug this file removes.

Rules:

- Keys are stable identifiers stored in the database — renaming one is a
  migration, not an edit.
- Labels are display text and may be changed freely.
- `roles[].may_assign_priority` encodes spec FR3 (only authorised clinical roles
  may set emergency/urgent). It is enforced in backend permission classes; the
  frontend uses it only to hide controls, never as the security boundary.
