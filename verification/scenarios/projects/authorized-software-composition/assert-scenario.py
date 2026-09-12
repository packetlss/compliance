#!/usr/bin/env python3
"""Bounded #131 proving consumer through the public CLI and normal artifacts."""
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

        def cli(*args, historical=False):
            command = ["compliance", "--no-config"] if historical else ["compliance", "--config", str(config)]
            result = subprocess.run([*command, *args], capture_output=True, text=True)
            assert result.returncode == 0, (args, result.stdout, result.stderr)
            return result.stdout

        for noun in ("config", "inventory", "policy"):
            cli(noun, "validate")
        coverage = json.loads(cli("coverage", "explain", "host/authorized-database", "--format", "json"))
        assert coverage["coverage_class"] == "result_required"
        objective, = [objective for assignment in coverage["assignments"]
                      for policy in assignment["policies"] for objective in policy["objectives"]]
        parameter, = objective["parameters"]
        assert parameter["slot"] == "allowed_software" and parameter["effective_value"] == UNION
        projected, = parameter["composition"]["contributions"]
        assert projected == {"identity": CONTRIBUTION, "members": ["postgresql"], "applicability": [PATH]}
        assert objective["checks"][0]["parameters"]["allowed"] == UNION
        assert not (project / "generated").exists(), "Coverage persisted generated state"

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
            assert check["implementation"] == "linux.packages.only_allowed"
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
        print("Authorized software: base subset, direct additive union, causal contribution removal, "
              "unexpected ID attribution, Coverage and exact historical plan/result passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--integration-root", type=Path, required=True)
    run(parser.parse_args().integration_root.resolve())
