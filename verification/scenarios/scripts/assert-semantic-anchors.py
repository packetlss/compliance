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
        def write_resource(path, document):
            path.write_text(json.dumps(document))

        empty_policy = s.work / "verification-policy/baselines/technical/coverage-empty.json"
        write_resource(empty_policy, {
            "apiVersion": "compliance.example/v1", "kind": "Baseline",
            "metadata": {"id": "verification.coverage-empty", "revision": 1},
            "spec": {"title": "Intentionally empty coverage policy", "controls": []},
        })
        for name, asset_id, lifecycle, labels in (
            ("coverage-inactive", "host/coverage-inactive", "retired", {"profile": "managed-linux"}),
            ("coverage-unassigned", "host/coverage-unassigned", "active", {}),
            ("coverage-no-assessable", "host/coverage-no-assessable", "active", {"coverage": "no-assessable"}),
            ("coverage-invalid", "host/coverage-invalid", "unknown", {"profile": "managed-linux"}),
        ):
            write_resource(s.project / f"inventory/{name}.json", {
                "apiVersion": "compliance.example/v1alpha1", "kind": "Subject",
                "metadata": {"name": name, "labels": labels},
                "spec": {
                    "id": asset_id, "type": "linux-host", "lifecycle": lifecycle,
                    "source": {"name": "synthetic-inventory", "externalId": asset_id,
                               "observedAt": AT},
                },
            })
        for name, selector in (
            ("coverage-no-assessable", {"coverage": "no-assessable"}),
            ("coverage-empty", None),
        ):
            spec = {"selector": {"matchLabels": selector}} if selector else {}
            write_resource(s.project / f"inventory/{name}-group.json", {
                "apiVersion": "compliance.example/v1alpha1", "kind": "InventoryGroup",
                "metadata": {"name": name}, "spec": spec,
            })
            write_resource(s.project / f"assignments/{name}.json", {
                "apiVersion": "compliance.example/v1alpha1", "kind": "PolicyAssignment",
                "metadata": {"name": name},
                "spec": {
                    "targetRef": {"kind": "InventoryGroup", "name": name},
                    "baselineRefs": [{"name": "verification.coverage-empty", "revision": "1"}],
                },
            })

        require(not (s.project / "generated").exists(), "coverage fixture started with generated state")
        coverage = json.loads(s.cli("coverage", "list", "assets", "--format", "json"))
        require(
            {row["coverage_class"] for row in coverage["assets"]}
            == {"result_required", "inactive", "unassigned", "no_assessable_policy", "invalid_resolution"},
            "coverage asset view lost an accepted assessment-expectation class",
        )
        groups = json.loads(s.cli("coverage", "list", "groups", "--format", "json"))
        empty_group = next(row for row in groups["groups"] if row["group_id"] == "coverage-empty")
        require(empty_group["current_asset_count"] == 0
                and empty_group["direct_assignment_count"] == 1,
                "zero-effect coverage group was omitted or collapsed")
        assignments = json.loads(s.cli("coverage", "list", "assignments", "--format", "json"))
        empty_assignment = next(row for row in assignments["assignments"]
                                if row["assignment_id"] == "coverage-empty")
        no_assessable = next(row for row in assignments["assignments"]
                             if row["assignment_id"] == "coverage-no-assessable")
        require(empty_assignment["current_asset_count"] == 0
                and no_assessable["current_asset_count"] == 1
                and no_assessable["assessable_asset_count"] == 0
                and no_assessable["coverage_classes"]["no_assessable_policy"] == 1,
                "coverage assignment presence was collapsed into assessability")
        current_explanation = s.cli("coverage", "explain", "host/technical-A")
        require("Applicable policy: Linux package baseline" in current_explanation
                and "Check: Required system packages are installed" in current_explanation
                and "Required evidence: linux.packages/v1" in current_explanation
                and "Objective:" not in current_explanation,
                "technical-only current coverage was not explained directly")
        require(not (s.project / "generated").exists(),
                "coverage query persisted generated state")

        evidence = s.collect()
        happy, plans, results = s.assess("host/technical-A", evidence=evidence, tag="happy")
        require(happy["summary"]["accounting_complete"] and happy["summary"]["all_passed"], "technical happy operation")
        plan = json.loads((plans / "host__technical-A.json").read_text())
        report = json.loads((results / "host__technical-A.json").read_text())
        validate_assessment_plan(plan); validate_assessment_results(report)
        require(not plan.get("requirements") and not report.get("requirement_assessments"),
                "technical-only path synthesized requirement objects")
        require(statuses(report) == ["pass"], "package happy path did not pass")
        explanation = s.cli(
            "assessment", "explain", "host/technical-A",
            "--plan", str(plans / "host__technical-A.json"),
            "--results", str(results), "--at", AT, "--as-of", AT,
            historical=True,
        )
        for expected in (
            "Applicable policies:",
            "Linux package baseline (verification.technical-packages@1)",
            "Required system packages are installed [PASS]",
            "Purpose: Verify that the packages mandated by policy are present.",
            'Effective parameters: {"ecosystem":"linux-native","required":[{"id":"auditd"}]}',
            "Required evidence: linux.packages/v1 (max age 86400s)",
        ):
            require(expected in explanation, f"technical explanation lost {expected!r}")
        require("Objectives:" not in explanation, "technical explanation synthesized an Objective")

        package = next(evidence.glob("*.json")); original = package.read_text()
        doc = json.loads(original); doc["payload"]["packages"] = []; package.write_text(json.dumps(doc))
        _, _, failed_results = s.assess("host/technical-A", evidence=evidence, tag="absent-package")
        require(statuses(json.loads((failed_results / "host__technical-A.json").read_text())) == ["fail"],
                "valid negative package evidence did not fail")

        package.unlink()
        _, _, missing_results = s.assess("host/technical-A", evidence=evidence, tag="missing")
        missing = json.loads((missing_results / "host__technical-A.json").read_text())
        require(statuses(missing) == ["unknown"]
                and missing["dependency_dispositions"] == [{
                    "instance_id": "verification.technical-packages.required",
                    "dependency_id": "observation",
                    "disposition": "absent",
                }]
                and not missing["results"][0].get("observed", {}).get("criterion"),
                "missing evidence did not remain pre-criterion unknown")
        missing_explanation = s.cli(
            "assessment", "explain", "host/technical-A",
            "--plan", str(missing_results.parent / "missing-plans" / "host__technical-A.json"),
            "--results", str(missing_results), "--at", AT, "--as-of", AT,
            historical=True,
        )
        require("No matching routed linux.packages/v1 observation" in missing_explanation,
                "missing evidence disposition was not explainable")

        stale_doc = json.loads(original)
        stale_doc["collected_at"] = "2026-08-30T00:00:00Z"
        package.write_text(json.dumps(stale_doc))
        _, _, stale_results = s.assess("host/technical-A", evidence=evidence, tag="stale")
        stale = json.loads((stale_results / "host__technical-A.json").read_text())
        stale_disposition, = stale["dependency_dispositions"]
        require(statuses(stale) == ["unknown"]
                and stale_disposition["disposition"] == "stale"
                and stale_disposition["latest_candidates"][0]["collected_at"] == "2026-08-30T00:00:00Z",
                "stale evidence did not retain the greatest stale candidate")

        package.write_text(original); doc = json.loads(original); doc["payload"]["packages"] = "invalid"
        package.write_text(json.dumps(doc))
        _, _, invalid_results = s.assess("host/technical-A", evidence=evidence, tag="invalid")
        invalid = json.loads((invalid_results / "host__technical-A.json").read_text())
        invalid_disposition, = invalid["dependency_dispositions"]
        diagnostics = invalid_disposition.get("diagnostics", [])
        require(statuses(invalid) == ["unknown"]
                and invalid_disposition["disposition"] == "invalid"
                and diagnostics
                and set(diagnostics[0]) == {
                    "code", "evidence_id", "evidence_digest", "schema_path", "keyword",
                }
                and invalid["results"][0]["observed"] == {}
                and invalid["provenance"]["selectedEvidence"] == []
                and "criterion not determined" in invalid["results"][0]["reason"],
                "schema-invalid evidence was not attributable pre-criterion unknown")

        base = json.loads(original); package.write_text(json.dumps(base))
        second = copy.deepcopy(base); second["id"] = "synthetic:distinct-copy"
        (evidence / "distinct.json").write_text(json.dumps(second))
        _, _, ambiguous_results = s.assess("host/technical-A", evidence=evidence, tag="ambiguous")
        ambiguous = json.loads((ambiguous_results / "host__technical-A.json").read_text())
        ambiguity, = ambiguous["dependency_dispositions"]
        require(statuses(ambiguous) == ["unknown"]
                and ambiguity["disposition"] == "ambiguous"
                and len(ambiguity["candidates"]) == 2
                and ambiguous["results"][0]["observed"] == {},
                "greatest-instant ambiguity was not unknown")

        second["id"] = base["id"]; (evidence / "distinct.json").write_text(json.dumps(second))
        _, copy_plans, copy_results = s.assess("host/technical-A", evidence=evidence, tag="copies")
        copies = json.loads((copy_results / "host__technical-A.json").read_text())
        require(statuses(copies) == ["pass"] and len(copies["provenance"]["evidence"]["documents"]) == 2,
                "canonical copies did not coalesce while preserving snapshot provenance")

        policy = s.work / "control-library/controls/linux/packages-required/policy.rego"
        original_policy = policy.read_text()
        error_cases = (
            (
                original_policy + "\nthis is not valid rego\n",
                "criterion_execution_failed",
                "Criterion execution failed.",
            ),
            (
                original_policy.replace(
                    "evaluate := result.make(input, outcome)",
                    'evaluate := {"invalid": "private evaluator output"}',
                ),
                "criterion_decision_invalid",
                "Criterion decision was unusable.",
            ),
            (
                original_policy.replace('"status": "pass"', '"status": "error"'),
                "criterion_reported_error",
                "Criterion reported an evaluation error.",
            ),
        )
        for index, (source, code, reason) in enumerate(error_cases):
            policy.write_text(source)
            _, _, error_results = s.assess(
                "host/technical-A", evidence=evidence, tag=f"error-{index}"
            )
            error_report = json.loads(
                (error_results / "host__technical-A.json").read_text()
            )
            error_result, = error_report["results"]
            require(error_result["status"] == "error"
                    and error_result["evaluation_error"]["code"] == code
                    and error_result["reason"] == reason
                    and error_result["expected"] == {}
                    and error_result["observed"] == {},
                    f"criterion error classification {code} was not durable and safe")
            require("private evaluator output" not in json.dumps(error_report),
                    "raw evaluator output was retained")
        policy.write_text(original_policy)

        assignment = s.project / "assignments/base.yaml"
        assignment.write_text(assignment.read_text().replace("verification.technical-packages\n", "verification.technical-packages-with-aide\n"))
        (evidence / "distinct.json").unlink()
        overlay, overlay_plans, _ = s.assess("host/technical-A", evidence=evidence, tag="overlay")
        overlay_plan = json.loads((overlay_plans / "host__technical-A.json").read_text())
        require(not overlay["summary"]["all_passed"] and overlay_plan["id"] != json.loads((copy_plans / "host__technical-A.json").read_text())["id"],
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
        require(history["whole_operation"]["all_passed"], "technical historical happy outcome changed")
    finally:
        s.close()


def iam(root, private_source):
    s = Scenario(root, "company-iam-policy-assessment", private_source)
    try:
        evidence = s.collect(); original = documents(evidence)
        happy, plans, results = s.assess("host/A", "host/B", evidence=evidence, tag="happy")
        require(happy["summary"]["accounting_complete"] and happy["summary"]["all_passed"], "IAM happy operation")
        reports = documents(results)
        for report in reports.values():
            validate_assessment_results(report)
            require(report["requirement_assessments"][0]["status"] == "pass"
                    and set(statuses(report)) == {"pass"}, "IAM roll-up")
            baseline_assessments = report["requirement_baseline_assessments"]
            require(len(baseline_assessments) == 1
                    and baseline_assessments[0]["baseline"] == "company.identity-access-objectives@1"
                    and baseline_assessments[0]["status"] == "pass",
                    "exact company requirement baseline did not pass")
        plan_a = json.loads((plans / "host__A.json").read_text()); validate_assessment_plan(plan_a)
        require(len(plan_a["operation"]["members"]) == 2, "supplied A/B scope not frozen")
        explanation = s.cli(
            "assessment", "explain", "host/A",
            "--plan", str(plans / "host__A.json"),
            "--assessed-plans", str(plans),
            "--results", str(results), "--at", AT, "--as-of", AT,
            historical=True,
        )
        for expected in (
            "Company identity and access objectives (company.identity-access-objectives@1)",
            "Access is granted through centrally governed roles (company.iam.role-based-access@1)",
            "Interactive access to governed systems must be authorized through centrally governed role or group membership",
            "IAM service integrations satisfy policy [PASS]",
            "Purpose: Verify that required identity-service conditions and their governed relationships are supported by attributable evidence.",
        ):
            require(expected in explanation, f"IAM explanation lost {expected!r}")
        require(
            "Checks:\n  Access is granted through centrally governed roles" not in explanation,
            "IAM explanation reused Objective title as Check meaning",
        )
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
        require("fail" in statuses(local)
                and local["requirement_assessments"][0]["status"] == "fail",
                "local failure roll-up")
        negative = mutate("host-A-iam-service*", lambda d:d["payload"]["source_assertion"].update(outcome="negative"), tag="service-fail")
        require("fail" in statuses(negative)
                and negative["requirement_assessments"][0]["status"] == "fail",
                "service failure roll-up")
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
        waived_asset = waived_history["assets"][0]
        require(waived_asset["historical_outcome"]=="waived" and
                waived_asset["current_qualification"]["recorded_waivers"][0]["qualification"] == "expired",
                "expired waiver rewrote history")

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
        require(len(selected_c["assets"]) == 2 and
                json.loads((c_plans / "host__A.json").read_text())["id"] == plan_a["id"], "nonselected C changed A/B identity")

        history_args = ["assessment", "status", "--plan", str(plans / "host__A.json"),
                        "--assessed-plans", str(plans), "--results", str(results), "--at", AT]
        current = json.loads(s.cli(*history_args, "--as-of", AT, "--comparison-plan", str(plans / "host__A.json"), "--format", "json", historical=True))
        aged = json.loads(s.cli(*history_args, "--as-of", "2026-09-03T00:00:01Z", "--comparison-plan", str(plans / "host__A.json"), "--format", "json", historical=True))
        require({row["current_qualification"]["plan_alignment"] for row in current["assets"]} == {"plan_aligned"},
                "matching exact comparison plan was not aligned")
        require(all(row["current_qualification"]["selected_evidence"]["status"] ==
                    "within_recorded_age_limits" for row in current["assets"]),
                "happy query instant did not keep all selected evidence within recorded age limits")
        require(current["whole_operation"]["all_passed"] and aged["whole_operation"]["all_passed"] and
                any(row["current_qualification"]["selected_evidence"]["status"] == "reassessment_due"
                    for row in aged["assets"]),
                "historical outcome/timeliness separation")
        mappings = json.loads(s.cli("assessment", "mappings", "--reference", "example-regulatory-framework:IAM-01",
                                      "--plan", str(plans / "host__A.json"), "--results", str(results), "--at", AT,
                                      "--as-of", AT, "--comparison-plan", str(plans / "host__A.json"), "--format", "json",
                                      historical=True))
        require(mappings["mappings"] and {row["external_ref"] for row in mappings["mappings"]} == {"example-regulatory-framework:IAM-01"}
                and {row["historical_outcome"] for row in mappings["mappings"]} == {"pass"}
                and "do not establish" in mappings["note"],
                "company IAM mapping view exceeded traceability semantics")
        _, comparison_plans, _ = s.assess("host/A", evidence=evidence, tag="comparison-singleton")
        different = json.loads(s.cli(*history_args, "--as-of", AT, "--comparison-plan", str(comparison_plans / "host__A.json"), "--format", "json", historical=True))
        require(next(m for m in different["assets"] if m["asset_id"] == "host/A")["current_qualification"]["plan_alignment"] == "different_plan"
                and len(different["assets"]) == 2, "different operation plan alignment")

        (results / "host__B.json").unlink()
        missing = json.loads(s.cli(*history_args, "--as-of", AT, "--format", "json", historical=True))
        require(not missing["whole_operation"]["accounting_complete"] and not missing["whole_operation"]["all_passed"], "missing exact operation result")
        _, _, singleton_results = s.assess("host/B", evidence=evidence, tag="singleton")
        (results / "host__B.json").write_bytes((singleton_results / "host__B.json").read_bytes())
        require(not json.loads(s.cli(*history_args, "--as-of", AT, "--format", "json", historical=True))["whole_operation"]["accounting_complete"],
                "another operation filled the B slot")

        realization = s.work / "environment-private/realizations/restricted/company-iam-policy-assessment.json"
        realization_bytes = realization.read_bytes(); realization.unlink()
        absent, absent_plans, _ = s.assess("host/A", evidence=evidence, tag="missing-realization")
        absent_plan = json.loads((absent_plans / "host__A.json").read_text())
        require(not absent["summary"]["all_passed"] and absent_plan["requirements"][0]["adoption"]["status"]=="not_implemented",
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
