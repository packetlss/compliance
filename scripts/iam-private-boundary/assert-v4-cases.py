#!/usr/bin/env python3
"""Focused v4 IAM consumer cases; all variants and outputs stay temporary."""
from __future__ import annotations

import argparse
import io
import json
import shutil
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path

from tools.artifact_validation import validate_assessment_plan, validate_assessment_results
from tools.assessment_provenance import validate_result_against_plan, validate_selection_snapshot
from tools.cli import main as cli_main
from tools.evaluate_plan import evaluate_plan_document
from tools.evidence_provenance import evidence_set_provenance
from tools.project_config import load_config

SUBJECT = "host/restricted-linux-01"
ARTIFACT = "host__restricted-linux-01.json"
INSTANT = "2026-09-01T00:00:00Z"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document))


def cli(config: Path, *arguments: str) -> str:
    output = io.StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        cli_main(["--config", str(config), *arguments])
    return output.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assembly-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    fixture = args.assembly_root / "verification/fixtures/iam-private-boundary"
    original_config = load_config(fixture / "compliance.yaml")
    plan = load(args.run_root / "plans" / ARTIFACT)
    result = load(args.run_root / "results" / ARTIFACT)
    documents = [load(path) for path in sorted((args.run_root / "evidence").rglob("*.json"))]
    require(len(documents) == 1, "IAM cases require the single typed access observation")
    observation = documents[0]
    root = args.run_root / "v4-cases"
    root.mkdir()

    # Reorder every source permutation, with private bytes physically relocated.
    # Paths/config location are acquisition details, not composition identity.
    from itertools import permutations
    private = root / "relocated-private"
    original_private = next(source.path for source in original_config.policy_sources
                            if source.name == "environment-private")
    shutil.copytree(original_private, private)
    for original in original_private.rglob("*"):
        if original.is_file():
            require(not original.samefile(private / original.relative_to(original_private)),
                    "private relocation must be a physical copy")
    sources = [{"name": source.name, "path": str(private if source.name == "environment-private" else source.path)}
               for source in original_config.policy_sources]
    config = {
        "schema": "compliance.example/project-config/v1alpha3",
        "policySources": sources,
        "paths": {key: str(original_config.path(key)) for key in ("inventory", "assignments", "waivers")},
    }
    config["paths"].update({"evidence": str(args.run_root / "evidence"),
                            "plan": str(root / "plans"), "results": str(root / "results")})
    config_path = root / "compliance.yaml"
    for order in permutations(sources):
        config["policySources"] = list(order)
        write(config_path, config)
        cli(config_path, "assessment", "run", SUBJECT, "--at", INSTANT)
        repeated_plan = load(root / "plans" / ARTIFACT)
        repeated_result = load(root / "results" / ARTIFACT)
        validate_assessment_plan(repeated_plan)
        validate_assessment_results(repeated_result)
        validate_result_against_plan(repeated_result, repeated_plan)
        require(repeated_plan["id"] == plan["id"], "source order/location changed v4 plan identity")
        require(repeated_result["id"] == result["id"], "source order/location changed v4 result identity")

    # Consume the original plan with missing, stale, invalid, and ambiguous evidence.
    # Authored 'implemented' must never turn an inconclusive check into pass.
    stale = {**observation, "collected_at": "2026-08-01T00:00:00Z"}
    invalid = {**observation, "payload": {}}
    ambiguous = {**observation, "extension": "distinct complete document"}
    variants = {"missing": [], "stale": [stale], "invalid": [observation, invalid],
                "ambiguous": [observation, ambiguous]}
    for name, evidence in variants.items():
        evidence_root = root / name
        evidence_root.mkdir()
        for index, document in enumerate(evidence):
            write(evidence_root / f"{index}.json", document)
        report = evaluate_plan_document(plan, evidence_root, original_config.policy_sources,
                                        evaluated_at=datetime.fromisoformat(INSTANT))
        validate_assessment_results(report)
        validate_result_against_plan(report, plan)
        require(report["outcome"] == "unknown" and all(
            child["status"] == "unknown" for child in report["results"]), f"{name}: technical checks did not stay unknown")
        require(report["requirement_assessments"][0]["status"] == "unknown"
                and report["requirement_baseline_assessments"][0]["status"] == "unknown",
                f"{name}: unknown did not propagate through retained objective roll-up")
        require(report["provenance"]["selectedEvidence"] == [], f"{name}: rejected evidence was marked selected")
        require(report["provenance"]["evidence"] == evidence_set_provenance(evidence),
                f"{name}: complete snapshot identity changed")
        field = {"invalid": "evidence_validation_errors", "ambiguous": "evidence_selection_ambiguities"}.get(name)
        if field:
            require(all(child["observed"].get(field) for child in report["results"]),
                    f"{name}: attributable diagnostics missing")
        write(root / f"{name}-result.json", report)

    # An older nonselected candidate remains snapshotted but is never successful use.
    evidence_root = root / "older-candidate"
    write(evidence_root / "old.json", stale)
    write(evidence_root / "selected.json", observation)
    report = evaluate_plan_document(plan, evidence_root, original_config.policy_sources,
                                    evaluated_at=datetime.fromisoformat(INSTANT))
    validate_assessment_results(report)
    validate_result_against_plan(report, plan)
    validate_selection_snapshot(report, [stale, observation])
    require(report["outcome"] == result["outcome"] and
            [item["status"] for item in report["results"]] ==
            [item["status"] for item in result["results"]],
            "older candidate changed IAM outcome")
    require(report["provenance"]["selectedEvidence"] == result["provenance"]["selectedEvidence"],
            "older candidate was mislabeled as successful evidence use")
    require(report["provenance"]["evidence"] == evidence_set_provenance([stale, observation]),
            "nonselected candidate disappeared from complete snapshot")
    require(report["id"] != result["id"], "complete snapshot change did not change v4 result identity")

    # Unlocked evaluation must still refuse changed private content against an old plan.
    private_document = next(private.rglob("*.json"))
    changed = load(private_document)
    changed["spec"]["checks"][0]["parameters"]["expected"] = False
    write(private_document, changed)
    changed_config = load_config(config_path)
    try:
        evaluate_plan_document(plan, args.run_root / "evidence", changed_config.policy_sources,
                               evaluated_at=datetime.fromisoformat(INSTANT))
    except ValueError as error:
        require("evaluation policy composition differs" in str(error), str(error))
    else:
        raise AssertionError("changed private-source content was accepted against old planning composition")
    print("IAM v4 source-order/location, unknown, selection provenance, and composition refusal cases passed.")


if __name__ == "__main__":
    main()
