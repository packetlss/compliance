#!/usr/bin/env python3
"""Assert deterministic machine-readable outcomes for linux-hardening-rollout."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from tools.artifact_validation import validate_assessment_plan, validate_assessment_results
from tools.assessment_provenance import validate_result_against_plan, validate_selection_snapshot
from tools.evaluator import opa_evaluator_identity
from tools.evidence_provenance import evidence_set_provenance
from tools.policy_sources import source_tree_digest
from tools.operation import plan_coverage
from tools.project_config import load_config
from tools.tooling_source import TOOLING_SOURCE_DIGEST_ALGORITHM, tooling_source_digest

FIXED_INSTANT = datetime.fromisoformat("2026-09-01T00:00:00+00:00")


def fail(message: str) -> None:
    raise SystemExit(f"scenario assertion failed: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def load_json(path: Path) -> dict:
    require(path.is_file(), f"missing JSON artifact: {path}")
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {path}: {error}")
    require(isinstance(value, dict), f"expected object in {path}")
    return value


def parse_instant(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        fail(f"invalid timestamp {value!r}: {error}")


def assert_fixed_instant(value: str, label: str) -> None:
    require(parse_instant(value) == FIXED_INSTANT, f"{label} is not the fixed instant: {value}")


def expected_summary(*, passed: int = 0, failed: int = 0, unknown: int = 0, waived: int = 0) -> dict:
    return {
        "pass": passed,
        "fail": failed,
        "unknown": unknown,
        "not_applicable": 0,
        "error": 0,
        "waived": waived,
    }


def is_digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None


def assert_assessment_plan_handoff(plan: dict, actual: dict) -> None:
    """Prove the retained plan is a complete external-adapter handoff."""
    require(plan.get("schema") == "compliance.example/assessment-plan/v4", "unexpected assessment-plan schema")
    validate_assessment_plan(plan)
    require(is_digest(plan.get("id")), "assessment plan ID is not content-addressed")
    require(is_digest(plan["provenance"]["planningComposition"]["compositionDigest"]),
            "planning composition is not content-addressed")

    subject = plan.get("subject", {})
    require(subject.get("id") == "host/container-app-01", "adapter handoff subject identity changed")
    require(subject.get("type") == "linux-host", "adapter handoff subject type changed")

    sources = plan["provenance"]["planningComposition"]["actual"]["policySources"]
    require(
        {source.get("name") for source in sources} == {"control-library", "verification-policy"},
        f"unexpected named policy sources: {sources}",
    )
    require(all(is_digest(source.get("content", {}).get("digest")) for source in sources), "policy source digest is missing")
    planning = plan.get("provenance", {}).get("planningComposition", {})
    require(planning.get("actual") == actual, "planning composition differs from assembled runtime bytes")
    require(
        planning.get("enforcement") == {"directExpectedContent": {}, "compositionLock": None},
        "unlocked plan claims expected enforcement",
    )

    controls = plan.get("controls", [])
    require(controls, "adapter handoff contains no active controls")
    require(
        any(
            control.get("instance_id")
            == "company.container-runtime.containerd-package"
            and control.get("parameters")
            == {
                "ecosystem": "linux-native",
                "required": [{"id": "containerd"}],
            }
            for control in controls
        ),
        "containerd control or resolved parameters changed",
    )
    forwarding = next(
        (
            control
            for control in controls
            if control.get("instance_id")
            == "benchmark.example.linux-server.ip-forwarding-disabled"
        ),
        None,
    )
    require(forwarding is not None, "tailored forwarding control is missing")
    require(forwarding.get("implementation") == "linux.sysctl.required", "stable forwarding implementation changed")
    require(
        forwarding.get("title") == "Linux kernel settings match policy",
        "tailoring changed the Control-owned check title",
    )
    require(
        forwarding.get("purpose")
        == "Verify that configured Linux kernel parameters have the values mandated by policy.",
        "tailoring changed the Control-owned check purpose",
    )
    require(
        forwarding.get("parameters")
        == {"settings": [{"key": "net.ipv4.ip_forward", "value": "1"}]},
        "resolved forwarding parameters changed",
    )
    require(forwarding.get("disposition") == "evaluate", "active control disposition changed")
    require(is_digest(forwarding.get("definition_fingerprint")), "control definition fingerprint is missing")
    require(
        any(item.get("operation") == "tailor" for item in forwarding.get("derivations", [])),
        "control derivation lineage is missing",
    )
    tailoring = next(
        item for item in forwarding["derivations"]
        if item.get("operation") == "tailor"
    )
    require(
        tailoring["before"]["parameters"]
        == {"settings": [{"key": "net.ipv4.ip_forward", "value": "0"}]},
        "base forwarding value changed",
    )
    require(
        tailoring["after"]["parameters"]
        == {"settings": [{"key": "net.ipv4.ip_forward", "value": "1"}]},
        "tailored forwarding value changed",
    )
    require(
        any(item.get("id") == "DEV-LINUX-CONTAINER-001" for item in forwarding.get("deviations", [])),
        "approved control deviation is missing",
    )
    require(forwarding.get("lineage"), "control lineage is missing")
    require(
        any(item.get("baseline") == "company.container-runtime-host@1" for item in forwarding.get("provenance", [])),
        "baseline/control provenance is missing",
    )
    require(
        all(item.get("policy_source") and item.get("path") for item in forwarding.get("implementation_sources", [])),
        "control source provenance is missing",
    )

    requirements = plan.get("requirements", [])
    require(len(requirements) == 1, "representative plan must carry one objective")
    requirement = requirements[0]
    require(requirement.get("reference") == "company.iam.role-based-access@1", "requirement lineage changed")
    require(
        requirement.get("external_refs") == ["example-regulatory-framework:IAM-01"],
        "explicit regulatory mapping changed",
    )
    realization = requirement.get("realization", {})
    require(
        realization.get("reference") == "company.linux.central-role-access@1",
        "selected realization lineage changed",
    )
    require(realization.get("policy_sources"), "realization source provenance is missing")
    technical_ids = set(requirement.get("technical_instance_ids", []))
    require(
        "company.linux.rbac.sssd-installed" in technical_ids,
        "requirement-to-technical-control lineage is missing",
    )
    realization_control = next(
        (
            control
            for control in controls
            if control.get("instance_id") == "company.linux.rbac.sssd-installed"
        ),
        None,
    )
    require(realization_control is not None, "realization control is missing")
    require(
        any(
            item.get("requirement") == "company.iam.role-based-access@1"
            and item.get("realization") == "company.linux.central-role-access@1"
            for item in realization_control.get("provenance", [])
        ),
        "control requirement/realization provenance is missing",
    )


def assert_assessment_result(
    report: dict,
    *,
    subject_id: str,
    summary: dict,
    requirement_status: str,
    baseline_status: str,
    plan: dict,
    actual: dict,
    evidence: list[dict],
) -> None:
    require(report.get("schema") == "compliance.example/assessment-results/v4", f"unexpected result schema for {subject_id}")
    validate_assessment_results(report)
    validate_result_against_plan(report, plan)
    validate_selection_snapshot(report, evidence)
    require(report.get("subject_id") == subject_id, f"wrong result subject: {report.get('subject_id')}")
    assert_fixed_instant(report.get("evaluated_at", ""), f"{subject_id} evaluated_at")
    counts = Counter(item["status"] for item in report.get("results", []))
    require({status: counts[status] for status in summary} == summary,
            f"unexpected technical outcomes for {subject_id}: {dict(counts)}")

    requirements = report.get("requirement_assessments", [])
    require(len(requirements) == 1, f"expected one requirement assessment for {subject_id}")
    require(requirements[0].get("status") == requirement_status, f"unexpected objective status for {subject_id}")

    baselines = report.get("requirement_baseline_assessments", [])
    require(len(baselines) == 1, f"expected one requirement-baseline assessment for {subject_id}")
    require(baselines[0].get("status") == baseline_status, f"unexpected objective-baseline status for {subject_id}")

    provenance = report.get("provenance", {})
    require("planningComposition" not in provenance,
            f"result copied planning provenance for {subject_id}")
    evaluation = provenance.get("evaluationComposition", {})
    require(evaluation.get("actual") == actual,
            f"evaluation composition differs from assembled bytes for {subject_id}")
    require(evaluation.get("actual", {}).get("policySources")
            == plan["provenance"]["planningComposition"]["actual"]["policySources"],
            f"evaluation source set differs from persisted plan for {subject_id}")
    require(evaluation.get("enforcement") == {"directExpectedContent": {}, "compositionLock": None},
            f"unlocked evaluation claims expected enforcement for {subject_id}")
    require(provenance.get("evaluator") == opa_evaluator_identity().document(),
            f"evaluator identity changed for {subject_id}")
    require(provenance.get("evidence") == evidence_set_provenance(evidence),
            f"evidence snapshot incomplete for {subject_id}")

    available_types = {document["type"] for document in evidence}
    expected_dependencies = {
        (control["instance_id"], dependency["id"])
        for control in plan.get("controls", [])
        for dependency in control.get("evidence", [])
        if dependency["type"] in available_types
    }
    selections = provenance.get("selectedEvidence", [])
    require(
        {(item["instance_id"], item["dependency_id"]) for item in selections}
        == expected_dependencies,
        f"successful selections differ from available assessed dependencies for {subject_id}",
    )
    snapshot_documents = {
        (item["id"], item["digest"])
        for item in provenance["evidence"]["documents"]
    }
    require(
        {(item["evidence_id"], item["evidence_digest"]) for item in selections}
        <= snapshot_documents,
        f"successful selection is absent from the complete snapshot for {subject_id}",
    )


def assert_assurance_narrative(scenario_readme: Path) -> None:
    text = " ".join(scenario_readme.read_text().lower().split())
    required_phrases = (
        "access-request approval",
        "periodic human access review",
        "image promotion",
        "configuration-application records",
        "cannot demonstrate complete framework coverage",
        "no certification, legal-compliance, or whole-framework claim",
    )
    for phrase in required_phrases:
        require(phrase in text, f"scenario assurance limitation disappeared: {phrase}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()

    run_root = args.run_root.resolve()
    scenario_root = args.scenario_root.resolve()
    integration_root = scenario_root.parents[3]

    require(scenario_root.is_dir(), f"scenario root not found: {scenario_root}")
    require(run_root != scenario_root and scenario_root not in run_root.parents, "run artifacts must live outside the tracked scenario tree")

    config = load_config(scenario_root / "compliance.yaml")
    require(config.schema == "compliance.example/project-config/v1alpha3", "predecessor project config remains")
    require("resourceSchema" not in config.paths, "scenario authors the executing tooling's inventory schema")
    require({source.name: source.path for source in config.policy_sources} == {
        "control-library": integration_root / "policy-sources/control-library/policies",
        "verification-policy": integration_root / "policy-sources/verification-policy/policies",
    }, "exact named-source materialization changed")
    actual = {
        "tooling": {
            "source": {"digestAlgorithm": TOOLING_SOURCE_DIGEST_ALGORITHM,
                       "digest": tooling_source_digest(integration_root / "tooling")},
            "execution": {"kind": "source"},
        },
        "policySources": [{"name": source.name, "content": {
            "digestAlgorithm": "compliance.example/policy-source-tree-digest/v1alpha1",
            "digest": source_tree_digest(source.path),
        }} for source in config.policy_sources],
    }

    waiver_catalog = load_json(run_root / "waivers.json")
    require(waiver_catalog.get("summary") == {"active": 1, "scheduled": 0, "expired": 0}, f"unexpected waiver lifecycle summary: {waiver_catalog.get('summary')}")
    waivers = waiver_catalog.get("waivers", [])
    require(len(waivers) == 1, "expected exactly one waiver at the fixed instant")
    waiver = waivers[0]
    require(waiver.get("id") == "standard-app-01-auditd-rollout", "unexpected active waiver")
    require(waiver.get("state") == "active", "auditd rollout waiver is not active")
    require(waiver.get("subject_id") == "host/standard-app-01", "waiver subject changed")
    require(waiver.get("instance_id") == "company.linux-server.audit-package", "waiver control changed")

    evidence_files = sorted((run_root / "evidence").glob("*.json"))
    require(evidence_files, "collector produced no evidence")
    for path in evidence_files:
        document = load_json(path)
        assert_fixed_instant(document.get("collected_at", ""), f"{path.name} collected_at")

    standard_plan = load_json(run_root / "plans/host__standard-app-01.json")
    standard_evidence = [load_json(path) for path in evidence_files
                         if load_json(path).get("subject", {}).get("id") == "host/standard-app-01"]
    standard = load_json(run_root / "results/host__standard-app-01.json")
    assert_assessment_result(
        standard,
        subject_id="host/standard-app-01",
        summary=expected_summary(passed=2, unknown=4, waived=1),
        requirement_status="unknown",
        baseline_status="unknown",
        plan=standard_plan,
        actual=actual,
        evidence=standard_evidence,
    )
    standard_requirement = standard["requirement_assessments"][0]
    requirement_instances = set(standard_plan["requirements"][0]["technical_instance_ids"])
    require(sum(item["status"] == "unknown" and item["instance_id"] in requirement_instances
                for item in standard["results"]) == 4,
            "standard missing-access checks are no longer four unknowns")
    waived = [item for item in standard.get("results", []) if item.get("instance_id") == "company.linux-server.audit-package"]
    require(len(waived) == 1 and waived[0].get("status") == "waived", "audit-package failure is not waived")
    require(waived[0].get("waiver", {}).get("underlying_status") == "fail", "waiver no longer preserves the underlying failure")
    require(
        any(
            control.get("instance_id") == "company.linux-server.audit-package"
            and control.get("parameters")
            == {"ecosystem": "linux-native", "required": [{"id": "auditd"}]}
            for control in standard_plan.get("controls", [])
        ),
        "standard assessment plan no longer retains the auditd control",
    )

    container_plan = load_json(run_root / "plans/host__container-app-01.json")
    container_evidence = [load_json(path) for path in evidence_files
                          if load_json(path).get("subject", {}).get("id") == "host/container-app-01"]
    container = load_json(run_root / "results/host__container-app-01.json")
    assert_assessment_result(
        container,
        subject_id="host/container-app-01",
        summary=expected_summary(passed=8),
        requirement_status="pass",
        baseline_status="pass",
        plan=container_plan,
        actual=actual,
        evidence=container_evidence,
    )
    assert_assessment_plan_handoff(container_plan, actual)
    forwarding = next(
        row for row in container_plan["controls"]
        if row["instance_id"] == "company.linux-server.ip-forwarding"
    )
    require(forwarding["title"] == "Linux kernel settings match policy",
            "container plan lost Check title")
    require(forwarding["purpose"] ==
            "Verify that configured Linux kernel parameters have the values mandated by policy.",
            "container plan lost Check purpose")
    require(forwarding["derivations"] and forwarding["deviations"][0]["id"] ==
            "DEV-LINUX-CONTAINER-001", "container plan lost exact tailoring facts")

    waived_result = next(item for item in standard["results"]
                         if item["instance_id"] == "company.linux-server.audit-package")
    require(waived_result.get("waiver", {}).get("id") == "standard-app-01-auditd-rollout",
            "waiver provenance lost the applied waiver identity")
    require(is_digest(waived_result.get("waiver", {}).get("digest")),
            "waiver provenance lost its exact snapshot digest")
    require("waiver_revision" not in standard and "waiver_revision" not in waived_result,
            "result retained whole-catalog waiver revision")

    conflict = load_json(run_root / "plans/host__persona-conflict-01.json")
    require(conflict.get("schema") == "compliance.example/assessment-plan/v4", "unexpected conflict plan schema")
    validate_assessment_plan(conflict)
    require(conflict["provenance"]["planningComposition"]["actual"] == actual,
            "invalid plan lost actual planning composition")
    require(conflict.get("resolution", {}).get("status") == "invalid", "contradictory persona unexpectedly resolved")
    require(
        any(
            error.get("type") == "control-instance-conflict"
            for error in conflict.get("resolution", {}).get("errors", [])
        ),
        "contradictory persona lost its no-precedence conflict evidence",
    )
    require(plan_coverage(conflict)["assessable"] is False, "contradictory persona became assessable")
    require(not (run_root / "results/host__persona-conflict-01.json").exists(), "assessment result was emitted for contradictory persona")

    assert_assurance_narrative(scenario_root / "README.md")
    print("linux-hardening-rollout deterministic assertions passed")


if __name__ == "__main__":
    main()
