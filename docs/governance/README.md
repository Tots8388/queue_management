# The governance gate — how it works

The spec requires institutional sign-off on several decisions **before** the
code that depends on them is written. `TASKS.md` tags those tasks
`[GOV SIGN-OFF]`, but a tag in a checklist stops nobody — anyone can tick the
box and keep going. This directory makes the gate enforceable.

## The three parts

1. **[`SIGNOFF.md`](./SIGNOFF.md)** — the register. Five items (G1–G5), each
   with a status, the approving body, what must be approved, the build tasks it
   blocks, and the source paths it blocks.
2. **[`../../tools/check_signoff.py`](../../tools/check_signoff.py)** — reads
   the register and reports or enforces it.
3. **[`../../.githooks/pre-commit`](../../.githooks/pre-commit)** — runs the
   checker against staged changes on every commit.

## Install the hook

Once per clone:

```bash
python tools/install_hooks.py
```

This sets `core.hooksPath` to the version-controlled `.githooks/`, so the gate
travels with the repository rather than living in one developer's `.git/hooks`.

## What the gate actually refuses

- **Commits touching blocked paths.** While G2 is `PENDING`,
  `backend/queueapp/models.py` cannot be committed. The message names the item
  and the approving body.
- **Ticked governance tasks.** Every `[GOV SIGN-OFF]` line in `TASKS.md` names
  the register item it depends on, e.g. `**[GOV SIGN-OFF] (G2)**`. Ticking one
  `[x]` while that item is `PENDING` is refused — the specific failure the gate
  exists to prevent: the checklist saying done when the approval never
  happened. A governance task that names no item cannot be verified, so it is
  also refused; ambiguity fails closed.
- **A cosmetic approval.** An item marked `APPROVED` with no approver or no
  approval date is treated as a malformed register, and a malformed register
  fails closed — everything stays blocked until it parses.

## Checking status

```bash
python tools/check_signoff.py           # every item
python tools/check_signoff.py --item G2 # one item
```

Exit code 0 means clear, 1 means something is blocked, 2 means the register
itself could not be read.

## Recording an approval

Only when the approval has actually happened, at the named body, and is minuted.

Edit the item's block in `SIGNOFF.md`:

```yaml
id: record-linkage
status: APPROVED
approver: Medical Center Governance Committee
approval_date: 2026-08-14
evidence: Minute 2026/08/14-4b, Medical Center Governance Committee
```

Then commit that change on its own, with a message saying which body approved
what. The register's history is the audit trail for the approvals themselves.

## The override, and why not to use it

`git commit --no-verify` skips the hook. It exists in git and cannot be removed.
Using it to get past this gate means writing code that handles the
identification, monitoring or retention of health data on an authority nobody
granted. If you are tempted, the correct move is the opposite one: take the
gated files out of the commit and carry on with the work that is not blocked.

## What is *not* gated

Everything else. Project setup, the queue engine, real-time transport, the
frontends, the wait-range calculation, notifications and the LAN deployment all
proceed normally. The gate is deliberately narrow: it covers the decisions that
determine how patient identity is held, what identifiable staff data is
retained, who can see oversight data, and the conditions for a real-data pilot.

And regardless of any of it: **the prototype uses fictional records only.**
