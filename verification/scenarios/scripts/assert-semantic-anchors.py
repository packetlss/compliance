#!/usr/bin/env python3
"""Semantic assertions for the two issue #82 conformance anchors."""
import argparse
import copy
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from tools.artifact_validation import validate_assessment_plan, validate_assessment_results

AT = "2026-09-01T00:00:00Z"


def require(value, message):
    if not value:
        raise AssertionError(message)


def documents(path):
    return {item.name: json.loads(item.read_text()) for item in path.glob("*.json")}


def statuses(report):
    return [row["status"] for row in report.get("results", [])]


class Scenario:
    def __init__(self, root, name, private_source=None):
        self.work = Path(tempfile.mkdtemp(prefix=f"{name}-"))
        self.project = self.work / "project"
        shutil.copytree(root / "verification/scenarios/projects" / name, self.project)
        sources = []
        entries = [
            ("control-library", root / "policy-sources/control-library/policies"),
            ("verification-policy", root / "policy-sources/verification-policy/policies"),
        ]
        if private_source:
            entries.append(("environment-private", private_source))
        for source_name, source in entries:
            target = self.work / source_name
            shutil.copytree(source, target)
            sources.append({"name": source_name, "path": str(target)})
        config = self.project / "compliance.yaml"
        data = {
            "schema": "compliance.example/project-config/v1alpha3",
            "policySources": sources,
            "paths": {
                "inventory": "inventory", "assignments": "assignments",
                "evidence": "generated/evidence", "plan": "generated/plans",
                "results": "generated/results", "waivers": "waivers",
            },
        }
        config.write_text(json.dumps(data))
        self.command = ["compliance", "--config", str(config)]

    def close(self):
        shutil.rmtree(self.work)

    def cli(self, *args, success=True, historical=False):
        command = ["compliance", "--no-config"] if historical else self.command
        result = subprocess.run([*command, *args], capture_output=True, text=True)
        if success:
            require(result.returncode == 0, result.stderr)
        else:
            require(result.returncode != 0, result.stdout)
        return result.stdout

    def collect(self):
        evidence = self.project / "generated/evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        for fixture in sorted((self.project / "fixtures").glob("*-api.json")):
            doc = json.loads(fixture.read_text())
            doc.update(schema="compliance.example/evidence/v1", id="synthetic:" + fixture.stem,
                       collected_at=AT)
            (evidence / fixture.name).write_text(json.dumps(doc))
        return evidence

    def assess(self, *subjects, evidence=None, tag="run", success=True, waivers=None):
        plans, results = self.work / f"{tag}-plans", self.work / f"{tag}-results"
        args = ["assessment", "run", *subjects, "--at", AT,
                "--plan-output", str(plans), "--output", str(results), "--format", "json"]
        if evidence is not None:
            args += ["--evidence", str(evidence)]
        if waivers is not None:
            args += ["--waivers", str(waivers)]
        output = self.cli(*args, success=success)
        return (json.loads(output) if output else None), plans, results


def technical(root):
    s = Scenario(root, "technical-only-packages")
    try:
        evidence = s.collect()
        happy, plans, results = s.assess("host/technical-A", evidence=evidence, tag="happy")
        require(happy["accounting_complete"] and happy["all_passed"], "technical happy operation")
        plan = json.loads((plans / "host__technical-A.json").read_text())
        report = json.loads((results / "host__technical-A.json").read_text())
        validate_assessment_plan(plan); validate_assessment_results(report)
        require(not plan.get("requirements") and not report.get("requirement_assessments"),
                "technical-only path synthesized requirement objects")
        require(statuses(report) == ["pass"], "package happy path did not pass")

        package = next(evidence.glob("*.json")); original = package.read_text()
        doc = json.loads(original); doc["payload"]["packages"] = []; package.write_text(json.dumps(doc))
        _, _, failed_results = s.assess("host/technical-A", evidence=evidence, tag="absent-package")
        require(statuses(json.loads((failed_results / "host__technical-A.json").read_text())) == ["fail"],
                "valid negative package evidence did not fail")

        package.unlink()
        _, _, missing_results = s.assess("host/technical-A", evidence=evidence, tag="missing")
        missing = json.loads((missing_results / "host__technical-A.json").read_text())
        require(statuses(missing) == ["unknown"] and not missing["results"][0].get("observed", {}).get("criterion"),
                "missing evidence did not remain pre-criterion unknown")

        package.write_text(original); doc = json.loads(original); doc["payload"]["packages"] = "invalid"
        package.write_text(json.dumps(doc))
        _, _, invalid_results = s.assess("host/technical-A", evidence=evidence, tag="invalid")
        invalid = json.loads((invalid_results / "host__technical-A.json").read_text())
        observed = invalid["results"][0]["observed"]
        require(statuses(invalid) == ["unknown"] and observed.get("evidence_validation_errors")
                and not observed.get("criterion")
                and invalid["provenance"]["selectedEvidence"] == []
                and "criterion not determined" in invalid["results"][0]["reason"],
                "schema-invalid evidence was not attributable pre-criterion unknown")

        base = json.loads(original); package.write_text(json.dumps(base))
        second = copy.deepcopy(base); second["id"] = "synthetic:distinct-copy"
        (evidence / "distinct.json").write_text(json.dumps(second))
        _, _, ambiguous_results = s.assess("host/technical-A", evidence=evidence, tag="ambiguous")
        ambiguous = json.loads((ambiguous_results / "host__technical-A.json").read_text())
        require(statuses(ambiguous) == ["unknown"] and ambiguous["results"][0]["observed"].get("evidence_selection_ambiguities"),
                "greatest-instant ambiguity was not unknown")

        second["id"] = base["id"]; (evidence / "distinct.json").write_text(json.dumps(second))
        _, copy_plans, copy_results = s.assess("host/technical-A", evidence=evidence, tag="copies")
        copies = json.loads((copy_results / "host__technical-A.json").read_text())
        require(statuses(copies) == ["pass"] and len(copies["provenance"]["evidence"]["documents"]) == 2,
                "canonical copies did not coalesce while preserving snapshot provenance")

        assignment = s.project / "assignments/base.yaml"
        assignment.write_text(assignment.read_text().replace("verification.technical-packages\n", "verification.technical-packages-with-aide\n"))
        (evidence / "distinct.json").unlink()
        overlay, overlay_plans, _ = s.assess("host/technical-A", evidence=evidence, tag="overlay")
        overlay_plan = json.loads((overlay_plans / "host__technical-A.json").read_text())
        require(not overlay["all_passed"] and overlay_plan["id"] != json.loads((copy_plans / "host__technical-A.json").read_text())["id"],
                "tailored effective policy did not differ relationally")
        require(overlay_plan["controls"][0]["parameters"]["required"] == [{"id":"auditd"},{"id":"aide"}],
                "overlay did not tailor effective package policy")

        assignment.write_text(assignment.read_text().replace(
            "    - name: verification.technical-packages-with-aide\n      revision: \"1\"",
            "    - name: verification.technical-packages\n      revision: \"1\"\n    - name: verification.technical-packages-with-aide\n      revision: \"1\""))
        s.assess("host/technical-A", evidence=evidence, tag="conflict", success=False)

        history = json.loads(s.cli("assessment", "status", "--plan", str(plans / "host__technical-A.json"),
                                   "--results", str(results), "--at", AT, "--as-of", AT,
                                   "--comparison-plan", str(plans / "host__technical-A.json"), "--format", "json",
                                   historical=True))
        require(history["all_passed"], "technical historical happy outcome changed")
    finally:
        s.close()


def iam(root, private_source):
    s = Scenario(root, "company-iam-policy-assessment", private_source)
    try:
        evidence = s.collect(); original = documents(evidence)
        happy, plans, results = s.assess("host/A", "host/B", evidence=evidence, tag="happy")
        require(happy["accounting_complete"] and happy["all_passed"], "IAM happy operation")
        reports = documents(results)
        for report in reports.values():
            validate_assessment_results(report)
            require(report["requirement_summary"]["pass"] == 1 and set(statuses(report)) == {"pass"}, "IAM roll-up")
            baseline_assessments = report["requirement_baseline_assessments"]
            require(len(baseline_assessments) == 1
                    and baseline_assessments[0]["baseline"] == "company.identity-access-objectives@1"
                    and baseline_assessments[0]["status"] == "pass",
                    "exact company requirement baseline did not pass")
        plan_a = json.loads((plans / "host__A.json").read_text()); validate_assessment_plan(plan_a)
        require(len(plan_a["operation"]["members"]) == 2, "supplied A/B scope not frozen")
        iam_control = next(row for row in plan_a["controls"] if row["implementation"] == "iam.integration.required")
        iam_ages = {d["max_age"] for d in iam_control["evidence"]}
        all_ages = {d["max_age"] for row in plan_a["controls"] for d in row["evidence"]}
        require(iam_ages == {"86400s"}, f"24h did not reach IAM dependencies: {iam_ages}")
        require(all_ages == {"86400s"}, f"24h not explicit everywhere: {all_ages}")

        def restore():
            for path in evidence.glob("*.json"): path.unlink()
            for name, doc in original.items(): (evidence / name).write_text(json.dumps(doc))
        def mutate(pattern, change=None, remove=False, tag="mutation"):
            restore(); path = next(evidence.glob(pattern)); doc = json.loads(path.read_text())
            if remove: path.unlink()
            else: change(doc); path.write_text(json.dumps(doc))
            _, _, out = s.assess("host/A", evidence=evidence, tag=tag)
            return json.loads((out / "host__A.json").read_text())
        local = mutate("host-A-linux*", lambda d:d["payload"]["packages"].update(sssd_installed=False), tag="local-fail")
        require("fail" in statuses(local) and local["requirement_summary"]["fail"] == 1, "local failure roll-up")
        negative = mutate("host-A-iam-service*", lambda d:d["payload"]["source_assertion"].update(outcome="negative"), tag="service-fail")
        require("fail" in statuses(negative) and negative["requirement_summary"]["fail"] == 1, "service failure roll-up")
        wrong = mutate("host-A-iam-service*", lambda d:d["payload"]["source_assertion"].update(subject_id="service/other"), tag="wrong-service")
        require("unknown" in statuses(wrong), "wrong service was substituted by routing")
        require("unknown" in statuses(mutate("host-A-iam-relationship*", remove=True, tag="missing-relationship")), "missing relationship")
        relationship = mutate("host-A-iam-relationship*", lambda d:d["payload"].update(integrated=False), tag="negative-relationship")
        require("fail" in statuses(relationship), "negative relationship")

        waiver_root = s.work / "waivers"; waiver_root.mkdir()
        (waiver_root / "local-failure.json").write_text(json.dumps({
            "apiVersion":"compliance.example/v1alpha1", "kind":"Waiver", "metadata":{"name":"local-failure"},
            "spec":{"subjectRef":{"id":"host/A"}, "controlRef":{"instanceId":"restricted.linux.rbac.sssd-installed"},
                    "validFrom":"2026-08-01T00:00:00Z", "expiresAt":"2026-09-02T00:00:00Z",
                    "rationale":"Synthetic fail-only waiver mutation.", "owner":"synthetic-governance",
                    "approval":{"reference":"synthetic/issue-82", "approvedBy":"synthetic-risk-owner", "approvedAt":"2026-08-01T00:00:00Z"}}}))
        restore(); local_path=next(evidence.glob("host-A-linux*")); doc=json.loads(local_path.read_text());doc["payload"]["packages"]["sssd_installed"]=False;local_path.write_text(json.dumps(doc))
        _, waiver_plans, waiver_results = s.assess("host/A", evidence=evidence, tag="waived", waivers=waiver_root)
        waived_report=json.loads((waiver_results / "host__A.json").read_text())
        waived_row=next(row for row in waived_report["results"] if row["instance_id"]=="restricted.linux.rbac.sssd-installed")
        require(waived_row["status"]=="waived" and waived_row["waiver"]["underlying_status"]=="fail", "fail-only waiver")
        waived_history=json.loads(s.cli("assessment","status","--plan",str(waiver_plans/"host__A.json"),"--results",str(waiver_results),
                                        "--at",AT,"--as-of","2026-09-03T00:00:00Z","--format","json",historical=True))
        require(waived_history["members"][0]["historical_outcome"]=="waived" and
                waived_history["qualification_summary"]["recorded_waivers.expired"] > 0, "expired waiver rewrote history")

        restore()
        for path in list(evidence.glob("host-A-iam-*.json")): path.unlink()
        for name, doc in original.items():
            if name.startswith("host-B-iam-"):
                other = copy.deepcopy(doc); other["subject"] = {"id":"host/A","type":"linux-host"}
                (evidence / name.replace("host-B", "host-A-routed-B")).write_text(json.dumps(other))
        _, _, isolated_results = s.assess("host/A", evidence=evidence, tag="beneficiary-isolation")
        require("unknown" in statuses(json.loads((isolated_results / "host__A.json").read_text())), "B evidence satisfied A")

        restore(); inventory = s.project / "inventory/host-C.yaml"
        inventory.write_text((s.project / "inventory/host-B.yaml").read_text().replace("host-b", "host-c").replace("host/B", "host/C"))
        selected_c, c_plans, _ = s.assess("host/A", "host/B", evidence=evidence, tag="nonselected-c")
        require(len(selected_c["members"]) == 2 and
                json.loads((c_plans / "host__A.json").read_text())["id"] == plan_a["id"], "nonselected C changed A/B identity")

        history_args = ["assessment", "status", "--plan", str(plans / "host__A.json"),
                        "--assessed-plans", str(plans), "--results", str(results), "--at", AT]
        current = json.loads(s.cli(*history_args, "--as-of", AT, "--comparison-plan", str(plans / "host__A.json"), "--format", "json", historical=True))
        aged = json.loads(s.cli(*history_args, "--as-of", "2026-09-03T00:00:01Z", "--comparison-plan", str(plans / "host__A.json"), "--format", "json", historical=True))
        require({row["plan_alignment"] for row in current["members"]} == {"plan_aligned"},
                "matching exact comparison plan was not aligned")
        require(all(control["within_recorded_age_limits"]
                    for row in current["members"] for control in row["evidence_timeliness"]["controls"]),
                "happy query instant did not keep all selected evidence within recorded age limits")
        require(current["all_passed"] and aged["all_passed"] and aged["qualification_summary"]["evidence_timeliness.stale_selected_dependencies"] > 0,
                "historical outcome/timeliness separation")
        frameworks = json.loads(s.cli("assessment", "frameworks", "--reference", "example-regulatory-framework:IAM-01",
                                      "--plan", str(plans / "host__A.json"), "--results", str(results), "--at", AT,
                                      "--as-of", AT, "--comparison-plan", str(plans / "host__A.json"), "--format", "json",
                                      historical=True))
        require(frameworks["mappings"] and {row["external_ref"] for row in frameworks["mappings"]} == {"example-regulatory-framework:IAM-01"}
                and {row["historical_outcome"] for row in frameworks["mappings"]} == {"pass"}
                and "no external conformity" in frameworks["claim"],
                "company IAM framework view exceeded traceability semantics")
        _, comparison_plans, _ = s.assess("host/A", evidence=evidence, tag="comparison-singleton")
        different = json.loads(s.cli(*history_args, "--as-of", AT, "--comparison-plan", str(comparison_plans / "host__A.json"), "--format", "json", historical=True))
        require(next(m for m in different["members"] if m["subject_id"] == "host/A")["plan_alignment"] == "different_plan"
                and len(different["members"]) == 2, "different operation plan alignment")

        (results / "host__B.json").unlink()
        missing = json.loads(s.cli(*history_args, "--as-of", AT, "--format", "json", historical=True))
        require(not missing["accounting_complete"] and not missing["all_passed"], "missing exact operation result")
        _, _, singleton_results = s.assess("host/B", evidence=evidence, tag="singleton")
        (results / "host__B.json").write_bytes((singleton_results / "host__B.json").read_bytes())
        require(not json.loads(s.cli(*history_args, "--as-of", AT, "--format", "json", historical=True))["accounting_complete"],
                "another operation filled the B slot")

        realization = s.work / "environment-private/realizations/restricted/company-iam-policy-assessment.json"
        realization_bytes = realization.read_bytes(); realization.unlink()
        absent, absent_plans, _ = s.assess("host/A", evidence=evidence, tag="missing-realization")
        absent_plan = json.loads((absent_plans / "host__A.json").read_text())
        require(not absent["all_passed"] and absent_plan["requirements"][0]["adoption"]["status"]=="not_implemented",
                "missing realization lost not_implemented semantics")
        realization.write_bytes(realization_bytes)

        baseline = s.work / "verification-policy/requirement-baselines/company/company-iam-baseline.json"
        baseline_doc=json.loads(baseline.read_text()); baseline_doc["spec"]["parameter_operations"]=[]; baseline.write_text(json.dumps(baseline_doc))
        unresolved_output=s.work/"unresolved-results"
        s.cli("assessment","run","host/A","--at",AT,"--evidence",str(evidence),"--output",str(unresolved_output),success=False)
        require(not (unresolved_output/"host__A.json").exists(), "unresolved parameter produced an assessment result")

        restore(); unsafe = next(evidence.glob("host-A-iam-service*")); doc=json.loads(unsafe.read_text());doc["subject"]=None;unsafe.write_text(json.dumps(doc))
        _, _, refused = s.assess("host/A", evidence=evidence, tag="refused", success=False)
        require(not (refused / "host__A.json").exists(), "unsafe routing published a result")
    finally:
        s.close()


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--integration-root", type=Path, required=True); parser.add_argument("--private-source", type=Path)
    args = parser.parse_args(); root=args.integration_root
    technical(root); iam(root, args.private_source or root / "external-sources/environment-private")
    print("IAM and technical-only semantic conformance anchors passed.")


if __name__ == "__main__": main()
