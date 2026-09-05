#!/usr/bin/env python3
"""Run the retained lower-level IAM realization roll-up assertion fixture."""

from __future__ import annotations

import argparse
import copy
from itertools import permutations
import json
from pathlib import Path

from tools.control_realization import (
    ControlRealizationError,
    roll_up_realization,
    roll_up_requirement_baseline,
    select_realization,
    validate_realization_lineage,
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirement", type=Path, required=True)
    parser.add_argument("--realization", type=Path, required=True)
    parser.add_argument("--base-realization", type=Path, required=True)
    parser.add_argument("--technical-results", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()

    requirement = load(args.requirement)
    realization = load(args.realization)
    base_realization = load(args.base_realization)
    technical_results = load(args.technical_results)
    baseline = load(args.baseline)

    lineage_errors = validate_realization_lineage(realization, base_realization)
    if lineage_errors:
        raise SystemExit("ERROR: " + "; ".join(lineage_errors))
    for order in permutations([base_realization, realization]):
        selected = select_realization(requirement, technical_results["subject"], list(order))
        if selected != realization:
            raise SystemExit("ERROR: source order changed private realization selection")
        missing = copy.deepcopy(technical_results["subject"])
        missing["labels"].pop("iam-profile", None)
        try:
            select_realization(requirement, missing, list(order))
        except ControlRealizationError as error:
            if "no realization applies" not in str(error):
                raise
        else:
            raise SystemExit("ERROR: missing selection label acquired a realization")
    overlapping = copy.deepcopy(base_realization)
    overlapping["spec"]["applies_to"] = copy.deepcopy(realization["spec"]["applies_to"])
    for order in permutations([overlapping, realization]):
        try:
            select_realization(requirement, technical_results["subject"], list(order))
        except ControlRealizationError as error:
            if "multiple realizations apply" not in str(error):
                raise
        else:
            raise SystemExit("ERROR: overlapping realizations acquired order precedence")
    requirement_assessment = roll_up_realization(
        requirement, realization, technical_results
    )
    baseline_assessment = roll_up_requirement_baseline(
        baseline, [requirement_assessment]
    )
    print(
        json.dumps(
            {
                "requirement_assessment": requirement_assessment,
                "baseline_assessment": baseline_assessment,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
