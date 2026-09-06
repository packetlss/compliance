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
)
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
        self.assertNotEqual(old["policy_revision"], self.plan["policy_revision"])
        self.assertEqual(
            [source["digest"] for source in old["policy_sources"]],
            [source["digest"] for source in self.plan["policy_sources"]],
        )
        # Compare domain fields directly; source locators legitimately change.
        fields = ("implementation", "instance_id", "parameters", "definition_fingerprint")
        self.assertEqual(
            [{field: control[field] for field in fields} for control in old["controls"]],
            [{field: control[field] for field in fields} for control in self.plan["controls"]],
        )
        self.assertEqual(old["coverage"], self.plan["coverage"])
        self.assertEqual(old["resolution"], self.plan["resolution"])

    def result_report(self, plan_id=None, **summary):
        return {
            "schema": "compliance.example/assessment-results/v4",
            "subject_id": self.subject["id"],
            "plan_id": plan_id or self.plan["id"],
            "evaluated_at": "2026-08-23T13:03:45Z",
            "summary": {
                status: summary.get(status, 0)
                for status in ("pass", "fail", "unknown", "not_applicable", "error", "waived")
            },
        }

    def test_failing_current_result_is_visible(self):
        row = status_row(self.plan, [self.result_report(**{"pass": 5, "fail": 1})])

        self.assertEqual(row["state"], "fail")
        self.assertTrue(row["matching_plan_result"])
        self.assertEqual(row["result_summary"]["fail"], 1)

    def test_failed_requirement_baseline_controls_subject_state(self):
        report = self.result_report(**{"pass": 4})
        report["requirement_summary"] = {"fail": 1}
        report["requirement_baseline_summary"] = {"fail": 1}

        row = status_row(self.plan, [report])

        self.assertEqual(row["state"], "fail")
        self.assertEqual(row["requirement_summary"]["fail"], 1)

    def test_result_for_old_plan_is_outdated(self):
        row = status_row(self.plan, [self.result_report(plan_id="sha256:old", **{"pass": 6})])

        self.assertEqual(row["state"], "different_plan")
        self.assertFalse(row["matching_plan_result"])

    def test_unassigned_coverage_takes_precedence_over_old_results(self):
        unassigned = render_plan(
            self.subject,
            self.groups,
            [],
            self.policy_sources,
        )

        row = status_row(unassigned, [self.result_report(**{"pass": 6})])

        self.assertEqual(row["state"], "unassigned")

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

        self.assertEqual([row["state"] for row in report["subjects"]], ["fail", "inactive"])
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
        )

        self.assertEqual(filtered["summary"]["total"], 1)
        self.assertEqual(filtered["subjects"][0]["subject_id"], self.subject["id"])
        self.assertEqual(
            filtered["filters"],
            {"groups": ["macos-developer-machines"], "states": ["fail"]},
        )

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
        self.assertEqual(group_report["groups"][0]["states"], {"fail": 1})
        self.assertIn("Subjects are counted in every resolved DAG group", table)

    def test_explanation_connects_result_and_policy_provenance(self):
        report = self.result_report(**{"pass": 5, "fail": 1})
        report["results"] = [{
            "instance_id": "developer.macos.shellcheck-required",
            "status": "fail",
            "reason": "Required Homebrew formulae are missing: shellcheck",
            "severity": "medium",
            "remediation": "Install shellcheck from the approved source.",
        }]

        explanation = build_explanation(self.plan, [report])
        rendered = render_explanation(explanation)

        self.assertEqual(explanation["status"]["state"], "fail")
        self.assertIn("developer.macos.shellcheck-required", rendered)
        self.assertIn("Required Homebrew formulae are missing: shellcheck", rendered)
        self.assertIn("remediation: Install shellcheck from the approved source.", rendered)
        self.assertIn("developer-workstation-policy-assignment", rendered)
        self.assertIn("benchmark.example.macos.audit-formula-required", rendered)

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
        waivers, revision = load_waivers(project / "waivers")
        waiver = {**waivers[0], "underlying_status": "fail"}
        report = {
            "schema": "compliance.example/assessment-results/v4",
            "subject_id": subject["id"],
            "plan_id": plan["id"],
            "evaluated_at": "2026-08-28T12:00:00Z",
            "waiver_revision": revision,
            "summary": {
                "pass": 2,
                "fail": 0,
                "unknown": 0,
                "not_applicable": 0,
                "error": 0,
                "waived": 1,
            },
            "results": [{
                "instance_id": "test.packages.extra",
                "status": "waived",
                "reason": "Required Linux packages are missing: jq",
                "severity": "medium",
                "remediation": "Install jq.",
                "waiver": waiver,
            }],
        }

        rendered = render_explanation(build_explanation(plan, [report]))

        self.assertIn(
            "lineage: test.linux@1 (defined)",
            rendered,
        )

        self.assertIn("State: ◇ WAIVED", rendered)
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
            reports.append({
                "schema": "compliance.example/assessment-results/v4",
                "subject_id": subject["id"],
                "plan_id": plan["id"],
                "evaluated_at": "2026-08-23T13:03:45Z",
                "results": [
                    {"instance_id": control["instance_id"], "status": "pass"}
                    for control in plan["controls"]
                ],
            })

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
        self.assertEqual({mapping["status"] for mapping in log_mappings}, {"pass"})
        self.assertEqual({mapping["alignment"] for mapping in log_mappings}, {"tailored"})
        self.assertIn("Technical results do not by themselves", rendered)
        self.assertIn("TEST:retention", rendered)
