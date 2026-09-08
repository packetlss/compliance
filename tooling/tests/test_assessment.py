import copy
import unittest
from datetime import UTC, datetime
from pathlib import Path

from contract_fixtures import fixture_root

from tools.assessment import (
    build_explanation,
    build_framework_report,
    build_group_report,
    build_status_report,
    filter_status_report,
    render_explanation,
    render_framework_table,
    render_group_table,
    render_table,
    status_row,
    control_implementation_pin,
)
from tools.artifact_validation import result_outcome
from tools.assessment_provenance import artifact_digest, digest
from tools.control_realization import compact_plan_outcomes
from tools.policy_sources import PolicySource
from tools.render_plan import load_inventory_inputs, render_plan
from tools.waivers import load_waivers


class AssessmentStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = fixture_root(cls)
        fixture = Path(__file__).resolve().parent / "fixtures/macos-project"
        cls.subject, cls.groups, cls.assignments = load_inventory_inputs(
            fixture / "inventory",
            fixture / "assignments",
            "workstation/tooling-macos-fixture",
            cls.root / "schemas/inventory/resource.schema.json",
        )
        cls.policy_sources = (
            PolicySource(
                "control-library",
                cls.root / "shared",
            ),
            PolicySource(
                "verification-policy",
                cls.root / "selection",
            ),
        )
        cls.plan = render_plan(
            cls.subject,
            cls.groups,
            cls.assignments,
            cls.policy_sources,
        )

    def test_source_rename_changes_plan_identity_without_changing_controls(self):
        old_sources = (
            PolicySource("shared-library", self.root / "shared"),
            self.policy_sources[1],
        )
        old = render_plan(self.subject, self.groups, self.assignments, old_sources)
        self.assertNotEqual(old["id"], self.plan["id"])
        old_composition = old['provenance']['planningComposition']
        new_composition = self.plan['provenance']['planningComposition']
        self.assertNotEqual(old_composition['compositionDigest'], new_composition['compositionDigest'])
        self.assertEqual(
            [source["content"]["digest"] for source in old_composition['actual']['policySources']],
            [source["content"]["digest"] for source in new_composition['actual']['policySources']],
        )
        # Compare domain fields directly; source locators legitimately change.
        fields = ("implementation", "instance_id", "parameters", "definition_fingerprint")
        self.assertEqual(
            [{field: control[field] for field in fields} for control in old["controls"]],
            [{field: control[field] for field in fields} for control in self.plan["controls"]],
        )
        self.assertEqual(old["resolution"], self.plan["resolution"])

    def result_report(self, plan=None, plan_id=None, **summary):
        plan = plan or self.plan
        evaluated_at = "2026-08-23T13:03:45Z"
        statuses = [
            status
            for status in ("error", "fail", "unknown", "waived", "pass", "not_applicable")
            for _ in range(summary.get(status, 0))
        ]
        statuses.extend(["pass"] * (len(plan["controls"]) - len(statuses)))
        results = [{
            "instance_id": control["instance_id"],
            "status": statuses[index],
            "reason": f"Synthetic {statuses[index]} outcome.",
            "expected": {},
            "observed": {},
        } for index, control in enumerate(plan["controls"])]
        requirements, baselines = compact_plan_outcomes(plan, results)
        documents = []
        selected_evidence = []
        for control in plan["controls"]:
            for dependency in control["evidence"]:
                evidence_id = f"synthetic:{control['instance_id']}:{dependency['id']}"
                evidence_digest = digest({"id": evidence_id, "collected_at": evaluated_at})
                documents.append({"id": evidence_id, "digest": evidence_digest})
                selected_evidence.append({
                    "instance_id": control["instance_id"],
                    "dependency_id": dependency["id"],
                    "evidence_id": evidence_id,
                    "evidence_digest": evidence_digest,
                    "collected_at": evaluated_at,
                })
        documents.sort(key=lambda item: (item["id"], item["digest"]))
        selected_evidence.sort(key=lambda item: (item["instance_id"], item["dependency_id"]))
        report = {
            "schema": "compliance.example/assessment-results/v4",
            "digestAlgorithm": "compliance.example/assessment-results-digest/v1alpha1",
            "subject_id": plan["subject"]["id"],
            "plan_id": plan_id or plan["id"],
            "evaluated_at": evaluated_at,
            "provenance": {
                "schema": "compliance.example/assessment-provenance/v1alpha1",
                "evaluationComposition": copy.deepcopy(plan["provenance"]["planningComposition"]),
                "evaluator": {"name": "opa", "version": "1.18.2", "executableSha256": "sha256:" + "e" * 64},
                "evidence": {
                    "documentDigestAlgorithm": "compliance.example/evidence-document-digest/v1alpha1",
                    "setDigestAlgorithm": "compliance.example/evidence-set-digest/v1alpha1",
                    "setDigest": digest(documents),
                    "documents": documents,
                },
                "selectedEvidence": selected_evidence,
            },
            "results": results,
            "requirement_assessments": requirements,
            "requirement_baseline_assessments": baselines,
        }
        report["outcome"] = result_outcome(report)
        report["id"] = artifact_digest(report)
        return report

    def test_failing_current_result_is_visible(self):
        row = status_row(self.plan, [self.result_report(**{"pass": 5, "fail": 1})])

        self.assertEqual(row["historical_outcome"], "fail")
        self.assertEqual(row["plan_alignment"], "plan_aligned")
        self.assertTrue(row["matching_plan_result"])
        self.assertEqual(row["result_summary"]["fail"], 1)

    def test_failed_requirement_baseline_controls_subject_state(self):
        report = self.result_report(**{"fail": 1})

        row = status_row(self.plan, [report])

        self.assertEqual(row["historical_outcome"], "fail")
        self.assertEqual(row["plan_alignment"], "plan_aligned")
        self.assertEqual(row["result_summary"]["fail"], 1)

    def test_orphaned_previous_result_is_not_interpreted_as_current_policy(self):
        row = status_row(self.plan, [self.result_report(plan_id="sha256:old", **{"pass": 6})])

        self.assertEqual(row["historical_outcome"], "no_assessment")
        self.assertEqual(row["plan_alignment"], "plan_alignment_unavailable")
        self.assertFalse(row["matching_plan_result"])

    def test_unassigned_coverage_takes_precedence_over_old_results(self):
        unassigned = render_plan(
            self.subject,
            self.groups,
            [],
            self.policy_sources,
        )

        row = status_row(unassigned, [self.result_report(**{"pass": 6})])

        self.assertEqual(row["historical_outcome"], "no_assessment")
        self.assertEqual(row["plan_alignment"], "plan_alignment_unavailable")
        self.assertEqual(row["coverage"]["status"], "unassigned")

    def test_no_assessment_is_independent_of_alignment_and_coverage(self):
        row = status_row(self.plan, [])

        self.assertEqual(row["historical_outcome"], "no_assessment")
        self.assertEqual(row["plan_alignment"], "plan_alignment_unavailable")
        self.assertEqual(row["coverage"]["status"], "assigned")

    def test_overview_sorts_attention_states_first_and_renders_table(self):
        retired = copy.deepcopy(self.subject)
        retired["id"] = "workstation/retired"
        retired["status"] = "retired"
        subjects = {self.subject["id"]: self.subject, retired["id"]: retired}

        report = build_status_report(
            subjects,
            self.groups,
            self.assignments,
            self.policy_sources,
            [self.result_report(**{"pass": 5, "fail": 1})],
            generated_at=datetime(2026, 8, 23, 14, tzinfo=UTC),
        )
        table = render_table(report)

        self.assertEqual(
            [row["historical_outcome"] for row in report["subjects"]],
            ["fail", "no_assessment"],
        )
        self.assertEqual(report["summary"]["historical_outcomes"], {
            "fail": 1, "no_assessment": 1,
        })
        self.assertEqual(report["summary"]["plan_alignment"], {
            "plan_aligned": 1, "plan_alignment_unavailable": 1,
        })
        self.assertIn("Assessment overview (2 subjects)", table)
        self.assertIn("P/F/?/E/W", table)
        self.assertIn("workstation/tooling-macos-fixture", table)

    def test_filters_by_resolved_group_and_operator_state(self):
        retired = copy.deepcopy(self.subject)
        retired["id"] = "workstation/retired"
        retired["status"] = "retired"
        report = build_status_report(
            {self.subject["id"]: self.subject, retired["id"]: retired},
            self.groups,
            self.assignments,
            self.policy_sources,
            [self.result_report(**{"pass": 5, "fail": 1})],
            generated_at=datetime(2026, 8, 23, 14, tzinfo=UTC),
        )

        filtered = filter_status_report(
            report,
            ["macos-developer-machines"],
            ["fail"],
            ["plan_aligned"],
        )

        self.assertEqual(filtered["summary"]["total"], 1)
        self.assertEqual(filtered["subjects"][0]["subject_id"], self.subject["id"])
        self.assertEqual(
            filtered["filters"],
            {"groups": ["macos-developer-machines"], "outcomes": ["fail"],
             "plan_alignment": ["plan_aligned"]},
        )

        previous = status_row(self.plan, [self.result_report(plan_id="sha256:" + "0" * 64, **{"pass": 6})])
        previous_report = {
            **report,
            "subjects": [previous],
        }
        preserved = filter_status_report(
            previous_report, [], ["no_assessment"], ["plan_alignment_unavailable"]
        )
        self.assertEqual(preserved["summary"]["historical_outcomes"], {"no_assessment": 1})
        self.assertEqual(preserved["summary"]["plan_alignment"], {"plan_alignment_unavailable": 1})
        self.assertEqual(preserved["subjects"][0]["historical_outcome"], "no_assessment")

    def test_group_report_counts_subject_in_each_resolved_dag_group(self):
        report = build_status_report(
            {self.subject["id"]: self.subject},
            self.groups,
            self.assignments,
            self.policy_sources,
            [self.result_report(**{"pass": 5, "fail": 1})],
            generated_at=datetime(2026, 8, 23, 14, tzinfo=UTC),
        )

        group_report = build_group_report(
            report,
            ["company-assets", "macos-developer-machines"],
        )
        table = render_group_table(group_report)

        self.assertEqual([group["total"] for group in group_report["groups"]], [1, 1])
        self.assertEqual(group_report["groups"][0]["historical_outcomes"], {"fail": 1})
        self.assertEqual(group_report["groups"][0]["plan_alignment"], {"plan_aligned": 1})
        self.assertIn("Subjects are counted in every resolved DAG group", table)

    def test_explanation_connects_result_and_policy_provenance(self):
        report = self.result_report(**{"pass": 5, "fail": 1})
        result = next(item for item in report["results"]
                      if item["instance_id"] == "developer.macos.shellcheck-required")
        result["status"] = "fail"
        result["reason"] = "Required Homebrew formulae are missing: shellcheck"
        report["outcome"] = result_outcome(report)
        report["id"] = artifact_digest(report)

        explanation = build_explanation(self.plan, [report])
        rendered = render_explanation(explanation)

        self.assertEqual(explanation["status"]["historical_outcome"], "fail")
        self.assertEqual(explanation["status"]["plan_alignment"], "plan_aligned")
        self.assertIn("developer.macos.shellcheck-required", rendered)
        self.assertIn("Required Homebrew formulae are missing: shellcheck", rendered)
        self.assertNotIn("Install shellcheck from the approved source.", rendered)
        self.assertIn("developer-workstation-policy-assignment", rendered)
        self.assertIn("benchmark.example.macos.audit-formula-required", rendered)

        policy = self.plan["resolved_baselines"][0]
        check = self.plan["controls"][0]
        excluded = self.plan["excluded_controls"][0]
        self.assertIn(f'Asset: {self.plan["subject"]["id"]}', rendered)
        self.assertIn(f'{policy["title"]} ({policy["reference"]})', rendered)
        self.assertIn(f'Check: {check["title"]} ({check["instance_id"]})', rendered)
        self.assertIn(f'Purpose: {check["purpose"]}', rendered)
        check_implementation = control_implementation_pin(check)
        self.assertIn(
            f'implementation: {check_implementation["id"]}@'
            f'{check_implementation["version"]}',
            rendered,
        )
        self.assertIn(
            f'implementation fingerprint: {check_implementation["fingerprint"]}',
            rendered,
        )
        self.assertIn(
            f'instance definition fingerprint: {check["definition_fingerprint"]}',
            rendered,
        )
        self.assertIn("effective parameters:", rendered)
        self.assertIn("required evidence:", rendered)
        self.assertIn("freshness:", rendered)
        self.assertNotIn("Objectives:", rendered)
        self.assertIn(
            f'EXCLUDED  Check: {excluded["title"]} ({excluded["instance_id"]})',
            rendered,
        )
        self.assertIn(f'Purpose: {excluded["purpose"]}', rendered)
        excluded_implementation = control_implementation_pin(excluded)
        self.assertIn(
            f'implementation: {excluded_implementation["id"]}@'
            f'{excluded_implementation["version"]}',
            rendered,
        )
        self.assertIn(
            'implementation fingerprint: '
            f'{excluded_implementation["fingerprint"]}',
            rendered,
        )
        self.assertIn("disposition: excluded", rendered)
        self.assertIn("assessment result: none (excluded policy disposition)", rendered)

    def test_assurance_explanation_keeps_objective_and_checks_distinct(self):
        subject, groups, assignments = load_inventory_inputs(
            self.root / "iam/inventory",
            self.root / "iam/assignments",
            "host/restricted-linux-01",
            self.root / "schemas/inventory/resource.schema.json",
        )
        plan = render_plan(
            subject,
            groups,
            assignments,
            (
                PolicySource("control-library", self.root / "shared"),
                PolicySource("verification-policy", self.root / "selection"),
                PolicySource("environment-private", self.root / "iam/policy"),
            ),
        )
        rendered = render_explanation(build_explanation(plan, []))
        requirement = plan["requirements"][0]
        check = next(
            item for item in plan["controls"]
            if item["instance_id"] in requirement["technical_instance_ids"]
        )

        self.assertIn(
            f'Objective: {requirement["title"]} ({requirement["reference"]})',
            rendered,
        )
        self.assertIn(f'Meaning: {requirement["statement"]}', rendered)
        self.assertIn(f'Check: {check["title"]} ({check["instance_id"]})', rendered)
        self.assertIn(f'Purpose: {check["purpose"]}', rendered)

    def test_explanation_shows_complete_active_deviation(self):
        rendered = render_explanation(build_explanation(self.plan, []))

        self.assertIn('effective criteria: {"minimum":"26.0.0"}', rendered)
        self.assertIn(
            "lineage: benchmark.example.macos-hardening@2026.1 (defined) "
            "-> company.macos-policy@1 (tailor)",
            rendered,
        )
        self.assertIn("derivation: tailor by company.macos-policy@1", rendered)
        self.assertIn(
            'before: implementation=macos.system.minimum_version, '
            'disposition=evaluate, criteria={"minimum":"26.6.0"}',
            rendered,
        )
        self.assertIn(
            'after: implementation=macos.system.minimum_version, '
            'disposition=evaluate, criteria={"minimum":"26.0.0"}',
            rendered,
        )
        self.assertIn("alignment: tailored", rendered)
        self.assertIn("deviation DEV-MAC-001 (support-policy)", rendered)
        self.assertIn(
            "rationale: Synthetic fixture parameter adjustment.",
            rendered,
        )
        self.assertIn(
            "approval: test/approval",
            rendered,
        )
        self.assertIn("review after: 2027-01-31", rendered)

    def test_explanation_shows_applied_waiver_and_underlying_failure(self):
        project = (
            self.root
            / "linux"
        )
        subject, groups, assignments = load_inventory_inputs(
            project / "inventory",
            project / "assignments",
            "host/configuration-linux-01",
            self.root / "schemas/inventory/resource.schema.json",
        )
        plan = render_plan(
            subject,
            groups,
            assignments,
            (
                PolicySource(
                    "control-library",
                    self.root / "shared",
                ),
                PolicySource(
                    "verification-policy",
                    self.root / "selection",
                ),
            ),
        )
        waivers, _ = load_waivers(project / "waivers")
        waiver = {**waivers[0], "underlying_status": "fail"}
        report = self.result_report(plan=plan)
        report["evaluated_at"] = "2026-08-28T12:00:00Z"
        for selection in report["provenance"]["selectedEvidence"]:
            selection["collected_at"] = report["evaluated_at"]
            selection["evidence_digest"] = digest({
                "id": selection["evidence_id"],
                "collected_at": report["evaluated_at"],
            })
        documents = [
            {"id": selection["evidence_id"], "digest": selection["evidence_digest"]}
            for selection in report["provenance"]["selectedEvidence"]
        ]
        documents.sort(key=lambda item: (item["id"], item["digest"]))
        report["provenance"]["evidence"]["documents"] = documents
        report["provenance"]["evidence"]["setDigest"] = digest(documents)
        result = next(item for item in report["results"] if item["instance_id"] == "test.packages.extra")
        result.update({
            "status": "waived",
            "reason": "Required Linux packages are missing: jq",
            "waiver": waiver,
        })
        report["outcome"] = result_outcome(report)
        report["id"] = artifact_digest(report)

        rendered = render_explanation(build_explanation(plan, [report]))

        self.assertIn(
            "lineage: test.linux@1 (defined)",
            rendered,
        )

        self.assertIn("Historical outcome: ◇ WAIVED", rendered)
        self.assertIn("waiver: test-package-waiver", rendered)
        self.assertIn("underlying status: fail", rendered)
        self.assertIn("approval: test/waiver-approval", rendered)

    def test_framework_view_preserves_result_and_parent_alignment(self):
        subjects = {self.subject["id"]: self.subject}
        groups, assignments = self.groups, self.assignments
        reports = []
        for subject in subjects.values():
            plan = render_plan(
                subject,
                groups,
                assignments,
                self.policy_sources,
            )
            reports.append(self.result_report(plan=plan, **{"pass": len(plan["controls"])}))

        report = build_framework_report(
            subjects,
            groups,
            assignments,
            self.policy_sources,
            reports,
        )
        rendered = render_framework_table(report)
        log_mappings = [
            mapping for mapping in report["mappings"]
            if mapping["external_ref"] == "TEST:retention"
        ]

        self.assertEqual(len(log_mappings), 1)
        self.assertEqual({mapping["historical_outcome"] for mapping in log_mappings}, {"pass"})
        self.assertEqual({mapping["plan_alignment"] for mapping in log_mappings}, {"plan_aligned"})
        self.assertEqual({mapping["policy_alignment"] for mapping in log_mappings}, {"tailored"})
        self.assertIn("Technical results do not by themselves", rendered)
        self.assertIn("TEST:retention", rendered)

    def test_framework_view_does_not_invent_outcome_for_new_plan_mapping(self):
        previous = {
            "schema": "compliance.example/assessment-results/v4",
            "subject_id": self.subject["id"],
            "plan_id": "sha256:previous",
            "evaluated_at": "2026-08-22T13:03:45Z",
            "results": [],
            "requirement_assessments": [],
        }

        report = build_framework_report(
            {self.subject["id"]: self.subject},
            self.groups,
            self.assignments,
            self.policy_sources,
            [previous],
            outcomes=["no_assessment"],
            plan_alignments=["plan_alignment_unavailable"],
        )

        self.assertTrue(report["mappings"])
        self.assertEqual(report["filters"]["outcomes"], ["no_assessment"])
        self.assertEqual(report["filters"]["plan_alignment"], ["plan_alignment_unavailable"])
        self.assertEqual(
            {mapping["historical_outcome"] for mapping in report["mappings"]},
            {"no_assessment"},
        )
        self.assertEqual(
            {mapping["plan_alignment"] for mapping in report["mappings"]},
            {"plan_alignment_unavailable"},
        )
