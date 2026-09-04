#!/usr/bin/env python3
"""Build a standalone tooling wheel with optional canonical source provenance."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
SCHEMA_MIRRORS = (
    (
        Path("schemas/inventory/resource.schema.json"),
        Path("package-data/schemas/inventory/resource.schema.json"),
    ),
    (
        Path("schemas/waivers/resource.schema.json"),
        Path("package-data/schemas/waivers/resource.schema.json"),
    ),
)


def _verify_schema_mirrors(root: Path) -> None:
    for canonical, packaged in SCHEMA_MIRRORS:
        canonical_path = root / canonical
        packaged_path = root / packaged
        if canonical_path.read_bytes() != packaged_path.read_bytes():
            raise SystemExit(
                f"packaged schema mirror differs from canonical source: {packaged} != {canonical}"
            )


def _copy_source(root: Path, staging: Path) -> None:
    shutil.copytree(
        root,
        staging,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            "build",
            "dist",
            "__pycache__",
            "*.pyc",
        ),
    )


def _inject_source_digest(staging: Path, source_digest: str | None) -> None:
    metadata_path = staging / "tools/release-metadata.json"
    document = json.loads(metadata_path.read_text(encoding="utf-8"))
    if document.get("schema") != "compliance.example/tooling-release-metadata/v2":
        raise SystemExit("build source must use tooling-release-metadata/v2")
    document["source_digest"] = source_digest
    metadata_path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the compliance tooling wheel from a clean staged source tree."
    )
    parser.add_argument(
        "--source-digest",
        help="canonical sha256 source digest to embed; omit for a development build",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist"),
        help="wheel output directory (default: dist)",
    )
    args = parser.parse_args()

    if args.source_digest and not DIGEST.fullmatch(args.source_digest):
        parser.error("--source-digest must be sha256:<64 lower-case hex characters>")

    root = Path(__file__).resolve().parents[1]
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    _verify_schema_mirrors(root)

    with tempfile.TemporaryDirectory(prefix="compliance-tooling-build-") as temporary:
        staging = Path(temporary) / "source"
        _copy_source(root, staging)
        _inject_source_digest(staging, args.source_digest)
        subprocess.run(
            [
                "uv",
                "build",
                "--wheel",
                "--no-sources",
                "--out-dir",
                str(output_dir),
                str(staging),
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
