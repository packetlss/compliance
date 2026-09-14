#!/usr/bin/env python3
"""Assert deterministic public workflow behavior for the Alder Forge slice."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.policy_sources import PolicySource
from tools.render_plan import (
    load_policy_catalogs,
    load_requirement_catalogs,
    validate_rego_entrypoints,
)


FIXED_INSTANT = "2026-09-01T00:00:00Z"
ENTITY = "entity/alder-forge-defence-systems"
LINUX = "host/alder-build-01"
SAAS = "saas/alder-admin-tenant"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == 71
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def result_by_instance(report: dict, instance_id: str) -> dict:
    for result in report["results"]:
        if result["instance_id"] == instance_id:
            return result
    fail(f"assessment result lost {instance_id}")


def requirement_statuses(report: dict) -> dict[str, str]:
    return {item["requirement"]: item["status"] for item in report["requirement_assessments"]}


def baseline_statuses(report: dict) -> dict[str, str]:
    return {
        item["baseline"]: item["status"]
        for item in report["requirement_baseline_assessments"]
    }


def assert_plan(plan: dict, subject_id: str) -> None:
    if plan.get("schema") != "compliance.example/assessment-plan/v4":
        fail(f"{subject_id} did not retain a v4 assessment plan")
    if plan.get("subject", {}).get("id") != subject_id:
        fail(f"plan subject changed for {subject_id}")
    operation = plan.get("operation", {})
    members = operation.get("members", [])
    if len(members) != 1 or members[0].get("subject_id") != subject_id:
        fail(f"{subject_id} plan leaked an operation member")
    if not all(is_digest(value) for value in (
        plan.get("id"), operation.get("operation_id"), members[0].get("member_plan_digest")
    )):
        fail(f"{subject_id} plan lost exact content identities")
    sources = plan.get("provenance", {}).get("planningComposition", {}).get("actual", {}).get("policySources", [])
    if {source.get("name") for source in sources} != {
        "control-library", "alder-forge-corporate-platform"
    }:
        fail(f"{subject_id} plan lost independently named policy source provenance")
    if any(not is_digest(source.get("content", {}).get("digest")) for source in sources):
        fail(f"{subject_id} plan has an invalid policy-source digest")


def assert_coverage(run_root: Path) -> None:
    document = load(run_root / "coverage-assets.json")
    if "historical" in json.dumps(document).lower() or "result" in document:
        fail("coverage consulted historical assessment state")
    assets = {item["asset_id"]: item for item in document["assets"]}
    expected = {ENTITY, LINUX, SAAS, "workstation/alder-dev-mac-01"}
    if set(assets) != expected:
        fail(f"inventory coverage lost or added supplied subjects: {set(assets)}")
    if (assets[ENTITY]["objective_count"], assets[ENTITY]["assessable_check_count"]) != (0, 0):
        fail("governance-only entity obligations became assessable policy")
    if (assets[LINUX]["objective_count"], assets[LINUX]["assessable_check_count"]) != (0, 1):
        fail("Linux 2409 direct-policy coverage changed")
    if (assets[SAAS]["objective_count"], assets[SAAS]["assessable_check_count"]) != (1, 1):
        fail("SaaS MFA objective coverage changed")
    if assets["workstation/alder-dev-mac-01"]["coverage_class"] != "unassigned":
        fail("unimplemented macOS policy was manufactured into coverage")

    entity = load(run_root / "coverage-entity.json")
    kinds = {item["policy_type"] for assignment in entity["assignments"] for item in assignment["policies"]}
    if kinds:
        fail("entity Coverage turned governance-only obligations into policy")
    if any("historical_result" in json.dumps(assignment) for assignment in entity["assignments"]):
        fail("Coverage explanation inspected evidence or results")


def assert_technical_cases(run_root: Path) -> None:
    root = run_root / "technical"
    linux_plan = load(root / "plans" / "host__alder-build-01.json")
    linux = load(root / "results" / "host__alder-build-01.json")
    saas_plan = load(root / "plans" / "saas__alder-admin-tenant.json")
    saas = load(root / "results" / "saas__alder-admin-tenant.json")
    assert_plan(linux_plan, LINUX)
    assert_plan(saas_plan, SAAS)
    if result_by_instance(linux, "alder-forge.corporate-linux.authorized-software-2409")["status"] != "fail":
        fail("Linux 2409 unexpected package did not fail")
    if linux["requirement_assessments"] or linux["requirement_baseline_assessments"]:
        fail("Linux direct policy acquired an Objective")
    if result_by_instance(saas, "alder-forge.saas.critical-access.mfa-enforced")["status"] != "pass":
        fail("SaaS MFA fact did not pass")
    if requirement_statuses(saas) != {"alder-forge.critical-access.mfa@1": "pass"}:
        fail("SaaS result leaked or lost the MFA Objective")
    if baseline_statuses(saas) != {"alder-forge.critical-access-mfa@1": "pass"}:
        fail("SaaS result leaked or lost the MFA Objective baseline")
    if any(result["status"] == "error" for report in (linux, saas) for result in report["results"]):
        fail("technical cases manufactured an error outcome")


def assert_framework_accounting(run_root: Path) -> None:
    framework = load(run_root / "framework-status.json")
    if framework.get("state") != "not_satisfied":
        fail("declared framework projection did not preserve the direct package failure")
    rows = {row["id"]: row for row in framework.get("obligations", [])}
    expected_states = {
        "0002": "unknown", "1101": "pass", "1202": "unknown", "2201": "pass",
        "2409": "fail", "2410": "pass", "2602": "unknown",
    }
    expected_bases = {
        "0002": "governance-declared", "1101": "governance-declared",
        "1202": "governance-declared", "2201": "evidence-assessed-objective",
        "2409": "direct-technical-policy", "2410": "governance-declared",
        "2602": "governance-declared",
    }
    if {item: rows.get(item, {}).get("state") for item in expected_states} != expected_states:
        fail("framework declaration did not retain exact ADR 0022 obligation states")
    if {item: rows.get(item, {}).get("basis") for item in expected_bases} != expected_bases:
        fail("framework declaration did not retain exact ADR 0022 obligation bases")
    if (run_root / "framework/results/entity__alder-forge-defence-systems.json").exists():
        fail("governance-only Alder obligations produced AssessmentResults")


def assert_private_sources(project: Path, control_library: Path) -> None:
    sources = {
        "alder-forge-corporate-platform": (project / "policy/corporate-platform/policies", (1, 1, 1, 1)),
    }
    for name, (path, expected) in sources.items():
        controls, baselines, errors = load_policy_catalogs((
            PolicySource("control-library", control_library), PolicySource(name, path),
        ))
        if errors:
            fail(f"{name} did not independently validate its baseline policy: {errors}")
        errors = validate_rego_entrypoints((
            PolicySource("control-library", control_library), PolicySource(name, path),
        ), controls)
        if errors:
            fail(f"{name} did not independently validate reusable entrypoints: {errors}")
        requirements, requirement_baselines, realizations, errors = load_requirement_catalogs(
            (PolicySource("control-library", control_library), PolicySource(name, path)), controls,
        )
        actual = (len(baselines), len(requirements), len(requirement_baselines), len(realizations))
        if errors or actual != expected:
            fail(f"{name} did not independently validate its intended private policy ownership: {actual}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--control-library-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.run_root.resolve()
    project = args.project_root.resolve()
    control_library = args.control_library_root.resolve()
    for source in (project / "policy/corporate-platform/policies",):
        if (source / "controls").exists() or (source / "schemas").exists():
            fail("project source introduced a reusable Control or evidence schema")
    assert_coverage(root)
    assert_technical_cases(root)
    assert_framework_accounting(root)
    assert_private_sources(project, control_library)
    print("Alder Forge deterministic current-capability assertions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
