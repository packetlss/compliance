#!/usr/bin/env python3
"""Prepare synthetic stored-plan snapshots for policy diff-set demonstrations."""

from __future__ import annotations

import argparse
import copy
import json
import os
import shlex
import tempfile
from pathlib import Path
from typing import Any, Sequence

from tools.artifact_validation import validate_assessment_plan
from tools.assessment_provenance import artifact_digest
from tools.compliance import default_schema_path
from tools.project_config import load_config
from tools.render_plan import (
    load_inventory_inputs,
    render_plan,
)


JsonObject = dict[str, Any]
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_REGISTRY = Path(
    os.environ.get(
        "COMPLIANCE_EXAMPLE_PROJECT_REGISTRY",
        str(WORKSPACE_ROOT / "compliance.yaml"),
    )
).resolve()


def _render(project_name: str, subject_id: str) -> JsonObject:
    config = load_config(PROJECT_REGISTRY, project_name)
    subject, groups, assignments = load_inventory_inputs(
        config.path("inventory"),
        config.path("assignments"),
        subject_id,
        config.path("resourceSchema") or default_schema_path(),
    )
    return render_plan(subject, groups, assignments, config.policy_sources, config=config)


def _resign(plan: JsonObject) -> JsonObject:
    from tools.operation import member_facts
    from tools.assessment_provenance import digest
    operation = plan["operation"]
    operation['members'] = [member_facts(plan)]
    operation['operation_id'] = digest({key: value for key, value in operation.items()
                                        if key != 'operation_id'})
    plan.pop("id", None)
    plan["id"] = artifact_digest(plan)
    validate_assessment_plan(plan)
    return plan


def _write_plan(directory: Path, plan: JsonObject) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    filename = plan["subject"]["id"].replace("/", "__") + ".json"
    (directory / filename).write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def prepare_demo(output: Path) -> dict[str, tuple[Path, Path]]:
    """Create unchanged, changed, and incomplete synthetic plan-set pairs."""
    if output.exists():
        if not output.is_dir():
            raise ValueError(f"demo output path is not a directory: {output}")
        if any(output.iterdir()):
            raise ValueError(f"demo output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    ordinary_aws = _render(
        "mock-fleet",
        "cloud-account/aws-111122223333",
    )
    conflict_aws = _render(
        "mock-fleet",
        "cloud-account/aws-444455556666",
    )
    saas = _render(
        "mock-fleet",
        "saas/acme-projects/company",
    )
    modified_aws = copy.deepcopy(ordinary_aws)
    modified_control = next(
        control
        for control in modified_aws["controls"]
        if control["instance_id"]
        == "company.aws.s3-account-public-access-block"
    )
    modified_control["remediation"] = (
        "Follow the newly approved synthetic release runbook."
    )
    _resign(modified_aws)

    invalid_persona = _render(
        "server-personas",
        "host/persona-conflict-01",
    )

    pairs = {
        "unchanged": (output / "unchanged/before", output / "unchanged/after"),
        "changed": (output / "changed/before", output / "changed/after"),
        "incomplete": (output / "incomplete/before", output / "incomplete/after"),
    }
    for directory in pairs["unchanged"]:
        _write_plan(directory, ordinary_aws)
        _write_plan(directory, conflict_aws)

    _write_plan(pairs["changed"][0], ordinary_aws)
    _write_plan(pairs["changed"][0], conflict_aws)
    _write_plan(pairs["changed"][1], modified_aws)
    _write_plan(pairs["changed"][1], saas)

    for directory in pairs["incomplete"]:
        _write_plan(directory, invalid_persona)
    return pairs


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="empty output directory; defaults to a new system temporary directory",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    output = (
        args.output.resolve()
        if args.output is not None
        else Path(tempfile.mkdtemp(prefix="compliance-policy-diff-set-"))
    )
    pairs = prepare_demo(output)
    print(f"Prepared synthetic policy diff-set samples under {output}")
    for name, (before, after) in pairs.items():
        command = " ".join((
            "scripts/dev cli --no-config policy diff-set",
            shlex.quote(str(before)),
            shlex.quote(str(after)),
        ))
        expected = {"unchanged": 0, "changed": 1, "incomplete": 2}[name]
        print(f"\n{name} (expected exit {expected}):\n{command}")


if __name__ == "__main__":
    main()
