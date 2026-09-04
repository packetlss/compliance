#!/usr/bin/env python3
"""Prepare or verify a provider-neutral compliance-tooling release payload."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.release_artifacts import (  # noqa: E402
    ToolingReleaseError,
    prepare_release_payload,
    verify_release_payload,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare or verify immutable tooling release assets."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser(
        "prepare",
        help="build and verify a complete content-addressed release payload",
    )
    prepare.add_argument(
        "--git-tag",
        help="optional release-navigation tag metadata; requires --git-commit",
    )
    prepare.add_argument(
        "--git-commit",
        help="optional exact Git commit metadata; requires --git-tag",
    )
    prepare.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist/release"),
        help="empty output directory for wheel, manifest, and SHA256SUMS",
    )

    verify = subparsers.add_parser(
        "verify",
        help="verify a previously prepared release payload",
    )
    verify.add_argument(
        "--release-dir",
        type=Path,
        default=Path("dist/release"),
        help="directory containing wheel, manifest, and SHA256SUMS",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "prepare":
            manifest = prepare_release_payload(
                ROOT,
                output_dir=args.output_dir,
                git_tag=args.git_tag,
                git_commit=args.git_commit,
            )
        else:
            manifest = verify_release_payload(args.release_dir)
    except (ToolingReleaseError, OSError) as error:
        print(f"tooling release: {error}", file=sys.stderr)
        return 2

    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
