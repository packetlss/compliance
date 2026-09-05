import copy
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from contract_fixtures import fixture_root

from tools.artifact_validation import (
    ArtifactValidationError,
    validate_assessment_plan,
    validate_assessment_results,
)
from tools.assessment import load_result_reports
from tools.evaluate_plan import evaluate_plan_document
from tools.policy_sources import PolicySource
from tools.render_plan import (
    content_digest,
    load_inventory_inputs,
    render_plan,
)


class AssessmentArtifactValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = fixture_root(cls)
        fixture = Path(__file__).resolve().parent / "fixtures/macos-project"
        subject, groups, assignments = load_inventory_inputs(
            fixture / "inventory",
            fixture / "assignments",
            "workstation/tooling-macos-fixture",
            cls.root / "schemas/inventory/resource.schema.json",
        )
        cls.plan = render_plan(
            subject,
            groups,
            assignments,
            (
                PolicySource(
                    "control-library",
                    cls.root / "shared",
                ),
                PolicySource(
                    "verification-policy",
                    cls.root / "selection",
                ),
            ),
        )
        iam_subject, iam_groups, iam_assignments = load_inventory_inputs(
            cls.root / "iam/inventory",
            cls.root / "iam/assignments",
            "host/restricted-linux-01",
            cls.root / "schemas/inventory/resource.schema.json",
        )
        cls.iam_plan = render_plan(
            iam_subject,
            iam_groups,
            iam_assignments,
            (
                PolicySource(
                    "control-library",
                    cls.root / "shared",
                ),
                PolicySource(
                    "verification-policy",
                    cls.root / "selection",
                ),
                PolicySource(
                    "environment-private",
                    cls.root / "iam/policy",
                ),
            ),
        )

    @staticmethod
    def opa_result(_opa, _policies, assessment_input, _entrypoint):
        control = assessment_input["control"]
        assessment = assessment_input["assessment"]
        return {
            "control_id": control["implementation"],
            "instance_id": control["instance_id"],
            "subject_id": assessment_input["subject"]["id"],
            "plan_id": assessment["plan_id"],
            "inventory_revision": assessment["inventory_revision"],
            "assignment_revision": assessment["assignment_revision"],
            "status": "pass",
            "severity": control["severity"],
            "reason": "Synthetic unit-test pass.",
            "expected": {},
            "observed": {},
            "evidence_ids": [],
            "remediation": control["remediation"],
            "external_refs": control.get("external_refs", []),
            "alignment": control["alignment"],
            "policy_revision": assessment["policy_revision"],
        }

    def result_report(self, plan=None):
        plan = plan or self.plan
        with tempfile.TemporaryDirectory() as directory, patch(
            "tools.evaluate_plan.evaluate_control",
            side_effect=self.opa_result,
        ):
            return evaluate_plan_document(
                plan,
                Path(directory),
                (
                    (
                        PolicySource(
                            "control-library",
                            self.root / "shared",
                        ),
                        PolicySource(
                            "verification-policy",
                            self.root / "selection",
                        ),
                    )
                    if plan is self.plan
                    else (
                        PolicySource(
                            "control-library",
                            self.root / "shared",
                        ),
                        PolicySource(
                            "verification-policy",
                            self.root / "selection",
                        ),
                        PolicySource(
                            "environment-private",
                            self.root / "iam/policy",
                        ),
                    )
                ),
                evaluated_at=datetime(2026, 8, 28, 12, tzinfo=UTC),
            )

    def test_rendered_plan_and_generated_results_satisfy_contracts(self):
        validate_assessment_plan(self.plan)
        validate_assessment_results(self.result_report())

    def test_unavailable_policy_source_remains_a_schema_valid_invalid_plan(self):
        fixture = Path(__file__).resolve().parent / "fixtures/macos-project"
        subject, groups, assignments = load_inventory_inputs(
            fixture / "inventory",
            fixture / "assignments",
            "workstation/tooling-macos-fixture",
            self.root / "schemas/inventory/resource.schema.json",
        )
        plan = render_plan(
            subject,
            groups,
            assignments,
            self.root / "does-not-exist-policy",
        )

        self.assertEqual(plan["resolution"]["status"], "invalid")
        self.assertEqual(plan["policy_sources"], [])
        validate_assessment_plan(plan)

    def test_plan_rejects_unknown_envelope_field(self):
        document = copy.deepcopy(self.plan)
        document["unexpected"] = True

        with self.assertRaisesRegex(ArtifactValidationError, "unexpected"):
            validate_assessment_plan(document)

    def test_plan_rejects_malformed_control_provenance(self):
        document = copy.deepcopy(self.plan)
        del document["controls"][0]["provenance"][0]["group"]
        document.pop("id")
        document["id"] = content_digest(document)

        with self.assertRaisesRegex(
            ArtifactValidationError,
            r"/controls/0/provenance/0.*group",
        ):
            validate_assessment_plan(document)

    def test_plan_rejects_stale_content_digest(self):
        document = copy.deepcopy(self.plan)
        document["subject"]["labels"]["changed"] = "true"

        with self.assertRaisesRegex(ArtifactValidationError, "content digest"):
            validate_assessment_plan(document)

    def test_plan_rejects_inconsistent_coverage_counts(self):
        document = copy.deepcopy(self.plan)
        document["coverage"]["active_control_count"] += 1
        document.pop("id")
        document["id"] = content_digest(document)

        with self.assertRaisesRegex(
            ArtifactValidationError,
            "/coverage/active_control_count",
        ):
            validate_assessment_plan(document)

    def test_plan_rejects_derivation_that_does_not_reach_effective_criteria(self):
        document = copy.deepcopy(self.plan)
        control = next(item for item in document["controls"] if item["derivations"])
        control["derivations"][-1]["after"]["parameters"] = {"tampered": True}
        document.pop("id")
        document["id"] = content_digest(document)

        with self.assertRaisesRegex(
            ArtifactValidationError,
            r"derivations.*at least one after state",
        ):
            validate_assessment_plan(document)

    def test_results_reject_inconsistent_summary(self):
        document = self.result_report()
        document["summary"]["pass"] -= 1

        with self.assertRaisesRegex(ArtifactValidationError, "/summary"):
            validate_assessment_results(document)

    def test_results_reject_child_revision_mismatch(self):
        document = self.result_report()
        document["results"][0]["plan_id"] = "sha256:" + "0" * 64

        with self.assertRaisesRegex(
            ArtifactValidationError,
            r"/results/0/plan_id.*envelope",
        ):
            validate_assessment_results(document)

    def test_results_reject_waiver_revision_mismatch(self):
        document = self.result_report()
        document["results"][0]["waiver_revision"] = "sha256:" + "0" * 64

        with self.assertRaisesRegex(
            ArtifactValidationError,
            r"/results/0/waiver_revision.*envelope",
        ):
            validate_assessment_results(document)

    def test_results_require_child_waiver_revision_for_new_envelope(self):
        document = self.result_report()
        del document["results"][0]["waiver_revision"]

        with self.assertRaisesRegex(
            ArtifactValidationError,
            r"/results/0/waiver_revision.*required",
        ):
            validate_assessment_results(document)

    def test_results_reject_inconsistent_objective_rollup(self):
        document = self.result_report(self.iam_plan)
        document["requirement_assessments"][0]["status"] = "fail"
        document["requirement_summary"]["pass"] = 0
        document["requirement_summary"]["fail"] = 1

        with self.assertRaisesRegex(
            ArtifactValidationError,
            r"/requirement_assessments/0/status.*expected pass",
        ):
            validate_assessment_results(document)

    def test_result_loader_rejects_malformed_matching_schema_with_path(self):
        document = self.result_report()
        document["results"][0]["status"] = "success"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "malformed.json"
            path.write_text(json.dumps(document), encoding="utf-8")

            with self.assertRaisesRegex(
                ArtifactValidationError,
                r"malformed\.json.*results/0/status",
            ):
                load_result_reports(Path(directory))


if __name__ == "__main__":
    unittest.main()
