#!/usr/bin/env python3
"""
Governance gate checker.

The spec requires institutional sign-off on several decisions before the code
that depends on them is written. A checklist alone does not enforce that — a
developer can tick a box and carry on. This script makes the gate real:

  * it reads the sign-off register in docs/governance/SIGNOFF.md;
  * it refuses commits that add or change code under a pending item's blocked
    paths (--staged, used by the pre-commit hook);
  * it fails if a [GOV SIGN-OFF] task in TASKS.md is ticked while the item it
    depends on is still PENDING.

Exit codes: 0 = clear, 1 = blocked, 2 = the register itself is malformed.

Usage:
    python tools/check_signoff.py            # report status of every item
    python tools/check_signoff.py --staged   # gate the staged changes
    python tools/check_signoff.py --item G2  # report one item
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTER_PATH = REPO_ROOT / "docs" / "governance" / "SIGNOFF.md"
TASKS_PATH = REPO_ROOT / "TASKS.md"

APPROVED = "APPROVED"
PENDING = "PENDING"

HEADING_RE = re.compile(r"^##\s+(G\d+)\s+—\s+(.+?)\s*$")
YAML_BLOCK_RE = re.compile(r"```yaml\n(.*?)```", re.DOTALL)
BLOCKS_TASKS_RE = re.compile(
    r"^\*\*Blocks tasks:\*\*\s*(.+?)(?=\n\n|\n\*\*|\Z)", re.MULTILINE | re.DOTALL
)
BLOCKS_PATHS_RE = re.compile(
    r"^\*\*Blocks paths:\*\*\s*\n((?:-\s+`[^`]+`\s*\n?)+)", re.MULTILINE
)


class RegisterError(Exception):
    """The register could not be parsed — treated as a hard failure."""


@dataclass
class GateItem:
    ref: str
    title: str
    item_id: str
    status: str
    approver: str
    approval_date: str
    evidence: str
    blocked_paths: list[str] = field(default_factory=list)
    blocks_tasks: str = ""

    @property
    def approved(self) -> bool:
        return self.status.upper() == APPROVED

    def blocks(self, path: str) -> bool:
        """True if `path` (repo-relative, forward slashes) is gated by this item."""
        normalised = path.replace("\\", "/").lstrip("./")
        for blocked in self.blocked_paths:
            if blocked.endswith("/"):
                if normalised.startswith(blocked):
                    return True
            elif normalised == blocked:
                return True
        return False


def _parse_yaml_block(block: str, ref: str) -> dict[str, str]:
    """A deliberately tiny key: value parser — the register has no nesting."""
    values: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise RegisterError(f"{ref}: cannot parse register line {line!r}")
        key, _, value = line.partition(":")
        values[key.strip()] = value.strip()
    return values


def parse_register(text: str) -> list[GateItem]:
    """Split the register into items. Malformed input raises rather than passes."""
    sections = re.split(r"^(?=##\s+G\d+\s+—)", text, flags=re.MULTILINE)
    items: list[GateItem] = []

    for section in sections:
        heading = HEADING_RE.match(section.splitlines()[0] if section.strip() else "")
        if not heading:
            continue
        ref, title = heading.group(1), heading.group(2)

        yaml_match = YAML_BLOCK_RE.search(section)
        if not yaml_match:
            raise RegisterError(f"{ref}: no status block found")
        values = _parse_yaml_block(yaml_match.group(1), ref)

        status = values.get("status", "").upper()
        if status not in {APPROVED, PENDING}:
            raise RegisterError(
                f"{ref}: status must be {APPROVED} or {PENDING}, got {status!r}"
            )

        item = GateItem(
            ref=ref,
            title=title,
            item_id=values.get("id", ""),
            status=status,
            approver=values.get("approver", ""),
            approval_date=values.get("approval_date", ""),
            evidence=values.get("evidence", ""),
        )

        # An approval with no approver or date is not an approval. This closes
        # the obvious shortcut of flipping the word and moving on.
        if item.approved and not (item.approver and item.approval_date):
            raise RegisterError(
                f"{ref} is marked {APPROVED} but has no approver and/or "
                f"approval_date. Record who approved it and when."
            )

        paths_match = BLOCKS_PATHS_RE.search(section)
        if paths_match:
            item.blocked_paths = re.findall(r"`([^`]+)`", paths_match.group(1))

        tasks_match = BLOCKS_TASKS_RE.search(section)
        if tasks_match:
            item.blocks_tasks = " ".join(tasks_match.group(1).split())

        items.append(item)

    if not items:
        raise RegisterError("no gate items found in the register")
    return items


def load_items() -> list[GateItem]:
    if not REGISTER_PATH.exists():
        raise RegisterError(f"register not found at {REGISTER_PATH}")
    return parse_register(REGISTER_PATH.read_text(encoding="utf-8"))


def staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


GATE_REF_RE = re.compile(r"\bG\d+\b")


def ticked_gov_tasks() -> list[str]:
    """Ticked TASKS.md checkboxes that carry the [GOV SIGN-OFF] tag."""
    if not TASKS_PATH.exists():
        return []
    return [
        line.strip()
        for line in TASKS_PATH.read_text(encoding="utf-8").splitlines()
        if line.lstrip().startswith("- [x]") and "[GOV SIGN-OFF]" in line
    ]


def check_ticked_tasks(items: list[GateItem]) -> list[str]:
    """
    A ticked governance task whose gate item is still pending is the failure
    mode this whole script exists for: the checklist says done, the approval
    never happened.

    Each [GOV SIGN-OFF] task must name the register item it depends on (G1, G2,
    …) so it can be checked against that item alone — otherwise approving one
    item would never let its own task be ticked while any other stayed pending.
    A task that names no item is ambiguous, and ambiguity fails closed.
    """
    by_ref = {item.ref: item for item in items}
    problems = []

    for task in ticked_gov_tasks():
        refs = [ref for ref in GATE_REF_RE.findall(task) if ref in by_ref]
        if not refs:
            problems.append(
                "TASKS.md has a ticked [GOV SIGN-OFF] task that names no "
                "register item, so it cannot be verified. Add its gate "
                f"reference (e.g. G2):\n      {task}"
            )
            continue

        unapproved = [ref for ref in refs if not by_ref[ref].approved]
        if unapproved:
            problems.append(
                f"TASKS.md has a ticked [GOV SIGN-OFF] task while "
                f"{', '.join(unapproved)} "
                f"{'is' if len(unapproved) == 1 else 'are'} still {PENDING}:\n"
                f"      {task}"
            )

    return problems


def check_staged(items: list[GateItem]) -> int:
    problems = check_ticked_tasks(items)

    for path in staged_files():
        for item in items:
            if item.approved or not item.blocks(path):
                continue
            problems.append(
                f"{path} is blocked by {item.ref} ({item.title}), status {PENDING}"
            )

    if not problems:
        return 0

    print("GOVERNANCE GATE — commit refused\n", file=sys.stderr)
    for problem in problems:
        print(f"  ✗ {problem}", file=sys.stderr)
    print(
        "\n  These changes depend on decisions that require Medical Center /\n"
        "  University governance approval before the code is written\n"
        "  (spec.md, Build-from-zero steps, step 2).\n\n"
        f"  Record the approval in {REGISTER_PATH.relative_to(REPO_ROOT)} — with\n"
        "  the approving body and date — or take these files out of the commit.\n\n"
        "  Overriding with `git commit --no-verify` is a deliberate act. Do not\n"
        "  do it to unblock yourself; the gate is the institution's, not the\n"
        "  repository's.",
        file=sys.stderr,
    )
    return 1


def report(items: list[GateItem], only: str | None = None) -> int:
    shown = [i for i in items if only is None or i.ref == only or i.item_id == only]
    if not shown:
        print(f"No gate item matches {only!r}", file=sys.stderr)
        return 2

    pending = [i for i in shown if not i.approved]

    print("Governance sign-off register\n")
    for item in shown:
        mark = "✓" if item.approved else "✗"
        print(f"  {mark} {item.ref}  {item.title}")
        print(f"      status:   {item.status}")
        if item.approved:
            print(f"      approved: {item.approver} on {item.approval_date}")
            if item.evidence:
                print(f"      evidence: {item.evidence}")
        else:
            if item.blocks_tasks:
                print(f"      blocks:   {item.blocks_tasks}")
            for path in item.blocked_paths:
                print(f"      path:     {path}")
        print()

    if pending:
        print(
            f"{len(pending)} of {len(shown)} item(s) pending — "
            "the dependent build tasks are blocked."
        )
        return 1

    print(f"All {len(shown)} item(s) approved.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--staged",
        action="store_true",
        help="gate the staged changes (used by the pre-commit hook)",
    )
    parser.add_argument("--item", help="report a single item, by ref (G2) or id")
    args = parser.parse_args()

    try:
        items = load_items()
    except RegisterError as error:
        # A register we cannot read is a blocked register, never an open one.
        print(f"GOVERNANCE GATE — register is unreadable: {error}", file=sys.stderr)
        return 2

    if args.staged:
        return check_staged(items)
    return report(items, args.item)


if __name__ == "__main__":
    sys.exit(main())
