#!/usr/bin/env python3
"""Install locked runtime dependencies and then an exact candidate wheel."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path


PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^ ;\\]+)")


def _locked_versions(requirements: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    for line in requirements.read_text(encoding="utf-8").splitlines():
        match = PIN.match(line)
        if match:
            versions[match.group(1)] = match.group(2)
    if not versions:
        raise SystemExit("locked runtime dependency export contained no exact selections")
    return versions


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Install the runtime dependency selections exported from uv.lock, then "
            "install a candidate wheel without dependency resolution."
        )
    )
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args()

    tooling_root = Path(__file__).resolve().parents[1]
    if not args.python.is_file():
        parser.error(f"target Python is unavailable: {args.python}")
    if not args.wheel.is_file():
        parser.error(f"candidate wheel is unavailable: {args.wheel}")

    with tempfile.TemporaryDirectory(prefix="compliance-locked-runtime-") as temporary:
        requirements = Path(temporary) / "requirements.txt"
        subprocess.run(
            [
                "uv",
                "export",
                "--project",
                str(tooling_root),
                "--frozen",
                "--no-dev",
                "--no-emit-project",
                "--format",
                "requirements.txt",
                "--output-file",
                str(requirements),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        locked_versions = _locked_versions(requirements)
        install = [
            "uv",
            "pip",
            "install",
            "--python",
            str(args.python),
            "--requirements",
            str(requirements),
            "--require-hashes",
        ]
        if args.cache_dir:
            install.extend(("--cache-dir", str(args.cache_dir)))
        subprocess.run(install, check=True)
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(args.python),
                "--no-deps",
                str(args.wheel.resolve()),
            ],
            check=True,
        )

        verification = (
            "import importlib.metadata as m, json, sys; "
            "expected=json.loads(sys.argv[1]); "
            "actual={name:m.version(name) for name in expected}; "
            "assert actual == expected, (actual, expected)"
        )
        subprocess.run(
            [str(args.python), "-c", verification, json.dumps(locked_versions)],
            check=True,
        )


if __name__ == "__main__":
    main()
