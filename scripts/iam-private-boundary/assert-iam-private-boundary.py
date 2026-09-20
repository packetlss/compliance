#!/usr/bin/env python3
"""Assert preserved IAM assessment behavior and private-source provenance."""

from __future__ import annotations

import argparse
from collections import Counter
import json

from tools.artifact_validation import validate_assessment_plan, validate_assessment_results
from tools.assessment_provenance import validate_result_against_plan, validate_selection_snapshot
from tools.evaluator import opa_evaluator_identity
from tools.evidence_provenance import evidence_set_provenance
from tools.policy_sources import source_tree_digest
from tools.render_plan import content_digest
from tools.tooling_source import TOOLING_SOURCE_DIGEST_ALGORITHM, tooling_source_digest
from pathlib import Path

FIXED_INSTANT = "2026-09-01T00:00:00Z"
SOURCE_NAMES = ["control-library", "environment-private", "verification-policy"]
CONTROL_INSTANCES = {
    "restricted.linux.rbac.sssd-installed",
    "restricted.linux.rbac.sssd-domain-configured",
    "restricted.linux.rbac.ssh-central-group-required",
    "restricted.linux.rbac.unmanaged-local-login-absent",
}


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


def assert_config(config: dict, assembly_root: Path) -> None:
    if config.get("schema") != "compliance.example/project-config/v1alpha3":
        fail("IAM config must use v1alpha3")
    sources = config.get("policy_sources", [])
    if [source.get("name") for source in sources] != SOURCE_NAMES:
        fail(f"config lost the exact named source set: {sources}")
    paths = {source["name"]: Path(source["path"]).resolve() for source in sources}
    expected_private = (assembly_root / "external-sources/environment-private").resolve()
    fixture_root = (
        assembly_root / "verification/fixtures/iam-private-boundary"
    ).resolve()
    if paths["environment-private"] != expected_private:
        fail(f"environment-private resolved to the wrong root: {paths['environment-private']}")
    if paths["environment-private"].is_relative_to(fixture_root):
        fail("environment-private resolved beneath the fixture tree")
    if (fixture_root / "policy").exists():
        fail("execution fixture still exposes its checked-in policy subtree")
    for source in sources:
        if not Path(source["path"]).resolve().is_relative_to(assembly_root):
            fail(f"policy source escaped the temporary assembly: {source}")


def assert_plan(plan: dict, config: dict) -> None:
    validate_assessment_plan(plan)
    if plan.get("schema") != "compliance.example/assessment-plan/v4":
        fail("IAM plan changed assessment schema")
    operation = plan.get("operation", {})
    member = next((row for row in operation.get("members", [])
                   if row.get("subject_id") == "host/restricted-linux-01"), {})
    if not all(is_digest(value) for value in (
        plan.get("id"), operation.get("operation_id"), member.get("member_plan_digest")
    )):
        fail("IAM plan lost bound, operation, or member identity")
    if plan.get("subject", {}).get("id") != "host/restricted-linux-01":
        fail("IAM plan lost the restricted synthetic subject")
    sources = plan.get("provenance", {}).get("planningComposition", {}).get(
        "actual", {}).get("policySources", [])
    if [source.get("name") for source in sources] != SOURCE_NAMES:
        fail(f"IAM plan lost canonical named-source provenance: {sources}")
    source_digests = {
        source.get("name"): source.get("content", {}).get("digest") for source in sources
    }
    private_root = next(
        Path(source["path"])
        for source in config["policy_sources"]
        if source["name"] == "environment-private"
    )
    if source_digests.get("environment-private") != source_tree_digest(private_root):
        fail(f"IAM plan has the wrong private-source digest: {source_digests}")
    if any(not is_digest(digest) for digest in source_digests.values()):
        fail("IAM plan contains an invalid policy-source content identity")

    requirements = plan.get("requirements", [])
    if len(requirements) != 1:
        fail(f"IAM plan has an unexpected requirement set: {requirements}")
    requirement = requirements[0]
    if requirement.get("reference") != "company.iam.role-based-access@1":
        fail("IAM plan selected the wrong requirement")
    realization = requirement.get("realization", {})
    if realization.get("reference") != "restricted.linux.central-role-access@1":
        fail(f"IAM plan selected the wrong realization: {realization}")
    realization_sources = realization.get("policy_sources", [])
    if {source.get("policy_source") for source in realization_sources} != {
        "environment-private"
    }:
        fail(f"restricted realization lost private-source provenance: {realization_sources}")
    if realization.get("based_on", {}).get("realization") != (
        "company.linux.central-role-access@1"
    ):
        fail("restricted realization lost non-inheriting based_on provenance")
    if requirement.get("adoption", {}).get("status") != "implemented":
        fail("IAM plan lost its authored adoption annotation")

    controls = plan.get("controls", [])
    if {control.get("instance_id") for control in controls} != CONTROL_INSTANCES:
        fail("IAM plan lost one or more restricted technical checks")
    freshness = {
        dependency.get("max_age")
        for control in controls
        for dependency in control.get("evidence", [])
    }
    if freshness != {"3600s"}:
        fail(f"private 1h ParameterPolicy tailoring did not reach every Check: {freshness}")
    private_parameters = [
        item for item in plan.get("parameters", {}).get("documents", [])
        if item.get("reference") == "restricted.iam.role-based-access@1"
    ]
    if len(private_parameters) != 1 or {
        source.get("policy_source")
        for source in private_parameters[0].get("policy_sources", [])
    } != {"environment-private"}:
        fail("IAM plan lost the explicitly applicable private ParameterPolicy")
    for control in controls:
        if control.get("disposition") != "evaluate":
            fail(f"restricted control is no longer evaluated: {control}")
        if not is_digest(control.get("definition_fingerprint")):
            fail(f"control lost its definition fingerprint: {control}")
        if not any(
            item.get("realization") == "restricted.linux.central-role-access@1"
            for item in control.get("lineage", [])
        ):
            fail(f"control lost restricted realization lineage: {control}")


def assert_result(result: dict) -> None:
    validate_assessment_results(result)
    if result.get("schema") != "compliance.example/assessment-results/v4":
        fail("IAM result changed assessment schema")
    if result.get("evaluated_at") != FIXED_INSTANT:
        fail(f"IAM result changed deterministic instant: {result.get('evaluated_at')}")
    summary = Counter(item["status"] for item in result["results"])
    if summary != {"pass": 3, "fail": 1}:
        fail(f"IAM technical pass/fail behavior changed: {summary}")
    failed = {
        item.get("instance_id")
        for item in result.get("results", [])
        if item.get("status") == "fail"
    }
    if failed != {"restricted.linux.rbac.ssh-central-group-required"}:
        fail(f"IAM failure moved to another technical check: {failed}")
    requirements = result.get("requirement_assessments", [])
    baselines = result.get("requirement_baseline_assessments", [])
    if len(requirements) != 1 or requirements[0].get("status") != "fail":
        fail(f"IAM objective no longer fails from technical evidence: {requirements}")
    if len(baselines) != 1 or baselines[0].get("status") != "fail":
        fail(f"IAM top requirement baseline no longer fails: {baselines}")



def assert_provenance(plan: dict, result: dict, config: dict, assembly_root: Path,
                      documents: list[dict]) -> None:
    expected_actual = {
        "tooling": {
            "source": {
                "digestAlgorithm": TOOLING_SOURCE_DIGEST_ALGORITHM,
                "digest": tooling_source_digest(assembly_root / "tooling"),
            },
            "execution": {"kind": "source"},
        },
        "policySources": [
            {"name": source["name"], "content": {
                "digestAlgorithm": "compliance.example/policy-source-tree-digest/v1alpha1",
                "digest": source_tree_digest(Path(source["path"])),
            }}
            for source in config["policy_sources"]
        ],
    }
    for stage in (plan["provenance"]["planningComposition"],
                  result["provenance"]["evaluationComposition"]):
        if stage["actual"] != expected_actual:
            fail("actual composition does not identify the executing tooling and materialized sources")
        if stage["enforcement"] != {"directExpectedContent": {}, "compositionLock": None}:
            fail("unlocked fixture claimed expected enforcement")
    if result["provenance"]["evaluator"] != opa_evaluator_identity().document():
        fail("result does not identify the actual OPA version and executable bytes")
    if result["provenance"]["evidence"] != evidence_set_provenance(documents):
        fail("result lost complete subject evidence snapshot identity")
    if "planningComposition" in result["provenance"]:
        fail("result copied planning-stage provenance from its bound plan")
    validate_result_against_plan(result, plan)
    validate_selection_snapshot(result, documents)
    selections = result["provenance"]["selectedEvidence"]
    if {item["instance_id"] for item in selections} != CONTROL_INSTANCES or len(selections) != 4:
        fail("IAM result lost successful evidence selection for a technical check")
    for item in selections:
        if item["collected_at"] != FIXED_INSTANT or item["dependency_id"] != "observation":
            fail("IAM result lost factual collection instant or assessed evidence requirement")

    roots = {source["name"]: Path(source["path"]) for source in config["policy_sources"]}
    requirement_document = load(roots["verification-policy"] / "requirements/company/company-role-based-access.json")
    realization_document = load(roots["environment-private"] / "realizations/restricted/restricted-linux-role-based-access.json")
    requirement = plan["requirements"][0]
    realization = requirement["realization"]
    if "classification" in realization:
        fail("IAM plan retained retired realization information classification")
    if "classification" in realization_document.get("metadata", {}):
        fail("private realization retained retired information classification")
    if requirement["digest"] != content_digest(requirement_document):
        fail("IAM requirement objective identity changed")
    if realization["digest"] != content_digest(realization_document):
        fail("IAM selected realization identity changed")
    if realization["based_on"] != realization_document["spec"]["based_on"]:
        fail("IAM non-inheriting realization lineage changed")
    if set(requirement["technical_instance_ids"]) != CONTROL_INSTANCES:
        fail("IAM requirement lost technical-control linkage")
    assessment = result["requirement_assessments"][0]
    if assessment["requirement"] != requirement["reference"] or assessment["status"] != "fail":
        fail("IAM compact requirement result no longer corresponds to its exact plan")
    checks = {check["instance_id"]: check for check in realization_document["spec"]["checks"]}
    for control in plan["controls"]:
        check = checks[control["instance_id"]]
        if control["parameters"] != check["parameters"] or control["implementation"] != check["implementation"]:
            fail("IAM plan changed restricted technical intent")


def assert_mappings(report: dict) -> None:
    mappings = report.get("mappings", [])
    matches = [
        mapping
        for mapping in mappings
        if mapping.get("external_ref") == "example-regulatory-framework:IAM-01"
    ]
    if len(matches) != 1 or matches[0].get("historical_outcome") != "fail":
        fail(f"IAM objective traceability mapping changed: {matches}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assembly-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    assembly_root = args.assembly_root.resolve()
    run_root = args.run_root.resolve()

    config = load(run_root / "config.json")
    plan = load(run_root / "plans/host__restricted-linux-01.json")
    result = load(run_root / "results/host__restricted-linux-01.json")
    assert_config(config, assembly_root)
    assert_plan(plan, config)
    assert_result(result)
    documents = [load(path) for path in sorted((run_root / "evidence").rglob("*.json"))]
    assert_provenance(plan, result, config, assembly_root, documents)
    assert_mappings(load(run_root / "mappings.json"))
    explain = (run_root / "explain.txt").read_text(encoding="utf-8")
    for expected in (
        "restricted.linux.central-role-access@1",
        "company.linux.central-role-access@1",
        "restricted.linux.rbac.ssh-central-group-required",
        "Restrict interactive SSH access",
    ):
        if expected not in explain:
            fail(f"IAM explanation lost {expected!r}")

    print("IAM private-boundary runtime and provenance assertions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
