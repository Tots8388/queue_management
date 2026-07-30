#!/usr/bin/env python3
"""
Point git at the repo's hooks directory so the governance gate runs on commit.

Run once after cloning:

    python tools/install_hooks.py

This sets `core.hooksPath` to `.githooks`, which is version-controlled — so the
gate travels with the repository instead of living in one developer's untracked
`.git/hooks`.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = ".githooks"


def main() -> int:
    hooks_path = REPO_ROOT / HOOKS_DIR
    if not (hooks_path / "pre-commit").exists():
        print(f"error: {hooks_path / 'pre-commit'} not found", file=sys.stderr)
        return 1

    subprocess.run(
        ["git", "config", "core.hooksPath", HOOKS_DIR],
        cwd=REPO_ROOT,
        check=True,
    )

    # Git needs the executable bit on POSIX; on Windows this is a no-op.
    hook = hooks_path / "pre-commit"
    hook.chmod(hook.stat().st_mode | 0o111)

    print(f"Governance gate installed — git will run {HOOKS_DIR}/pre-commit.")
    print("Check status any time with: python tools/check_signoff.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
