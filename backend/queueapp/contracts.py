"""
Loads the shared queue vocabulary from ``shared/contracts.json``.

The frontend reads the same file, so a role, stage or status can never exist on
one side of the system and not the other. Django model choices are derived from
here rather than redeclared — see ``models.py``.
"""

import json
from functools import lru_cache
from pathlib import Path

CONTRACTS_PATH = (
    Path(__file__).resolve().parent.parent.parent / "shared" / "contracts.json"
)


@lru_cache(maxsize=1)
def contracts() -> dict:
    """The parsed contracts file. Cached — it is static for the process."""
    with CONTRACTS_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def choices(section: str) -> list[tuple[str, str]]:
    """Django ``choices`` for a contracts section, e.g. ``choices("stages")``."""
    return [(item["key"], item["label"]) for item in contracts()[section]]


def keys(section: str) -> list[str]:
    """The stable identifiers for a section, in declared order."""
    return [item["key"] for item in contracts()[section]]


def by_key(section: str, key: str) -> dict:
    """A single entry from a section, by its stable key."""
    for item in contracts()[section]:
        if item["key"] == key:
            return item
    raise KeyError(f"{key!r} is not a known {section} key")


def roles_that_may_assign_priority() -> list[str]:
    """
    Roles permitted to set emergency/urgent priority (spec FR3).

    This is the authoritative list the backend permission classes enforce. The
    frontend uses the same data only to hide controls, never as the boundary.
    """
    return [
        role["key"] for role in contracts()["roles"] if role["may_assign_priority"]
    ]


def public_display_allowed_fields() -> list[str]:
    """
    The only fields a public-display payload may contain (spec FR8).

    Public screens show an anonymous token and its destination — never a name,
    priority category, diagnosis or prescription.
    """
    return list(contracts()["privacy"]["public_display_allowed_fields"])
