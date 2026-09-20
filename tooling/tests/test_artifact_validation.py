import copy
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from assessment_fixture import assessment_plan, refresh_operation
from contract_fixtures import fixture_root

from tools.artifact_validation import (
    ArtifactValidationError,
    result_outcome,
    validate_assessment_plan,
    validate_assessment_results,
)
from tools.assessment_provenance import artifact_digest, validate_result_against_plan
from tools.assessment import load_result_reports
from tools.evaluate_plan import evaluate_plan_document
from tools.policy_sources import PolicySource
from tools.render_plan import (
    content_digest,
    load_inventory_inputs,
    render_plan,
)


class AssessmentArtifactValidationTests(unittest.TestCase):
    def test_public_semantic_identifiers_are_not_normalized_in_frozen_plans(self):
        plan = assessment_plan(
            [{"name": "test", "digest": "sha256:" + "1" * 64}],
            with_requirement=True,
        )
        mutations = (
            lambda item: item["controls"][0].update(
                implementation="test.control_legacy"
            ),
            lambda item: item["controls"][0].update(
                instance_id="test.check_legacy"
            ),
            lambda item: item["assignments"][0]["baselines"].__setitem__(
                0, "test_baseline@1"
            ),
            lambda item: item["requirements"][0].update(
                reference="test_requirement@1"
            ),
        )
        for mutate in mutations:
            changed = copy.deepcopy(plan)
            mutate(changed)
            with self.subTest(mutation=mutate), self.assertRaises(
                ArtifactValidationError
            ):
                validate_assessment_plan(changed)








    def test_plan_rejects_frozen_control_identity_contract_tampering(self):
        cases = {
            "active version": (
                lambda document: document["controls"][0]["policy_inputs"][
                    "definition"
                ]["metadata"].update(version="bad__version"),
                "invalid frozen Control version",
            ),
            "active evidence dependency": (
                lambda document: document["controls"][0]["policy_inputs"][
                    "definition"
                ]["spec"]["evidence"][0].update(id="bad__dependency"),
                "invalid frozen Control evidence dependency identity",
            ),
            "active evidence type": (
                lambda document: document["controls"][0]["policy_inputs"][
                    "definition"
                ]["spec"]["evidence"][0].update(type="bad_type/v1"),
                "invalid frozen Control evidence type",
            ),
            "excluded parameter schema owner": (
                lambda document: document["excluded_controls"][0]["policy_inputs"][
                    "parameters_schema"
                ].update(
                    {
                        "$id": (
                            "https://compliance.example/schemas/controls/other.control/"
                            "parameters/v1.schema.json"
                        )
                    }
                ),
                "parameter schema identity does not match its semantic owner",
            ),
            "malformed parameter schema URI": (
                lambda document: document["excluded_controls"][0]["policy_inputs"][
                    "parameters_schema"
                ].update({
                    "$id": (
                        "https://schemas.\nadopter.example/schemas/controls/"
                        "test.setting-equals/parameters/v1.schema.json"
                    )
                }),
                "parameter schema identity does not match its semantic owner",
            ),
            "empty query delimiter in parameter schema URI": (
                lambda document: document["excluded_controls"][0]["policy_inputs"][
                    "parameters_schema"
                ].update({
                    "$id": (
                        "https://schemas.adopter.example/schemas/controls/"
                        "test.setting-equals/parameters/v1.schema.json?"
                    )
                }),
                "parameter schema identity does not match its semantic owner",
            ),
        }
        for case, (mutate, expected) in cases.items():
            with self.subTest(case=case):
                tampered = copy.deepcopy(self.plan)
                mutate(tampered)
                refresh_operation(tampered)
                tampered["id"] = artifact_digest(tampered)
                with self.assertRaisesRegex(ArtifactValidationError, expected):
                    validate_assessment_plan(tampered)






    def test_result_outcome_uses_fail_first_logical_precedence(self):
        self.assertEqual(result_outcome({
            "results": [{"status": "error"}, {"status": "fail"}],
            "requirement_assessments": [],
            "requirement_baseline_assessments": [],
        }), "fail")

    def test_unknown_results_require_complete_frozen_control_coverage(self):
        report = self.result_report()
        self.assertFalse(report['provenance']['selectedEvidence'])
        self.assertTrue(report['results'])
        changed = copy.deepcopy(report)
        changed['results'] = changed['results'][1:]
        changed['outcome'] = result_outcome(changed)
        changed['id'] = artifact_digest(changed)
        with self.assertRaisesRegex(
            ValueError, 'dependency disposition control is absent from results'
        ):
            validate_assessment_results(changed)

    def test_matching_freshness_copies_cannot_bypass_instance_fingerprint(self):
        from tools.assessment_provenance import artifact_digest
        plan = copy.deepcopy(self.plan)
        control = next(c for c in plan['controls'] if not c['derivations'])
        dependency = control['evidence'][0]
        dependency['max_age'] = '999999999s'
        control['policy_inputs']['instance']['evidence'][dependency['id']]['max_age'] = '999999999s'
        plan['id'] = artifact_digest(plan)
        with self.assertRaisesRegex(ArtifactValidationError, 'instance fingerprint mismatch'):
            validate_assessment_plan(plan)

    def test_frozen_realization_cannot_lose_required_checks(self):
        from tools.assessment_provenance import artifact_digest
        plan = copy.deepcopy(self.iam_plan)
        requirement = plan['requirements'][0]
        self.assertGreater(len(requirement['technical_instance_ids']), 1)
        requirement['technical_instance_ids'] = requirement['technical_instance_ids'][:1]
        plan['id'] = artifact_digest(plan)
        with self.assertRaisesRegex(ArtifactValidationError, 'membership or adoption'):
            validate_assessment_plan(plan)

    def test_frozen_baseline_rejects_different_requirement_digest(self):
        plan = copy.deepcopy(self.iam_plan)
        baseline = plan["resolved_requirement_baselines"][0]
        baseline["requirements"][0]["digest"] = "sha256:" + "0" * 64
        baseline["document"]["spec"]["requirements"][0]["digest"] = "sha256:" + "0" * 64
        baseline["digest"] = content_digest(baseline["document"])
        refresh_operation(plan)
        plan["id"] = artifact_digest(plan)

        with self.assertRaisesRegex(
            ArtifactValidationError,
            "matching baseline membership|RequirementBaseline projection|Objective membership",
        ):
            validate_assessment_plan(plan)

    def test_plan_rejects_retired_realization_classification(self):
        plan = copy.deepcopy(self.iam_plan)
        plan["requirements"][0]["realization"]["classification"] = "restricted"
        plan["id"] = artifact_digest(plan)

        with self.assertRaisesRegex(
            ArtifactValidationError,
            r"classification.*unexpected",
        ):
            validate_assessment_plan(plan)

    def test_frozen_derivation_records_cannot_be_omitted(self):
        from tools.assessment_provenance import artifact_digest
        plan = copy.deepcopy(self.iam_plan)
        plan['resolved_requirement_baselines'] = []
        plan['id'] = artifact_digest(plan)
        with self.assertRaisesRegex(
            ArtifactValidationError,
            'selected baseline|baseline coverage',
        ):
            validate_assessment_plan(plan)

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
            "status": "pass",
            "severity": control["severity"],
            "reason": "Synthetic unit-test pass.",
            "expected": {},
            "observed": {},
            "remediation": control["remediation"],
            "external_refs": control.get("external_refs", []),
            "alignment": control["alignment"],
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
        result = self.result_report()
        validate_assessment_results(result)
        for item in result["results"]:
            self.assertNotIn("title", item)
            self.assertNotIn("purpose", item)

    def test_unavailable_policy_source_refuses_without_invented_provenance(self):
        fixture = Path(__file__).resolve().parent / "fixtures/macos-project"
        subject, groups, assignments = load_inventory_inputs(
            fixture / "inventory",
            fixture / "assignments",
            "workstation/tooling-macos-fixture",
            self.root / "schemas/inventory/resource.schema.json",
        )
        with self.assertRaisesRegex(ValueError, "not a directory"):
            render_plan(subject, groups, assignments, self.root / "does-not-exist-policy")

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

    def test_plan_rejects_missing_or_contradictory_frozen_meaning(self):
        missing = copy.deepcopy(self.plan)
        del missing["controls"][0]["title"]
        with self.assertRaisesRegex(ArtifactValidationError, r"/controls/0.*title"):
            validate_assessment_plan(missing)

        cases = (
            (
                lambda plan: plan["controls"][0].update(
                    title="Contradictory active check title"
                ),
                r"/controls/0/title: differs from frozen Control title",
            ),
            (
                lambda plan: plan["excluded_controls"][0].update(
                    purpose="Contradictory excluded check purpose"
                ),
                r"/excluded_controls/0/purpose: differs from frozen Control purpose",
            ),
        )
        for mutate, message in cases:
            with self.subTest(message=message):
                document = copy.deepcopy(self.plan)
                mutate(document)
                refresh_operation(document)
                document.pop("id", None)
                document["id"] = artifact_digest(document)
                with self.assertRaisesRegex(ArtifactValidationError, message):
                    validate_assessment_plan(document)

        requirement_plan = copy.deepcopy(self.iam_plan)
        requirement_plan["resolved_requirement_baselines"][0]["title"] = (
            "Contradictory objective policy title"
        )
        refresh_operation(requirement_plan)
        requirement_plan.pop("id", None)
        requirement_plan["id"] = artifact_digest(requirement_plan)
        with self.assertRaisesRegex(
            ArtifactValidationError,
            r"RequirementBaseline projection mismatch",
        ):
            validate_assessment_plan(requirement_plan)

    def test_unconsumed_subject_label_is_not_identity_bearing(self):
        document = copy.deepcopy(self.plan)
        document["subject"]["labels"]["changed"] = "true"
        validate_assessment_plan(document)
        self.assertEqual(document['id'], self.plan['id'])

    def test_plan_rejects_stale_member_commitment(self):
        document = copy.deepcopy(self.plan)
        document['controls'][0]['remediation'] = 'tampered'

        with self.assertRaisesRegex(
            ArtifactValidationError,
            "subject plan differs from frozen operation",
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

    def test_results_reject_deleted_predecessor_fields(self):
        document = self.result_report()
        for field, value in (
            ("assessment_id", "old"), ("summary", {}), ("waiver_revision", "sha256:" + "0" * 64),
            ("operation", copy.deepcopy(self.plan["operation"])), ("resolved_policy", {}),
        ):
            changed = copy.deepcopy(document)
            changed[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ArtifactValidationError, field):
                validate_assessment_results(changed)

    def test_results_reject_plan_owned_child_attribution(self):
        document = self.result_report()
        document["results"][0]["plan_id"] = "sha256:" + "0" * 64

        with self.assertRaisesRegex(
            ArtifactValidationError,
            r"/results/0.*plan_id",
        ):
            validate_assessment_results(document)

    def test_results_reject_child_waiver_revision(self):
        document = self.result_report()
        document["results"][0]["waiver_revision"] = "sha256:" + "0" * 64

        with self.assertRaisesRegex(
            ArtifactValidationError,
            r"/results/0.*waiver_revision",
        ):
            validate_assessment_results(document)

    def test_results_reject_inconsistent_objective_rollup(self):
        document = self.result_report(self.iam_plan)
        document["requirement_assessments"][0]["status"] = "fail"
        document["outcome"] = result_outcome(document)
        document["id"] = artifact_digest(document)
        validate_assessment_results(document)
        with self.assertRaisesRegex(ValueError, "requirement outcomes differ"):
            validate_result_against_plan(document, self.iam_plan)

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

    def test_result_loader_rejects_explicit_missing_or_non_result_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "results path does not exist"):
                load_result_reports(root / "missing.json")

            other = root / "policy.json"
            other.write_text(json.dumps({"kind": "Baseline"}), encoding="utf-8")
            with self.assertRaisesRegex(
                ValueError, "results input is not an assessment result"
            ):
                load_result_reports(other)


if __name__ == "__main__":
    unittest.main()
