#!/usr/bin/env python3
"""Reject reusable resource ownership in the verification policy source."""

from pathlib import Path
import sys


def check_source_boundary(root: Path) -> None:
    if not root.is_dir():
        raise ValueError(f"policy source is not a directory: {root}")
    for name in ("controls", "schemas"):
        path = root / name
        if path.exists() or path.is_symlink():
            raise ValueError(f"verification policy must not own reusable policies/{name} content")
    for path in root.rglob("*.rego"):
        if path.is_file() or path.is_symlink():
            raise ValueError(f"verification policy must not copy reusable Rego: {path}")


if __name__ == "__main__":
    try:
        check_source_boundary(Path(sys.argv[1]))
    except (IndexError, ValueError) as error:
        raise SystemExit(f"source boundary error: {error}") from error
