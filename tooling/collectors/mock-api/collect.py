#!/usr/bin/env python3
"""Turn deterministic mock API responses into fresh compliance evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools._canonical_json import canonical_json_bytes


def canonical_digest(value: Any) -> str:
    encoded = canonical_json_bytes(value)
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def collect_fixture(path: Path, collected_at: datetime) -> dict[str, Any]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    payload = fixture["payload"]
    timestamp = collected_at.isoformat().replace("+00:00", "Z")
    digest = canonical_digest(payload)
    return {
        "schema": "compliance.example/evidence/v1",
        "id": (
            f'evidence:{fixture["type"]}:{timestamp}:'
            f'{digest.removeprefix("sha256:")[:16]}'
        ),
        "subject": fixture["subject"],
        "type": fixture["type"],
        "collected_at": timestamp,
        "collector": fixture["collector"],
        "payload": payload,
    }


def safe_filename(subject_id: str, evidence_type: str) -> str:
    return "__".join((subject_id, evidence_type)).replace("/", "_") + ".json"


def parse_collected_at(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"not a valid RFC 3339 timestamp: {value!r}"
        ) from error
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError(
            f"timestamp must include a timezone: {value!r}"
        )
    return parsed.astimezone(UTC).replace(microsecond=0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures", type=Path, help="directory containing *-api.json fixtures")
    parser.add_argument("output", type=Path, help="evidence output directory")
    parser.add_argument(
        "--collected-at",
        type=parse_collected_at,
        help="fixed RFC 3339 collection instant for deterministic verification",
    )
    args = parser.parse_args()

    fixture_paths = sorted(args.fixtures.glob("*-api.json"))
    if not fixture_paths:
        raise SystemExit(f"no *-api.json fixtures found in {args.fixtures}")

    collected_at = args.collected_at or datetime.now(UTC).replace(microsecond=0)
    args.output.mkdir(parents=True, exist_ok=True)
    for fixture_path in fixture_paths:
        evidence = collect_fixture(fixture_path, collected_at)
        output = args.output / safe_filename(evidence["subject"]["id"], evidence["type"])
        output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f'wrote {evidence["type"]} for {evidence["subject"]["id"]} to {output}')


if __name__ == "__main__":
    main()
