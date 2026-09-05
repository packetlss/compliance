#!/usr/bin/env python3
"""Prove canonical v4 actual/expected composition separation and refusal."""

from __future__ import annotations

import argparse
import copy
import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import yaml

from tools.artifact_validation import validate_assessment_plan
from tools.cli import main as cli_main
from tools.composition import COMPOSITION_LOCK_SCHEMA
from tools.project_config import composition_validation, load_config

SUBJECT = "host/container-app-01"
ARTIFACT = "host__container-app-01.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def invoke(config: Path, *arguments: str) -> str:
    output = StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        cli_main(["--config", str(config), *arguments])
    return output.getvalue()


def expect_refusal(config: Path, output: Path, expected: str) -> None:
    captured = StringIO()
    refusal = ""
    with redirect_stdout(captured), redirect_stderr(captured):
        try:
            cli_main(["--config", str(config), "plan", "render", SUBJECT,
                      "--output", str(output)])
        except SystemExit as error:
            refusal = str(error)
        else:
            raise AssertionError(f"{expected} did not refuse")
    diagnostic = refusal + captured.getvalue()
    require(expected in diagnostic, f"unexpected mismatch refusal: {diagnostic}")
    require(not output.exists() or not any(output.iterdir()),
            "composition mismatch reached domain execution and emitted a plan")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    scenario = args.scenario_root.resolve()
    run = args.run_root.resolve()
    unlocked = load(run / "plans" / ARTIFACT)

    original = load(scenario / "compliance.yaml")
    config = copy.deepcopy(original)
    config["policySources"] = [
        {"name": item["name"], "path": str((scenario / item["path"]).resolve())}
        for item in original["policySources"]
    ]
    config["paths"] = {
        "inventory": str((scenario / original["paths"]["inventory"]).resolve()),
        "assignments": str((scenario / original["paths"]["assignments"]).resolve()),
        "evidence": str(run / "evidence"),
        "plan": str(run / "locked-plans"),
        "results": str(run / "locked-results"),
        "waivers": str((scenario / original["paths"]["waivers"]).resolve()),
    }
    case = run / "composition-cases"
    config_path = case / "compliance.yaml"
    write(config_path, config)
    actual = composition_validation(load_config(config_path))["actual"]
    lock = {
        "schema": COMPOSITION_LOCK_SCHEMA,
        "expected": {
            "tooling": actual["tooling"],
            "policySources": {
                item["name"]: {"content": item["content"]}
                for item in actual["policySources"]
            },
        },
    }
    write(case / "compliance.lock.yaml", lock)
    config["expectedComposition"] = {"path": "compliance.lock.yaml"}
    write(config_path, config)
    invoke(config_path, "plan", "render", SUBJECT, "--output", str(run / "locked-plans"))
    locked = load(run / "locked-plans" / ARTIFACT)
    validate_assessment_plan(locked)
    require(locked["id"] == unlocked["id"],
            "identical actual composition changed semantic plan ID under lock")
    require(locked["provenance"]["planningComposition"]["actual"]
            == unlocked["provenance"]["planningComposition"]["actual"],
            "locked and unlocked runs recorded different actual composition")
    require(unlocked["provenance"]["planningComposition"]["enforcement"]
            == {"directExpectedContent": {}, "compositionLock": None},
            "unlocked actual provenance acquired expected enforcement")
    require(locked["provenance"]["planningComposition"]["enforcement"]["compositionLock"],
            "locked run did not record distinct expected enforcement")

    wrong = {"digestAlgorithm": "compliance.example/policy-source-tree-digest/v1alpha1",
             "digest": "sha256:" + "0" * 64}
    direct = copy.deepcopy(config)
    direct.pop("expectedComposition")
    direct["policySources"][0]["expectedContent"] = wrong
    direct_path = run / "direct-mismatch/compliance.yaml"
    write(direct_path, direct)
    expect_refusal(direct_path, run / "direct-mismatch/plans", "direct expected content mismatch")

    mismatched_lock = copy.deepcopy(lock)
    first = sorted(mismatched_lock["expected"]["policySources"])[0]
    mismatched_lock["expected"]["policySources"][first]["content"] = wrong
    lock_case = run / "lock-mismatch"
    lock_config = copy.deepcopy(config)
    lock_config["paths"]["plan"] = str(lock_case / "plans")
    write(lock_case / "compliance.yaml", lock_config)
    write(lock_case / "compliance.lock.yaml", mismatched_lock)
    expect_refusal(lock_case / "compliance.yaml", lock_case / "plans", "composition-lock mismatch")
    print("v4 locked/unlocked plan identity and pre-domain mismatch refusal passed")


if __name__ == "__main__":
    main()
