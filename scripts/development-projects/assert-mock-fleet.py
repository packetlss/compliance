#!/usr/bin/env python3
"""Assert mock-fleet deterministic runtime outcomes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

FIXED_INSTANT = "2026-09-01T00:00:00Z"


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


def assert_assessment_plan_handoff(plan: dict, subject_id: str) -> None:
    if plan.get("schema") != "compliance.example/assessment-plan/v4":
        fail(f"unexpected assessment-plan schema for {subject_id}")
    if not is_digest(plan.get("id")) or not is_digest(plan.get("policy_revision")):
        fail(f"assessment plan lost plan or final policy identity for {subject_id}")
    subject = plan.get("subject", {})
    if subject.get("id") != subject_id or not subject.get("type"):
        fail(f"assessment plan lost subject identity for {subject_id}")

    policy_sources = plan.get("policy_sources", [])
    source_names = {source.get("name") for source in policy_sources}
    if source_names != {"control-library", "verification-policy"}:
        fail(f"assessment plan lost named policy sources for {subject_id}: {source_names}")
    if any(not is_digest(source.get("digest")) for source in policy_sources):
        fail(f"assessment plan has invalid policy-source content identity for {subject_id}")

    active = plan.get("controls")
    excluded = plan.get("excluded_controls")
    if not isinstance(active, list) or not active or not isinstance(excluded, list):
        fail(f"assessment plan lost active/excluded control collections for {subject_id}")
    common_fields = {
        "instance_id",
        "implementation",
        "parameters",
        "definition_fingerprint",
        "disposition",
        "derivations",
        "deviations",
        "lineage",
        "provenance",
    }
    for control in active:
        if not common_fields.issubset(control) or control.get("disposition") != "evaluate":
            fail(f"active control lost adapter-handoff fields for {subject_id}")
        if not is_digest(control.get("definition_fingerprint")):
            fail(f"active control lost its definition fingerprint for {subject_id}")
        if not control.get("lineage") or not control.get("provenance"):
            fail(f"active control lost lineage or baseline provenance for {subject_id}")
        if not control.get("implementation_sources"):
            fail(f"active control lost implementation-source provenance for {subject_id}")
    for control in excluded:
        if not common_fields.issubset(control) or control.get("disposition") != "excluded":
            fail(f"excluded control lost adapter-handoff fields for {subject_id}")

    provenance_names = {
        locator.get("policy_source")
        for baseline in plan.get("resolved_baselines", [])
        for locator in baseline.get("policy_sources", [])
    }
    provenance_names.update(
        locator.get("policy_source")
        for control in active
        for locator in control.get("implementation_sources", [])
    )
    if not {"control-library", "verification-policy"}.issubset(provenance_names):
        fail(f"assessment plan lost named source provenance for {subject_id}")


def assert_framework_filters(run_root: Path) -> None:
    report = load(run_root / "frameworks.json")
    mappings = report.get("mappings", [])
    subjects = {mapping.get("subject_id") for mapping in mappings}
    if subjects != {
        "cloud-account/aws-111122223333",
        "cloud-account/aws-444455556666",
        "saas/acme-projects/company",
    }:
        fail(f"framework report lost cloud or SaaS subjects: {subjects}")
    if not any(mapping.get("alignment") == "tailored" for mapping in mappings):
        fail("framework alignment output lost tailored mappings")
    if not any(str(mapping.get("external_ref", "")).startswith("CSA-CCM-v4.1:") for mapping in mappings):
        fail("framework alignment output lost CSA CCM mappings")

    aws = load(run_root / "frameworks-aws.json")
    aws_subjects = {mapping.get("subject_id") for mapping in aws.get("mappings", [])}
    if aws.get("filters", {}).get("groups") != ["aws-production-accounts"]:
        fail("AWS framework report did not record its group filter")
    if aws_subjects != {
        "cloud-account/aws-111122223333",
        "cloud-account/aws-444455556666",
    }:
        fail(f"AWS group filter returned unexpected subjects: {aws_subjects}")

    saas = load(run_root / "frameworks-saas.json")
    saas_subjects = {mapping.get("subject_id") for mapping in saas.get("mappings", [])}
    if saas.get("filters", {}).get("groups") != ["production-saas-tenants"]:
        fail("SaaS framework report did not record its group filter")
    if saas_subjects != {"saas/acme-projects/company"}:
        fail(f"SaaS group filter returned unexpected subjects: {saas_subjects}")

    s3 = load(run_root / "frameworks-s3.json")
    if s3.get("filters", {}).get("external_refs") != ["AWS-Security-Hub:S3.1"]:
        fail("S3 framework report did not record its reference filter")
    if s3.get("filters", {}).get("levels") != ["technical"]:
        fail("S3 framework report did not record its technical-level filter")
    s3_mappings = s3.get("mappings", [])
    if len(s3_mappings) != 2 or any(
        mapping.get("external_ref") != "AWS-Security-Hub:S3.1"
        or mapping.get("mapping_level") != "technical"
        for mapping in s3_mappings
    ):
        fail(f"S3 reference filter returned unexpected mappings: {s3_mappings}")


def assert_runtime(run_root: Path) -> None:
    expected = {
        "cloud-account__aws-111122223333.json": (2, 3),
        "cloud-account__aws-444455556666.json": (5, 0),
        "saas__acme-projects__company.json": (3, 1),
    }
    for filename, (expected_pass, expected_fail) in expected.items():
        document = load(run_root / "results" / filename)
        summary = document["summary"]
        if summary.get("pass") != expected_pass or summary.get("fail") != expected_fail:
            fail(f"unexpected assessment summary for {filename}: {summary}")
        if document.get("evaluated_at") != FIXED_INSTANT:
            fail(f"unexpected evaluation instant for {filename}")

    evidence = list((run_root / "evidence").glob("*.json"))
    if len(evidence) != 5:
        fail(f"expected 5 collected evidence documents, found {len(evidence)}")
    for path in evidence:
        if load(path).get("collected_at") != FIXED_INSTANT:
            fail(f"unexpected collection instant in {path.name}")

    aws_plan = load(run_root / "plans" / "cloud-account__aws-111122223333.json")
    assert_assessment_plan_handoff(aws_plan, "cloud-account/aws-111122223333")
    s3_control = next(
        (
            control
            for control in aws_plan.get("controls", [])
            if control.get("instance_id") == "company.aws.s3-account-public-access-block"
        ),
        None,
    )
    if s3_control is None or set(s3_control.get("parameters", {}).values()) != {True}:
        fail("AWS assessment plan lost resolved S3 public-access parameters")

    secondary_plan = load(run_root / "plans" / "cloud-account__aws-444455556666.json")
    assert_assessment_plan_handoff(secondary_plan, "cloud-account/aws-444455556666")

    unknown = load(run_root / "unknown-results" / "saas__acme-projects__company.json")
    unknown_summary = unknown.get("summary", {})
    if unknown_summary.get("unknown") != 4 or any(
        unknown_summary.get(state, 0) for state in ("pass", "fail", "error", "waived")
    ):
        fail(f"missing SaaS evidence did not remain unknown: {unknown_summary}")

    assert_framework_filters(run_root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()

    assert_runtime(args.run_root.resolve())
    print("Mock-fleet runtime assertions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
