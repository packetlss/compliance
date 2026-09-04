#!/usr/bin/env python3
"""Prepare or verify a generic standard control-library release payload."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from policy_release import (  # noqa: E402
    PolicyReleaseError,
    prepare_release_payload,
    release_tag_version,
    verify_release_payload,
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser(
        "prepare",
        help="write a canonical content descriptor and optional acquisition representations",
    )
    prepare.add_argument(
        "--version",
        required=True,
        help="semantic release version; must match release/VERSION",
    )
    prepare.add_argument(
        "--git-tag",
        help="optional v<SemVer> source/release tag recorded as noncanonical metadata",
    )
    prepare.add_argument(
        "--git-commit",
        help="optional exact 40-hex source commit recorded as noncanonical metadata",
    )
    prepare.add_argument(
        "--archive",
        action="store_true",
        help="also emit a deterministic policy-source-archive/v1 representation",
    )
    prepare.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist/release"),
        help="empty output directory for descriptor, checksums, and optional representations",
    )

    verify = commands.add_parser(
        "verify",
        help="verify a release descriptor and all representations it declares",
    )
    verify.add_argument(
        "--release-dir",
        type=Path,
        default=Path("dist/release"),
        help="directory containing the descriptor, checksums, and declared representations",
    )
    verify.add_argument(
        "--policy-root",
        type=Path,
        help="optional materialized policy tree to verify against canonical content.digest",
    )
    return root


def _source_release_version() -> str:
    version_file = ROOT / "release/VERSION"
    try:
        version = version_file.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise PolicyReleaseError(f"cannot read source release version: {error}") from error
    if not version:
        raise PolicyReleaseError("source release version is empty")
    return version


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "prepare":
            source_version = _source_release_version()
            if args.version != source_version:
                raise PolicyReleaseError(
                    f"requested release version {args.version!r} does not match "
                    f"source release version {source_version!r}"
                )
            if args.git_tag is not None and release_tag_version(args.git_tag) != args.version:
                raise PolicyReleaseError(
                    f"source Git tag {args.git_tag!r} does not name release "
                    f"version {args.version!r}"
                )
            manifest = prepare_release_payload(
                ROOT,
                version=args.version,
                output_dir=args.output_dir,
                git_tag=args.git_tag,
                git_commit=args.git_commit,
                include_archive=args.archive,
            )
        else:
            manifest = verify_release_payload(
                args.release_dir,
                policy_root=args.policy_root,
            )
    except (PolicyReleaseError, OSError) as error:
        print(f"policy release: {error}", file=sys.stderr)
        return 2

    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
