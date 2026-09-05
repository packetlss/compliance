#!/usr/bin/env python3
"""Assert server-personas deterministic behavior."""
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


def control_by_instance(plan: dict, instance_id: str) -> dict:
    control = next(
        (
            item
            for item in plan.get("controls", [])
            if item.get("instance_id") == instance_id
        ),
        None,
    )
    if control is None:
        fail(f"assessment plan lost control instance {instance_id}")
    return control


def assert_assessment_plan_handoff(plan: dict, subject_id: str) -> None:
    if plan.get("schema") != "compliance.example/assessment-plan/v4":
        fail(f"unexpected assessment-plan schema for {subject_id}")
    if not is_digest(plan.get("id")) or not is_digest(plan.get("policy_revision")):
        fail(f"assessment plan lost plan or final policy identity for {subject_id}")
    if plan.get("subject", {}).get("id") != subject_id:
        fail(f"assessment plan lost subject identity for {subject_id}")
    policy_sources = plan.get("policy_sources", [])
    if {source.get("name") for source in policy_sources} != {
        "control-library",
        "verification-policy",
    }:
        fail(f"assessment plan lost named policy sources for {subject_id}")
    if any(not is_digest(source.get("digest")) for source in policy_sources):
        fail(f"assessment plan has invalid source identity for {subject_id}")

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


def assert_runtime(run_root: Path) -> None:
    evidence = list((run_root / "evidence").glob("*.json"))
    if len(evidence) != 6:
        fail(f"expected 6 collected evidence documents, found {len(evidence)}")
    for path in evidence:
        if load(path).get("collected_at") != FIXED_INSTANT:
            fail(f"unexpected collection instant in {path.name}")

    standard = load(run_root / "results" / "host__standard-app-01.json")
    if standard["summary"] != {"pass": 2, "fail": 0, "unknown": 0, "error": 0, "waived": 1}:
        fail(f"unexpected standard-host summary: {standard['summary']}")
    waived = [result for result in standard.get("results", []) if result.get("status") == "waived"]
    if len(waived) != 1:
        fail(f"expected one waived standard-host failure, found {len(waived)}")
    waiver = waived[0].get("waiver", {})
    if (
        waiver.get("id") != "standard-app-01-auditd-rollout"
        or waiver.get("underlying_status") != "fail"
    ):
        fail(f"unexpected waiver application: {waiver}")

    waivers_text = (run_root / "waivers.json").read_text(encoding="utf-8")
    if "standard-app-01-auditd-rollout" not in waivers_text or "risk-acceptance/RA-2026-042" not in waivers_text:
        fail("waiver catalog lost id or approval provenance")

    standard_plan = load(run_root / "plans" / "host__standard-app-01.json")
    assert_assessment_plan_handoff(standard_plan, "host/standard-app-01")
    audit_control = control_by_instance(standard_plan, "company.linux-server.audit-package")
    required_packages = {
        package["id"] for package in audit_control.get("parameters", {}).get("required", [])
    }
    if "auditd" not in required_packages:
        fail("temporary waiver rewrote assessed policy; auditd is no longer required")

    container_result = load(run_root / "results" / "host__container-app-01.json")
    summary = container_result.get("summary", {})
    if summary != {"pass": 4, "fail": 0, "unknown": 0, "error": 0, "waived": 0}:
        fail(f"container persona no longer passes its expected technical controls: {summary}")

    container_plan = load(run_root / "plans" / "host__container-app-01.json")
    assert_assessment_plan_handoff(container_plan, "host/container-app-01")
    containerd = control_by_instance(
        container_plan, "company.container-runtime.containerd-package"
    )
    if {package["id"] for package in containerd.get("parameters", {}).get("required", [])} != {
        "containerd"
    }:
        fail("container persona lost its required containerd parameter")
    forwarding = control_by_instance(
        container_plan, "benchmark.example.linux-server.ip-forwarding-disabled"
    )
    values = {
        setting["key"]: setting["value"]
        for setting in forwarding.get("parameters", {}).get("settings", [])
    }
    if values.get("net.ipv4.ip_forward") != "1":
        fail("container persona lost approved ip_forward=1 deviation")
    if not forwarding.get("derivations") or not any(
        deviation.get("id") == "DEV-LINUX-CONTAINER-001"
        for deviation in forwarding.get("deviations", [])
    ):
        fail("container persona lost overlay derivation or approved deviation provenance")

    conflict_assessment = load(run_root / "plans" / "host__persona-conflict-01.json")
    if conflict_assessment.get("resolution", {}).get("status") != "invalid":
        fail("contradictory persona assessment plan did not remain invalid")
    if not conflict_assessment.get("resolution", {}).get("errors"):
        fail("contradictory persona assessment plan lost its conflict evidence")
    if (run_root / "results" / "host__persona-conflict-01.json").exists():
        fail("contradictory persona unexpectedly produced an assessment result")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()

    assert_runtime(args.run_root.resolve())
    print("Server-personas runtime assertions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
