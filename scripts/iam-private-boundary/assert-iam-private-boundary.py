#!/usr/bin/env python3
"""Assert preserved IAM assessment behavior and private-source provenance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

FIXED_INSTANT = "2026-09-01T00:00:00Z"
PRIVATE_POLICY_DIGEST = (
    "sha256:f94aea8ac3259219c8a745a9bcd057f7ccdb80c97bed36a923f4f2522e3644aa"
)
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


def assert_plan(plan: dict) -> None:
    if plan.get("schema") != "compliance.example/assessment-plan/v1":
        fail("IAM plan changed assessment schema")
    if not is_digest(plan.get("id")) or not is_digest(plan.get("policy_revision")):
        fail("IAM plan lost plan or final policy identity")
    if plan.get("subject", {}).get("id") != "host/restricted-linux-01":
        fail("IAM plan lost the restricted synthetic subject")
    sources = plan.get("policy_sources", [])
    if [source.get("name") for source in sources] != SOURCE_NAMES:
        fail(f"IAM plan lost canonical named-source provenance: {sources}")
    source_digests = {source.get("name"): source.get("digest") for source in sources}
    if source_digests.get("environment-private") != PRIVATE_POLICY_DIGEST:
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
    required_handoff = {
        "instance_id",
        "implementation",
        "parameters",
        "definition_fingerprint",
        "disposition",
        "derivations",
        "deviations",
        "lineage",
        "provenance",
        "implementation_sources",
    }
    for control in controls:
        if not required_handoff.issubset(control):
            fail(f"control lost external-adapter handoff fields: {control}")
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
    if result.get("schema") != "compliance.example/assessment-results/v1":
        fail("IAM result changed assessment schema")
    if result.get("evaluated_at") != FIXED_INSTANT:
        fail(f"IAM result changed deterministic instant: {result.get('evaluated_at')}")
    summary = result.get("summary", {})
    if summary.get("pass") != 3 or summary.get("fail") != 1:
        fail(f"IAM technical pass/fail behavior changed: {summary}")
    if any(summary.get(state, 0) for state in ("unknown", "error", "waived")):
        fail(f"IAM result gained unexpected technical states: {summary}")
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
    if requirements[0].get("adoption", {}).get("status") != "implemented":
        fail("IAM objective lost its authored adoption annotation")
    if len(baselines) != 1 or baselines[0].get("status") != "fail":
        fail(f"IAM top requirement baseline no longer fails: {baselines}")


def assert_frameworks(frameworks: dict) -> None:
    mappings = frameworks.get("mappings", [])
    matches = [
        mapping
        for mapping in mappings
        if mapping.get("external_ref") == "example-regulatory-framework:IAM-01"
    ]
    if len(matches) != 1 or matches[0].get("status") != "fail":
        fail(f"IAM objective framework mapping changed: {matches}")


def assert_rollup(rollup: dict) -> None:
    if rollup.get("requirement_assessment", {}).get("status") != "fail":
        fail("direct IAM requirement roll-up no longer fails")
    if rollup.get("baseline_assessment", {}).get("status") != "fail":
        fail("direct IAM baseline roll-up no longer fails")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assembly-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    assembly_root = args.assembly_root.resolve()
    run_root = args.run_root.resolve()

    assert_config(load(run_root / "config.json"), assembly_root)
    assert_plan(load(run_root / "plans/host__restricted-linux-01.json"))
    assert_result(load(run_root / "results/host__restricted-linux-01.json"))
    assert_frameworks(load(run_root / "frameworks.json"))
    assert_rollup(load(run_root / "direct-rollup.json"))
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
