#!/usr/bin/env python3
"""End-to-end #150 shared-objective proof through the public CLI."""
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from tools.artifact_validation import validate_assessment_plan, validate_assessment_results

AT = "2026-09-01T00:00:00Z"
LINUX = "host/admin-bastion-01"
SAAS = "saas/administration-tenant"
OBJECTIVE = "company.administrative-access.identity-gated@1"
LINUX_REALIZATION = "company.linux.administrative-access-identity-gated@1"
SAAS_REALIZATION = "company.saas.administrative-access-identity-gated@1"


def read(path):
    return json.loads(path.read_text())


def require(value, message):
    if not value:
        raise AssertionError(message)


def document_path(directory, subject_id):
    return directory / (subject_id.replace("/", "__") + ".json")


def objective(coverage):
    rows = [row for assignment in coverage["assignments"]
            for policy in assignment["policies"] for row in policy["objectives"]]
    require(len(rows) == 1, "coverage did not retain one shared Objective")
    return rows[0]


def main(root):
    with tempfile.TemporaryDirectory(prefix="hybrid-administrative-access-") as temporary:
        work = Path(temporary)
        project = work / "project"
        shutil.copytree(root / "verification/scenarios/projects/hybrid-administrative-access", project)
        sources = []
        for name in ("control-library", "verification-policy"):
            target = work / name
            shutil.copytree(root / "policy-sources" / name / "policies", target)
            sources.append({"name": name, "path": str(target)})
        config = project / "compliance.yaml"
        config.write_text(json.dumps({
            "schema": "compliance.example/project-config/v1alpha3",
            "policySources": sources,
            "paths": {"inventory": "inventory", "assignments": "assignments",
                      "evidence": "generated/evidence", "plan": "generated/plans",
                      "results": "generated/results", "waivers": "waivers"},
        }))

        def cli(*args, historical=False, returncodes=(0,)):
            command = (["compliance", "--no-config"] if historical else
                       ["compliance", "--config", str(config)])
            result = subprocess.run([*command, *args], capture_output=True, text=True)
            require(result.returncode in returncodes,
                    f"{args}: {result.returncode}\n{result.stdout}\n{result.stderr}")
            return result.stdout

        for noun in ("config", "inventory", "policy"):
            cli(noun, "validate")

        linux_coverage = json.loads(cli("coverage", "explain", LINUX, "--format", "json"))
        saas_coverage = json.loads(cli("coverage", "explain", SAAS, "--format", "json"))
        for coverage, subject_type, realization, expected_checks in (
            (linux_coverage, "linux-host", LINUX_REALIZATION, {
                "company.linux.administrative-access.iam-domain-configured",
                "company.linux.administrative-access.operator-group-required",
                "company.linux.administrative-access.unmanaged-local-accounts-absent",
            }),
            (saas_coverage, "saas-tenant", SAAS_REALIZATION, {
                "company.saas.administrative-access.sso-enforced",
                "company.saas.administrative-access.guest-access-disabled",
            }),
        ):
            require(coverage["asset"]["asset_type"] == subject_type
                    and coverage["coverage_class"] == "result_required",
                    "coverage lost factual assessable scope")
            row = objective(coverage)
            require(row["reference"] == OBJECTIVE
                    and row["realization"] == {"reference": realization}
                    and {check["instance_id"] for check in row["checks"]} == expected_checks,
                    "coverage did not retain selected platform realization")
            require("parameters" not in row, "Objective retained parameter ownership")
        linux_technical, = [policy for assignment in linux_coverage["assignments"]
                            for policy in assignment["policies"]
                            if policy["policy_type"] == "technical"]
        require(linux_technical["reference"] == "company.linux-server-operations@1"
                and not linux_technical["objectives"]
                and [check["instance_id"] for check in linux_technical["checks"]]
                == ["company.linux-server.audit-package"],
                "Linux direct technical policy was synthesized as an Objective")
        require(all(policy["policy_type"] == "objective"
                    for assignment in saas_coverage["assignments"]
                    for policy in assignment["policies"]),
                "SaaS coverage gained Linux technical policy")
        require(not (project / "generated").exists(), "Coverage persisted assessment state")

        evidence = work / "evidence"
        subprocess.run(["python", str(root / "tooling/collectors/mock-api/collect.py"),
                        str(project / "fixtures"), str(evidence), "--collected-at", AT],
                       check=True, capture_output=True, text=True)
        plans, results = work / "plans", work / "results"
        operation = json.loads(cli("assessment", "run", LINUX, SAAS, "--at", AT,
                                   "--evidence", str(evidence), "--plan-output", str(plans),
                                   "--output", str(results), "--format", "json"))
        require(operation["summary"] == {
            "selected_assets": 2, "expected_result_slots": 2,
            "filled_result_slots": 2, "missing_result_slots": 0,
            "historical_outcomes": {"fail": 1, "pass": 1},
            "accounting_complete": True, "historical_interpretation_complete": True,
            "all_passed": False,
        }, "two-member operation did not retain complete unsuccessful accounting")

        linux_plan, saas_plan = (read(document_path(plans, subject)) for subject in (LINUX, SAAS))
        linux_report, saas_report = (read(document_path(results, subject)) for subject in (LINUX, SAAS))
        for plan, report in ((linux_plan, linux_report), (saas_plan, saas_report)):
            validate_assessment_plan(plan)
            validate_assessment_results(report)
            require(len(plan["requirements"]) == 1 and len(report["requirement_assessments"]) == 1,
                    "Objective leaked or was omitted across operation members")
        require(linux_plan["operation"]["operation_id"] == saas_plan["operation"]["operation_id"]
                and linux_plan["id"] != saas_plan["id"],
                "operation did not retain distinct member plans")
        linux_requirement, = linux_plan["requirements"]
        saas_requirement, = saas_plan["requirements"]
        require(linux_requirement["reference"] == saas_requirement["reference"] == OBJECTIVE
                and linux_requirement["realization"]["reference"] == LINUX_REALIZATION
                and saas_requirement["realization"]["reference"] == SAAS_REALIZATION,
                "same Objective did not retain exactly one platform realization per member")
        require({row["instance_id"] for row in linux_plan["controls"]} == {
            "company.linux.administrative-access.iam-domain-configured",
            "company.linux.administrative-access.operator-group-required",
            "company.linux.administrative-access.unmanaged-local-accounts-absent",
            "company.linux-server.audit-package",
        } and {row["instance_id"] for row in saas_plan["controls"]} == {
            "company.saas.administrative-access.sso-enforced",
            "company.saas.administrative-access.guest-access-disabled",
        }, "member plans leaked platform checks")
        require(linux_report["outcome"] == "pass"
                and saas_report["outcome"] == "fail"
                and linux_report["requirement_assessments"][0]["status"] == "pass"
                and saas_report["requirement_assessments"][0]["status"] == "fail",
                "Objective roll-up did not preserve member outcomes")
        saas_results = {row["instance_id"]: row for row in saas_report["results"]}
        guest = saas_results["company.saas.administrative-access.guest-access-disabled"]
        require(guest["status"] == "fail"
                and guest["expected"] == {"guest_access": {"allowed": False}}
                and guest["observed"] == {"guest_access": {"allowed": True}}
                and not saas_report["dependency_dispositions"]
                and saas_report["provenance"]["selectedEvidence"],
                "enabled guest access was not attributable negative evidence")

        saas_explanation = json.loads(cli("assessment", "explain", SAAS,
                                          "--plan", str(document_path(plans, LINUX)),
                                          "--assessed-plans", str(plans), "--results", str(results),
                                          "--at", AT, "--as-of", AT, "--format", "json", historical=True))
        require(saas_explanation["historical_outcome"] == "fail"
                and saas_explanation["objectives"][0]["historical_outcome"] == "fail"
                and next(row for row in saas_explanation["checks"]
                         if row["check"]["instance_id"] == guest["instance_id"])["historical_result"]["historical_outcome"] == "fail",
                "historical explanation did not retain the SaaS failure")
        linux_explanation = json.loads(cli("assessment", "explain", LINUX,
                                           "--plan", str(document_path(plans, LINUX)),
                                           "--assessed-plans", str(plans), "--results", str(results),
                                           "--at", AT, "--as-of", AT, "--format", "json", historical=True))
        linux_checks = {row["check"]["instance_id"]: row for row in linux_explanation["checks"]}
        linux_objective, = linux_explanation["objectives"]
        direct = linux_checks["company.linux-server.audit-package"]
        require(linux_explanation["historical_outcome"] == "pass"
                and linux_objective["reference"] == OBJECTIVE
                and linux_objective["realization"] == LINUX_REALIZATION
                and linux_objective["historical_outcome"] == "pass"
                and set(linux_objective["check_instance_ids"]) == {
                    "company.linux.administrative-access.iam-domain-configured",
                    "company.linux.administrative-access.operator-group-required",
                    "company.linux.administrative-access.unmanaged-local-accounts-absent",
                }
                and direct["historical_result"]["historical_outcome"] == "pass"
                and direct["policy_alignment"] == "unaltered"
                and direct["policy_attribution"] == [{
                    "policy_reference": "company.linux-server-operations@1",
                    "group": "linux-hosts",
                    "assignment": "linux-server-operations",
                }], "historical explanation did not keep Linux Objective and direct policy separate")

        # Removing only the applicable SaaS demonstration must retain an exact gap
        # while Linux's independent Objective and direct package Check still pass.
        (work / "verification-policy/realizations/company/company-saas-administrative-access-identity-gated.json").unlink()
        gap_plans, gap_results = work / "gap-plans", work / "gap-results"
        gap_operation = json.loads(cli("assessment", "run", LINUX, SAAS, "--at", AT,
            "--evidence", str(evidence), "--plan-output", str(gap_plans),
            "--output", str(gap_results), "--format", "json"))
        gap_plan = read(document_path(gap_plans, SAAS))
        gap_report = read(document_path(gap_results, SAAS))
        gap, = gap_plan["requirements"]
        require(gap["implementation_state"] == "no_realization" and "adoption" not in gap
                and "realization" not in gap and not gap["technical_instance_ids"],
                "zero match fabricated adoption or Check membership")
        require(gap_report["outcome"] is None and not gap_report["results"]
                and gap_report["requirement_assessments"][0]["status"] is None
                and gap_report["requirement_assessments"][0]["implementation_gap"]
                and gap_report["requirement_baseline_assessments"][0]["implementation_gap"],
                "missing realization fabricated an Assessment outcome")
        require(gap_operation["summary"]["accounting_complete"]
                and not gap_operation["summary"]["all_passed"]
                and gap_operation["summary"]["historical_outcomes"] == {"pass": 1},
                "gap erased accounting or manufactured successful demonstration")
        gap_explanation = json.loads(cli("assessment", "explain", SAAS,
            "--plan", str(document_path(gap_plans, SAAS)), "--assessed-plans", str(gap_plans),
            "--results", str(gap_results), "--at", AT, "--as-of", AT,
            "--format", "json", historical=True))
        require(gap_explanation["implementation_gap"]
                and gap_explanation["objectives"][0]["implementation_state"] == "no_realization"
                and gap_explanation["historical_outcome"] is None,
                "historical explanation confused gap with Assessment outcome")
        human = cli("assessment", "explain", SAAS,
            "--plan", str(document_path(gap_plans, SAAS)), "--assessed-plans", str(gap_plans),
            "--results", str(gap_results), "--at", AT, "--as-of", AT, historical=True)
        require("Implementation gap: True" in human, "human explanation concealed gap")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--integration-root", type=Path, required=True)
    main(parser.parse_args().integration_root)
