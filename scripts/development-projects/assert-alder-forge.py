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
        "control-library", "alder-forge-programme", "alder-forge-corporate-platform"
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
    if (assets[ENTITY]["objective_count"], assets[ENTITY]["assessable_check_count"]) != (3, 3):
        fail("entity coverage did not expose the retained assessed Objectives")
    if (assets[LINUX]["objective_count"], assets[LINUX]["assessable_check_count"]) != (0, 1):
        fail("Linux 2409 direct-policy coverage changed")
    if (assets[SAAS]["objective_count"], assets[SAAS]["assessable_check_count"]) != (1, 1):
        fail("SaaS MFA objective coverage changed")
    if assets["workstation/alder-dev-mac-01"]["coverage_class"] != "unassigned":
        fail("unimplemented macOS policy was manufactured into coverage")

    entity = load(run_root / "coverage-entity.json")
    kinds = {item["policy_type"] for assignment in entity["assignments"] for item in assignment["policies"]}
    if kinds != {"objective"}:
        fail("entity Coverage classified an organisational obligation as technical policy")
    if any("historical_result" in json.dumps(assignment) for assignment in entity["assignments"]):
        fail("Coverage explanation inspected evidence or results")


def assert_organisation_cases(run_root: Path) -> None:
    cases = {
        "risk-assessment": ("alder-forge.periodic-risk-assessment@1", "unknown", "unknown", "unknown"),
        "software-review": ("alder-forge.authorized-software-review@1", "pass", "unknown", "unknown"),
        "awareness-training": ("alder-forge.awareness-training@1", "fail", "fail", "fail"),
    }
    objectives = {
        "alder-forge.authorized-software-review@1",
        "alder-forge.awareness-training@1",
        "alder-forge.periodic-risk-assessment@1",
    }
    for name, (selected_objective, expected_status, programme_status, overall_status) in cases.items():
        root = run_root / "organization" / name
        plan = load(root / "plans" / "entity__alder-forge-defence-systems.json")
        report = load(root / "results" / "entity__alder-forge-defence-systems.json")
        assert_plan(plan, ENTITY)
        if report.get("evaluated_at") != FIXED_INSTANT:
            fail(f"{name} assessment was not fixed-time")
        if any(result["status"] == "error" for result in report["results"]):
            fail(f"{name} manufactured an error outcome")
        statuses = requirement_statuses(report)
        if set(statuses) != objectives:
            fail(f"{name} did not retain every applicable organisational Objective")
        if statuses[selected_objective] != expected_status or any(
            status != "unknown" for objective, status in statuses.items()
            if objective != selected_objective
        ):
            fail(f"{name} did not preserve one supplied assertion fact against sibling unknown Objectives")
        baselines = baseline_statuses(report)
        if baselines.get("alder-forge.bounded-assessed-objectives@1") != programme_status:
            fail(f"{name} lost the bounded assessed-Objective roll-up status")
        if report.get("outcome") != overall_status:
            fail(f"{name} did not retain accepted aggregate roll-up semantics")


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


def assert_frozen_operator_views(run_root: Path) -> None:
    explanation = load(run_root / "entity-explain.json")
    if explanation.get("schema") != "compliance.example/assessment-explanation-view/v1alpha1":
        fail("assessment explanation did not use the public exact-history view")
    if explanation.get("historical_outcome") != "unknown":
        fail("frozen entity explanation lost its aggregate unknown outcome")
    risk_assessment = next(
        item for item in explanation["checks"]
        if item["check"]["instance_id"] == "alder-forge.entity.risk-assessment-1202.assertion"
    )
    if risk_assessment["historical_result"]["historical_outcome"] != "unknown":
        fail("frozen explanation lost risk assessment's exact unknown")
    if risk_assessment["policy_alignment"] != "realization":
        fail("risk assessment assertion was not presented as an Objective realization")

    mappings = load(run_root / "entity-mappings.json")
    expected_refs = {f"DEFSTAN-05-138-ISSUE-4:{control}" for control in ("1202", "2410", "2602")}
    if mappings.get("scope") != "exact_frozen_operation":
        fail("mapping view did not use the frozen operation")
    if {item["external_ref"] for item in mappings["mappings"]} != expected_refs:
        fail("entity mapping traceability lost an implemented obligation")
    if {item["mapping_level"] for item in mappings["mappings"]} != {"objective"}:
        fail("entity framework mappings retained a technical-policy level")
    if {item["asset_id"] for item in mappings["mappings"]} != {ENTITY}:
        fail("mapping result leaked across project members")
    if "do not establish" not in mappings.get("note", ""):
        fail("mapping view lost its traceability-only boundary")


def assert_private_sources(project: Path, control_library: Path) -> None:
    sources = {
        "alder-forge-programme": (project / "policy/programme/policies", (0, 3, 1, 3)),
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
    for source in (project / "policy/programme/policies", project / "policy/corporate-platform/policies"):
        if (source / "controls").exists() or (source / "schemas").exists():
            fail("project source introduced a reusable Control or evidence schema")
    assert_coverage(root)
    assert_organisation_cases(root)
    assert_technical_cases(root)
    assert_frozen_operator_views(root)
    framework = load(root / "framework-status.json")
    if framework.get("state") != "not_satisfied":
        fail("declared framework projection did not preserve the direct/awareness failures")
    rows = {row["id"]: row for row in framework.get("obligations", [])}
    if rows.get("0002", {}).get("state") != "unknown" or rows.get("1101", {}).get("state") != "pass":
        fail("framework declaration did not retain external and governance accounting")
    assert_private_sources(project, control_library)
    print("Alder Forge deterministic current-capability assertions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
