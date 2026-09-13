#!/usr/bin/env python3
"""Bounded #131/#149 proof through the public CLI and normal artifacts."""
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from tools.artifact_validation import validate_assessment_plan, validate_assessment_results

AT = "2026-09-01T00:00:00Z"
BASE = ["auditd", "curl"]
UNION = ["auditd", "curl", "postgresql"]
CONTRIBUTION = {
    "baseline": "company.database-software@1", "id": "database-packages",
    "requirement": "company.authorized-software", "slot": "allowed_software",
}
PATH = {
    "assignment": "database-software", "group": "database",
    "baseline": "company.database-software@1",
}
APPLICATION = "host/authorized-base"
DATABASE = "host/authorized-database"


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value))


def run(root):
    with tempfile.TemporaryDirectory(prefix="authorized-software-") as temporary:
        work = Path(temporary)
        project = work / "project"
        shutil.copytree(root / "verification/scenarios/projects/authorized-software-composition", project)
        sources = []
        for name in ("control-library", "verification-policy"):
            target = work / name
            shutil.copytree(root / "policy-sources" / name / "policies", target)
            sources.append({"name": name, "path": str(target)})
        config = project / "compliance.yaml"
        write(config, {
            "schema": "compliance.example/project-config/v1alpha3", "policySources": sources,
            "paths": {"inventory": "inventory", "assignments": "assignments",
                      "evidence": "generated/evidence", "plan": "generated/plans",
                      "results": "generated/results", "waivers": "waivers"},
        })

        def cli(*args, historical=False, config_path=config, returncodes=(0,)):
            command = (['compliance', '--no-config'] if historical else
                       ['compliance', '--config', str(config_path)])
            result = subprocess.run([*command, *args], capture_output=True, text=True)
            assert result.returncode in returncodes, (
                args, result.returncode, result.stdout, result.stderr,
            )
            return result.stdout

        def member(plan, subject_id):
            row, = [row for row in plan["operation"]["members"]
                    if row["subject_id"] == subject_id]
            return row

        def plan_path(directory, subject_id):
            return directory / (subject_id.replace("/", "__") + ".json")

        for noun in ("config", "inventory", "policy"):
            cli(noun, "validate")
        coverage = json.loads(cli("coverage", "explain", DATABASE, "--format", "json"))
        assert coverage["coverage_class"] == "result_required"
        objective, = [objective for assignment in coverage["assignments"]
                      for policy in assignment["policies"] for objective in policy["objectives"]]
        parameter, = objective["parameters"]
        assert parameter["slot"] == "allowed_software" and parameter["effective_value"] == UNION
        projected, = parameter["composition"]["contributions"]
        assert projected == {"identity": CONTRIBUTION, "members": ["postgresql"], "applicability": [PATH]}
        assert objective["checks"][0]["parameters"]["allowed"] == UNION
        assert not (project / "generated").exists(), "Coverage persisted generated state"
        application_coverage = json.loads(cli("coverage", "explain", APPLICATION, "--format", "json"))

        evidence = work / "evidence"
        evidence.mkdir()
        # Use the existing collector, fixing time for deterministic eligibility.
        subprocess.run(["python", str(root / "tooling/collectors/mock-api/collect.py"),
                        str(project / "fixtures"), str(evidence), "--collected-at", AT], check=True,
                       capture_output=True, text=True)

        def assess(name, tag, expected_status, allowed, unexpected):
            plans, results = work / (tag + "-plans"), work / (tag + "-results")
            operation = json.loads(cli(
                "assessment", "run", "host/authorized-" + name, "--at", AT,
                "--evidence", str(evidence), "--plan-output", str(plans),
                "--output", str(results), "--format", "json",
            ))
            assert operation["summary"]["accounting_complete"]
            assert operation["summary"]["all_passed"] == (expected_status == "pass")
            filename = "host__authorized-" + name + ".json"
            plan_path, result_path = plans / filename, results / filename
            plan, report = read(plan_path), read(result_path)
            validate_assessment_plan(plan)
            validate_assessment_results(report)
            check, = plan["controls"]
            assert check["implementation"] == "linux.packages.only-allowed"
            assert check["parameters"] == {"ecosystem": "linux-native", "allowed": allowed}
            assert check["evidence"] == [{"id": "observation", "type": "linux.packages/v1", "max_age": "86400s"}]
            requirement, = plan["requirements"]
            state = requirement["parameter_facts"]["states"]["allowed_software"]
            assert state["value"] == allowed
            assert state["composition"]["kind"] == "additive-set"
            assert state["composition"]["base_value"] == BASE
            result, = report["results"]
            assert result["status"] == expected_status
            assert result["expected"] == {"ecosystem": "linux-native", "allowed": allowed}
            assert result["observed"]["unexpected"] == unexpected
            assert report["requirement_assessments"][0]["status"] == expected_status
            # The ordinary historical CLI validates the exact retained plan/result relation.
            explanation = cli(
                "assessment", "explain", "host/authorized-" + name, "--plan", str(plan_path),
                "--results", str(results), "--at", AT, "--as-of", AT,
                "--format", "json", historical=True,
            )
            return plan, report, explanation, plan_path, results

        def assess_operation(subjects, tag):
            plans, results = work / (tag + "-plans"), work / (tag + "-results")
            operation = json.loads(cli(
                "assessment", "run", *subjects, "--at", AT, "--evidence", str(evidence),
                "--plan-output", str(plans), "--output", str(results), "--format", "json",
            ))
            plan_documents = {subject_id: read(plan_path(plans, subject_id)) for subject_id in subjects}
            report_documents = {subject_id: read(plan_path(results, subject_id)) for subject_id in subjects}
            for plan in plan_documents.values():
                validate_assessment_plan(plan)
            for report in report_documents.values():
                validate_assessment_results(report)
            return operation, plan_documents, report_documents, plans, results

        base, base_result, _, _, _ = assess("base", "base", "pass", BASE, [])
        assert base_result["results"][0]["observed"]["installed"] == ["auditd"]
        assert base["requirements"][0]["parameter_facts"]["states"]["allowed_software"]["composition"]["contributions"] == []
        happy, happy_result, historical, happy_path, happy_results = assess("database", "contribution", "pass", UNION, [])
        assert happy_result["results"][0]["observed"]["installed"] == ["auditd", "postgresql"]
        facts = happy["requirements"][0]["parameter_facts"]
        composition = facts["states"]["allowed_software"]["composition"]
        contribution, = composition["contributions"]
        assert contribution["identity"] == CONTRIBUTION
        assert contribution["applicability"] == [PATH]
        assert contribution["members"] == ["postgresql"]
        assert contribution["owner"]["document"]["spec"]["parameter_contributions"][0]["target"] == {
            "requirement": "company.authorized-software", "slot": "allowed_software",
        }
        assert composition["member_origins"][-1] == {
            "member": "postgresql", "origins": [{"kind": "contribution", "identity": CONTRIBUTION}],
        }
        feature, = [row for row in happy["resolved_requirement_baselines"]
                    if row["reference"] == "company.database-software@1"]
        assert feature["requirements"] == []

        # #149: retain one exact two-member operation before current governed
        # inventory changes.  These plans/results are the historical assertion.
        historical_operation, historical_plans, historical_reports, historical_plans_path, historical_results = assess_operation(
            (APPLICATION, DATABASE), "historical-two-member"
        )
        assert historical_operation["summary"] == {
            "selected_assets": 2, "expected_result_slots": 2,
            "filled_result_slots": 2, "missing_result_slots": 0,
            "historical_outcomes": {"pass": 2},
            "accounting_complete": True, "historical_interpretation_complete": True,
            "all_passed": True,
        }
        old_application, old_database = historical_plans[APPLICATION], historical_plans[DATABASE]
        old_operation_id = old_application["operation"]["operation_id"]
        assert old_database["operation"]["operation_id"] == old_operation_id
        assert {report["outcome"] for report in historical_reports.values()} == {"pass"}
        assert old_application["controls"][0]["parameters"]["allowed"] == BASE
        assert old_database["controls"][0]["parameters"]["allowed"] == UNION
        old_database_contribution, = old_database["requirements"][0]["parameter_facts"]["states"]["allowed_software"]["composition"]["contributions"]
        assert old_database_contribution["identity"] == CONTRIBUTION
        assert old_database_contribution["members"] == ["postgresql"]
        assert old_database_contribution["applicability"] == [PATH]
        assert old_application["requirements"][0]["parameter_facts"]["states"]["allowed_software"]["composition"]["contributions"] == []

        # Make a separate current-input view.  It changes only the supplied
        # database classification, never the committed policy, evidence, or old pair.
        current_project = work / "current-project"
        shutil.copytree(project, current_project)
        current_config = current_project / "compliance.yaml"
        write(current_config, {
            "schema": "compliance.example/project-config/v1alpha3", "policySources": sources,
            "paths": {"inventory": "inventory", "assignments": "assignments",
                      "evidence": "generated/evidence", "plan": "generated/plans",
                      "results": "generated/results", "waivers": "waivers"},
        })
        changed_inventory = current_project / "inventory/database.json"
        changed_database = read(changed_inventory)
        del changed_database["metadata"]["labels"]["feature.database"]
        write(changed_inventory, changed_database)

        current_inventory = json.loads(cli(
            "inventory", "explain", DATABASE, "--format", "json", config_path=current_config,
        ))
        assert current_inventory["asset"]["labels"] == {"profile": "managed-linux"}
        assert {group["id"] for group in current_inventory["resolved_groups"]} == {"managed-linux"}
        current_database_coverage = json.loads(cli(
            "coverage", "explain", DATABASE, "--format", "json", config_path=current_config,
        ))
        assert {assignment["assignment_id"] for assignment in current_database_coverage["assignments"]} == {
            "managed-linux-software",
        }
        current_objective, = [objective for assignment in current_database_coverage["assignments"]
                              for policy in assignment["policies"] for objective in policy["objectives"]]
        current_parameter, = current_objective["parameters"]
        assert current_parameter["effective_value"] == BASE
        assert current_parameter["composition"]["contributions"] == []
        assert current_objective["checks"][0]["parameters"]["allowed"] == BASE
        assert json.loads(cli(
            "coverage", "explain", APPLICATION, "--format", "json", config_path=current_config,
        )) == application_coverage

        comparison_plans_path = work / "current-comparison-plans"
        cli("plan", "render", APPLICATION, DATABASE, "--output", str(comparison_plans_path),
            config_path=current_config)
        comparison_application = read(plan_path(comparison_plans_path, APPLICATION))
        comparison_database = read(plan_path(comparison_plans_path, DATABASE))
        validate_assessment_plan(comparison_application)
        validate_assessment_plan(comparison_database)
        comparison_operation_id = comparison_application["operation"]["operation_id"]
        assert comparison_database["operation"]["operation_id"] == comparison_operation_id
        assert comparison_operation_id != old_operation_id
        assert member(old_application, APPLICATION)["member_plan_digest"] == member(
            comparison_application, APPLICATION
        )["member_plan_digest"]
        assert member(old_database, DATABASE)["member_plan_digest"] != member(
            comparison_database, DATABASE
        )["member_plan_digest"]
        assert old_application["id"] != comparison_application["id"]
        assert old_database["id"] != comparison_database["id"]

        # The old denominator/outcomes remain exact.  The new operation is only a
        # comparison anchor, so different_plan never creates a current outcome.
        historical_status = json.loads(cli(
            "assessment", "status", "--plan", str(plan_path(historical_plans_path, APPLICATION)),
            "--assessed-plans", str(historical_plans_path), "--results", str(historical_results),
            "--at", AT, "--as-of", AT,
            "--comparison-plan", str(plan_path(comparison_plans_path, APPLICATION)),
            "--format", "json", historical=True,
        ))
        assert historical_status["operation"]["operation_id"] == old_operation_id
        assert historical_status["whole_operation"]["accounting_complete"]
        assert historical_status["whole_operation"]["all_passed"]
        assert len(historical_status["assets"]) == 2
        assert {row["historical_outcome"] for row in historical_status["assets"]} == {"pass"}
        assert {row["current_qualification"]["plan_alignment"]
                for row in historical_status["assets"]} == {"different_plan"}
        historical_database = json.loads(cli(
            "assessment", "explain", DATABASE,
            "--plan", str(plan_path(historical_plans_path, APPLICATION)),
            "--assessed-plans", str(historical_plans_path), "--results", str(historical_results),
            "--at", AT, "--as-of", AT,
            "--comparison-plan", str(plan_path(comparison_plans_path, APPLICATION)),
            "--format", "json", historical=True,
        ))
        assert historical_database["historical_outcome"] == "pass"
        assert historical_database["current_qualification"]["plan_alignment"] == "different_plan"
        assert historical_database["checks"][0]["effective_parameters"]["allowed"] == UNION
        database_policy, = [policy for policy in historical_database["applicable_policies"]
                            if policy["reference"] == "company.database-software@1"]
        assert database_policy["paths"] == [{"group": "database", "assignment": "database-software"}]

        application_diff = json.loads(cli(
            "policy", "diff", str(plan_path(historical_plans_path, APPLICATION)),
            str(plan_path(comparison_plans_path, APPLICATION)), "--format", "json",
            historical=True,
        ))
        assert application_diff["comparison"]["status"] == "complete"
        assert not application_diff["summary"]["changed"]
        assert application_diff["context"]["changed_fields"] == ["plan_id", "operation_id"]
        database_diff = json.loads(cli(
            "policy", "diff", str(plan_path(historical_plans_path, DATABASE)),
            str(plan_path(comparison_plans_path, DATABASE)), "--format", "json",
            historical=True, returncodes=(1,),
        ))
        assert database_diff["comparison"]["status"] == "complete"
        assert database_diff["summary"]["changed"]
        assert database_diff["context"]["changed_fields"] == [
            "plan_id", "member_plan_digest", "operation_id",
        ]
        assert any(change["kind"] == "assignment" and change["identity"] == "database-software"
                   and change["change"] == "removed" for change in database_diff["scope_changes"])
        assert database_diff["summary"]["requirements"]["modified"] == 1
        assert database_diff["summary"]["controls"]["modified"] == 1

        assignment = project / "assignments/database.json"
        assignment_bytes = assignment.read_bytes()
        evidence_bytes = {path.name: path.read_bytes() for path in evidence.glob("*.json")}
        assignment.unlink()
        without, without_result, _, _, _ = assess("database", "without-contribution", "fail", BASE, ["postgresql"])
        assert {path.name: path.read_bytes() for path in evidence.glob("*.json")} == evidence_bytes
        assert without_result["results"][0]["reason"] == "Unexpected Linux packages are installed: postgresql"
        assert without["requirements"][0]["parameter_facts"]["states"]["allowed_software"]["composition"]["contributions"] == []
        assignment.write_bytes(assignment_bytes)

        package = next(path for path in evidence.glob("*.json")
                       if read(path)["subject"]["id"] == "host/authorized-database")
        doc = read(package)
        doc["payload"]["packages"].insert(0, {"id": "telnet", "version": "1.0"})
        write(package, doc)
        _, unexpected_result, _, _, _ = assess("database", "unexpected", "fail", UNION, ["telnet"])
        assert unexpected_result["results"][0]["reason"] == "Unexpected Linux packages are installed: telnet"

        # No mutable policy, inventory or evidence is needed to explain the happy pair.
        shutil.rmtree(work / "control-library")
        shutil.rmtree(work / "verification-policy")
        shutil.rmtree(project)
        shutil.rmtree(evidence)
        retained = cli("assessment", "explain", "host/authorized-database", "--plan", str(happy_path),
                       "--results", str(happy_results), "--at", AT, "--as-of", AT,
                       "--format", "json", historical=True)
        assert retained == historical
        print("Authorized software: additive contribution, current inventory/Coverage change, "
              "operation-bound identity, immutable two-member history, and stored-plan policy diff passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--integration-root", type=Path, required=True)
    run(parser.parse_args().integration_root.resolve())
