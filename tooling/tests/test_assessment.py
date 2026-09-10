"""Purpose-built Assessment operator projections preserve exact-domain ownership."""

import copy
import tempfile
import unittest
from pathlib import Path

from assessment_fixture import assessment_plan, evidence_plan
from tools.assessment import (
    build_explanation_view,
    build_mappings_view,
    build_run_view,
    build_status_view,
    render_explanation_view,
    render_mappings_view,
    render_run_view,
    render_status_view,
)
from tools.operation import account_operation, qualify_operation
from tools.waivers import parse_timestamp


class AssessmentOperatorViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        _, self.plan = evidence_plan(Path(self.temp.name))
        self.instant = "2026-08-23T12:00:00Z"
        self.query = "2026-08-24T12:00:01Z"
        self.account = qualify_operation(
            account_operation(self.plan, [], self.instant, [self.plan]),
            [],
            parse_timestamp(self.query),
            assessed_plans=[self.plan],
        )

    def result(self, *, status="pass", disposition=None, error=None, waiver=None):
        control = {
            "instance_id": "test.check",
            "status": status,
            "reason": "Bounded criterion reason.",
            "expected": {},
            "observed": {},
        }
        if error:
            control.update(
                reason={
                    "criterion_execution_failed": "Criterion execution failed.",
                    "criterion_decision_invalid": "Criterion decision was unusable.",
                    "criterion_reported_error": "Criterion reported an evaluation error.",
                }[error],
                evaluation_error={
                    "stage": "criterion_execution" if error == "criterion_execution_failed" else "criterion_decision",
                    "code": error,
                },
            )
        if waiver:
            control["waiver"] = waiver
        report = {
            "id": "sha256:" + "1" * 64,
            "plan_id": self.plan["id"],
            "subject_id": "host/test",
            "evaluated_at": self.instant,
            "outcome": status,
            "results": [control],
            "requirement_assessments": [],
            "requirement_baseline_assessments": [],
            "dependency_dispositions": [],
            "provenance": {"selectedEvidence": []},
        }
        if disposition:
            fact = {
                "instance_id": "test.check",
                "dependency_id": "observation",
                "disposition": disposition,
            }
            if disposition == "stale":
                fact["latest_candidates"] = [{
                    "evidence_id": "evidence:stale",
                    "evidence_digest": "sha256:" + "2" * 64,
                    "collected_at": "2026-08-20T12:00:00Z",
                }]
            if disposition == "invalid":
                fact["diagnostics"] = [{
                    "code": "evidence_schema_invalid",
                    "evidence_id": "evidence:invalid",
                    "evidence_digest": "sha256:" + "3" * 64,
                    "schema_path": "/properties/payload/type",
                    "keyword": "type",
                }]
            if disposition == "ambiguous":
                fact["candidates"] = [
                    {
                        "evidence_id": f"evidence:{name}",
                        "evidence_digest": "sha256:" + digit * 64,
                        "collected_at": self.instant,
                    }
                    for name, digit in (("a", "4"), ("b", "5"))
                ]
            report["dependency_dispositions"] = [fact]
        else:
            report["provenance"]["selectedEvidence"] = [{
                "instance_id": "test.check",
                "dependency_id": "observation",
                "evidence_id": "evidence:selected",
                "evidence_digest": "sha256:" + "6" * 64,
                "collected_at": "2026-08-23T11:00:00Z",
            }]
        return report

    def account_with_result(self, report, *, plan_available=True):
        account = copy.deepcopy(self.account)
        member = account["members"][0]
        member.update(
            state=report["outcome"],
            result_present=True,
            result_id=report["id"],
            historical_outcome=report["outcome"],
            historical_interpretation="validated" if plan_available else "unavailable",
        )
        account.update(
            accounting_complete=True,
            historical_interpretation_complete=plan_available,
            all_passed=plan_available and report["outcome"] == "pass",
        )
        return account

    def test_run_view_is_bounded_and_keeps_accounting_separate_from_outcome(self):
        view = build_run_view(self.account, [self.plan], [])

        self.assertFalse(view["summary"]["accounting_complete"])
        self.assertIsNone(view["assets"][0]["historical_outcome"])
        self.assertEqual(view["assets"][0]["expected_result_slot"]["present"], False)
        self.assertNotIn("members", view)
        self.assertNotIn("controls", view)
        self.assertIn("ASSET", render_run_view(view))

    def test_run_summary_counts_result_owned_outcomes(self):
        report = self.result(status="fail")
        account = self.account_with_result(report)
        account["members"][0].pop("historical_outcome")

        view = build_run_view(account, [self.plan], [report])

        self.assertEqual(view["summary"]["historical_outcomes"], {"fail": 1})
        self.assertEqual(view["assets"][0]["historical_outcome"], "fail")

    def test_status_preserves_missing_slot_and_group_accounting(self):
        view = build_status_view(self.account)
        grouped = build_status_view(self.account, by_group=True)

        self.assertIsNone(view["assets"][0]["historical_outcome"])
        self.assertEqual(view["whole_operation"]["missing_result_slots"], 1)
        self.assertEqual(grouped["groups"][0]["frozen_accounting"]["missing_result_slots"], 1)
        self.assertEqual(
            grouped["groups"][0]["current_qualification"]["plan_alignment"],
            {"plan_alignment_unavailable": 1},
        )
        self.assertIn("whole-operation accounting", render_status_view(view).lower())
        self.assertIn("CURRENT EVIDENCE", render_status_view(grouped))

    def test_status_retains_empty_group_from_frozen_selection_witness(self):
        account = copy.deepcopy(self.account)
        account["operation"]["request"] = {
            "all": False,
            "subjects": ["host/test"],
            "groups": ["empty-requested"],
        }
        account["operation"]["selection_witness"] = {
            "mode": "groups",
            "groups": [{"id": "empty-requested", "parents": []}],
        }

        view = build_status_view(
            account,
            group_ids=["empty-requested"],
            outcomes=["pass"],
            by_group=True,
        )

        self.assertEqual(len(view["groups"]), 1)
        group = view["groups"][0]
        self.assertEqual(group["group_id"], "empty-requested")
        self.assertEqual(group["visible_assets"], 0)
        self.assertEqual(group["frozen_accounting"]["selected_assets"], 0)
        self.assertEqual(group["current_qualification"]["assets"], 0)

    def test_dependency_free_operation_makes_no_positive_timeliness_claim(self):
        account = copy.deepcopy(self.account)
        account["members"][0]["evidence_timeliness"] = {
            "dependencies": [],
            "controls": [],
            "timely_selected_dependencies": 0,
            "stale_selected_dependencies": 0,
            "unavailable_required_dependencies": 0,
            "controls_within_recorded_age_limits": 0,
            "controls_needing_reassessment": 0,
            "controls_with_unavailable_timeliness": 0,
        }

        view = build_status_view(account)

        self.assertEqual(
            view["assets"][0]["current_qualification"]["selected_evidence"]["status"],
            "not_applicable",
        )

    def test_non_assessable_dispositions_remain_visible_in_status_and_explanation(self):
        for disposition in ("inactive", "unassigned", "no_assessable_policy"):
            with self.subTest(disposition=disposition):
                account = copy.deepcopy(self.account)
                member = account["members"][0]
                member.update(
                    accounting_disposition=disposition,
                    state=disposition,
                    result_present=False,
                    result_id=None,
                    historical_outcome=None,
                )

                asset_view = build_status_view(account)
                group_view = build_status_view(account, by_group=True)
                explanation = build_explanation_view(account, member, None, None)
                display = disposition.replace("_", " ").upper()

                self.assertIn(display, render_status_view(asset_view))
                self.assertEqual(
                    group_view["groups"][0]["frozen_accounting"][
                        "accounting_dispositions"
                    ],
                    {disposition: 1},
                )
                self.assertIn(display, render_status_view(group_view))
                self.assertEqual(
                    explanation["expected_result_slot"]["accounting_disposition"],
                    disposition,
                )
                self.assertIn(
                    disposition.replace("_", " "),
                    render_explanation_view(explanation),
                )

    def test_status_filters_do_not_change_whole_operation_accounting(self):
        report = self.result(status="fail")
        account = self.account_with_result(report)
        view = build_status_view(
            account,
            group_ids=["test-hosts"],
            outcomes=["fail"],
            plan_alignments=["plan_alignment_unavailable"],
        )

        self.assertEqual(len(view["assets"]), 1)
        self.assertTrue(view["whole_operation"]["accounting_complete"])
        self.assertTrue(view["filtered"])

    def test_all_dependency_dispositions_have_deterministic_safe_language(self):
        expected = {
            "absent": "No matching routed test.evidence/v1 observation",
            "stale": "older than the exact assessed freshness limit (86400s)",
            "invalid": "did not satisfy the exact assessment-time evidence schema",
            "ambiguous": "Multiple distinct equally latest eligible",
        }
        for disposition, text in expected.items():
            with self.subTest(disposition=disposition):
                report = self.result(status="unknown", disposition=disposition)
                account = self.account_with_result(report)
                view = build_explanation_view(account, account["members"][0], self.plan, report)
                dependency = view["checks"][0]["required_evidence"][0]
                self.assertIn(text, dependency["assessment_explanation"])
                self.assertIn(text, render_explanation_view(view))
                serialized = str(view)
                self.assertNotIn("instance_path", serialized)
                self.assertNotIn("message", serialized)

    def test_criterion_unknown_is_distinct_from_dependency_unknown(self):
        report = self.result(status="unknown")
        account = self.account_with_result(report)
        view = build_explanation_view(account, account["members"][0], self.plan, report)

        explanation = view["checks"][0]["historical_result"]["explanation"]
        self.assertIn("All required observations were selected", explanation)
        self.assertIn("criterion returned UNKNOWN", explanation)

    def test_fail_explanation_preserves_reason_and_remediation(self):
        report = self.result(status="fail")
        account = self.account_with_result(report)
        plan = copy.deepcopy(self.plan)
        plan["controls"][0]["remediation"] = "Restore the expected setting."

        view = build_explanation_view(account, account["members"][0], plan, report)
        rendered = render_explanation_view(view)

        self.assertIn("The check failed: Bounded criterion reason.", rendered)
        self.assertIn("Severity:", rendered)
        self.assertIn("Remediation:", rendered)

    def test_each_closed_error_class_has_deterministic_language(self):
        expected = {
            "criterion_execution_failed": "Criterion execution failed",
            "criterion_decision_invalid": "criterion decision was unusable",
            "criterion_reported_error": "structurally valid ERROR decision",
        }
        for code, text in expected.items():
            with self.subTest(code=code):
                report = self.result(status="error", error=code)
                account = self.account_with_result(report)
                view = build_explanation_view(account, account["members"][0], self.plan, report)
                self.assertIn(
                    text,
                    view["checks"][0]["historical_result"]["explanation"],
                )

    def test_technical_only_explanation_has_no_synthetic_objective(self):
        report = self.result()
        account = self.account_with_result(report)
        view = build_explanation_view(account, account["members"][0], self.plan, report)

        self.assertEqual(view["objectives"], [])
        self.assertEqual(view["applicable_policies"][0]["title"], "Synthetic technical policy")
        self.assertEqual(view["checks"][0]["check"]["title"], "Synthetic test check")
        self.assertEqual(
            view["checks"][0]["policy_attribution"],
            [{
                "policy_reference": "test.baseline@1",
                "group": "test-hosts",
                "assignment": "test-policy",
            }],
        )

    def test_multi_policy_explanation_retains_every_policy_to_check_path(self):
        plan = copy.deepcopy(self.plan)
        second = copy.deepcopy(plan["resolved_baselines"][0])
        second.update(
            reference="test.second@1",
            title="Second synthetic policy",
            assignment="second-policy",
        )
        plan["resolved_baselines"].append(second)
        plan["controls"][0]["provenance"].append({
            "group": "test-hosts",
            "assignment": "second-policy",
            "baseline": "test.second@1",
        })
        report = self.result()
        account = self.account_with_result(report)

        view = build_explanation_view(account, account["members"][0], plan, report)
        rendered = render_explanation_view(view)

        self.assertEqual(
            [item["reference"] for item in view["applicable_policies"]],
            ["test.baseline@1", "test.second@1"],
        )
        self.assertEqual(
            view["applicable_policies"][1]["paths"],
            [{"group": "test-hosts", "assignment": "second-policy"}],
        )
        self.assertEqual(
            view["applicable_policies"][1]["check_instance_ids"],
            ["test.check"],
        )
        self.assertEqual(len(view["checks"][0]["policy_attribution"]), 2)
        self.assertIn("Synthetic technical policy (test.baseline@1)", rendered)
        self.assertIn("Second synthetic policy (test.second@1)", rendered)
        self.assertIn("test-hosts -> second-policy", rendered)

    def test_objective_retains_bounded_realization_lineage(self):
        plan = assessment_plan(
            [{"name": "shared", "digest": "sha256:" + "7" * 64}],
            with_requirement=True,
        )
        plan["requirements"][0]["realization"]["based_on"] = {
            "realization": "test.parent-realization@1",
            "digest": "sha256:" + "9" * 64,
        }
        report = self.result()
        account = self.account_with_result(report)

        view = build_explanation_view(account, account["members"][0], plan, report)

        self.assertEqual(
            view["objectives"][0]["realization_based_on"],
            "test.parent-realization@1",
        )
        self.assertIn("Based on: test.parent-realization@1", render_explanation_view(view))

    def test_no_exact_plan_shows_only_bounded_result_owned_facts(self):
        report = self.result(status="unknown", disposition="invalid")
        account = self.account_with_result(report, plan_available=False)
        view = build_explanation_view(account, account["members"][0], None, report)

        self.assertEqual(view["interpretation"], "limited_without_exact_plan")
        self.assertNotIn("applicable_policies", view)
        self.assertNotIn("checks", view)
        self.assertNotIn("evidence_type", str(view))
        self.assertNotIn("max_age", str(view))
        self.assertNotIn("plan", view)
        self.assertNotIn("result", view)
        self.assertIn("full policy", render_explanation_view(view))

    def test_no_exact_plan_retains_result_owned_waiver_and_window_qualification(self):
        waiver = {
            "id": "test-waiver",
            "underlying_status": "fail",
            "valid_from": "2026-08-01T00:00:00Z",
            "expires_at": "2026-08-24T00:00:00Z",
            "rationale": "Bounded reason.",
            "owner": "owner",
            "approval_ref": "approval/1",
            "approved_by": "approver",
            "approved_at": "2026-07-31T00:00:00Z",
        }
        report = self.result(status="waived", waiver=waiver)
        account = qualify_operation(
            self.account_with_result(report, plan_available=False),
            [report],
            parse_timestamp(self.query),
            assessed_plans=[],
        )
        member = account["members"][0]

        view = build_explanation_view(account, member, None, report)
        rendered = render_explanation_view(view)

        self.assertEqual(
            member["recorded_waiver_qualification"]["waivers"][0]["qualification"],
            "expired",
        )
        self.assertEqual(view["raw_result_facts"][0]["waiver"]["id"], "test-waiver")
        self.assertEqual(
            view["current_qualification"]["recorded_waivers"][0]["qualification"],
            "expired",
        )
        self.assertIn("Recorded waiver test-waiver", rendered)
        self.assertIn("current qualification expired", rendered)
        self.assertIn("approval approval/1 by approver", rendered)

    def test_missing_exact_slot_is_not_promoted_to_an_outcome(self):
        view = build_explanation_view(
            self.account, self.account["members"][0], self.plan, None
        )

        self.assertIsNone(view["historical_outcome"])
        self.assertEqual(view["interpretation"], "exact_result_slot_missing")
        self.assertIn("No result was synthesized", view["explanation"])

    def test_mappings_are_exact_bounded_traceability(self):
        plan = copy.deepcopy(self.plan)
        plan["controls"][0]["external_refs"] = ["EXAMPLE:1"]
        plan["operation"]["members"][0]["policy"]["controls"][0]["external_refs"] = [
            "EXAMPLE:1"
        ]
        report = self.result(status="pass")
        account = self.account_with_result(report)
        account["members"][0]["policy"]["controls"][0]["external_refs"] = ["EXAMPLE:1"]
        view = build_mappings_view(account, [report], [plan])

        self.assertEqual(view["mappings"][0]["historical_outcome"], "pass")
        self.assertEqual(view["mappings"][0]["asset_id"], "host/test")
        self.assertIn("do not establish", view["note"])
        rendered = render_mappings_view(view)
        self.assertIn("Assessment mappings", rendered)
        self.assertNotIn("framework mappings", rendered.lower())

    def test_mapping_order_is_independent_of_external_reference_order(self):
        plan = copy.deepcopy(self.plan)
        account = copy.deepcopy(self.account)
        references = ["EXAMPLE:2", "EXAMPLE:1"]
        plan["controls"][0]["external_refs"] = references
        account["members"][0]["policy"]["controls"][0]["external_refs"] = references

        first = build_mappings_view(account, [], [plan])
        account["members"][0]["policy"]["controls"][0]["external_refs"].reverse()
        second = build_mappings_view(account, [], [plan])

        self.assertEqual(first, second)
        self.assertEqual(
            [item["external_ref"] for item in first["mappings"]],
            ["EXAMPLE:1", "EXAMPLE:2"],
        )

    def test_waiver_expiry_qualifies_without_rewriting_historical_waived(self):
        waiver = {
            "id": "test-waiver",
            "underlying_status": "fail",
            "valid_from": "2026-08-01T00:00:00Z",
            "expires_at": "2026-08-24T00:00:00Z",
            "rationale": "Bounded reason.",
            "owner": "owner",
            "approval_ref": "approval/1",
            "approved_by": "approver",
            "approved_at": "2026-07-31T00:00:00Z",
        }
        report = self.result(status="waived", waiver=waiver)
        account = self.account_with_result(report)
        account["members"][0]["recorded_waiver_qualification"] = {
            "waivers": [{
                "instance_id": "test.check",
                "waiver_id": "test-waiver",
                "valid_from": waiver["valid_from"],
                "expires_at": waiver["expires_at"],
                "qualification": "expired",
            }],
            "counts": {"within_window": 0, "expired": 1, "not_yet_in_window": 0},
        }
        view = build_explanation_view(account, account["members"][0], self.plan, report)

        self.assertEqual(view["historical_outcome"], "waived")
        historical = view["checks"][0]["historical_result"]
        self.assertEqual(historical["current_waiver_qualification"]["qualification"], "expired")
        self.assertIn("remains WAIVED", historical["explanation"])
        self.assertIn(
            "test-waiver=EXPIRED",
            render_status_view(build_status_view(account)),
        )
        grouped = build_status_view(account, by_group=True)
        self.assertEqual(
            grouped["groups"][0]["current_qualification"]["recorded_waivers"],
            {"expired": 1},
        )


if __name__ == "__main__":
    unittest.main()
