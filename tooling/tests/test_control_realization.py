import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker

from contract_fixtures import fixture_root

from tools.control_realization import (
    ControlRealizationError,
    roll_up_plan_requirements,
    roll_up_realization,
    roll_up_requirement_baseline,
    select_realization,
    validate_realization,
    validate_realization_lineage,
)
from tools.render_plan import load_inventory_inputs, render_plan
from tools.policy_sources import PolicySource


class ControlRealizationTests(unittest.TestCase):
    def test_distinct_revisions_cannot_split_stable_parameter_identity(self):
        from tools import policy_parameters as pp
        from tools.artifact_validation import validate_assessment_plan, ArtifactValidationError
        from tools.assessment_provenance import artifact_digest
        subject, groups, assignments = load_inventory_inputs(
            self.root / 'iam/inventory', self.root / 'iam/assignments',
            'host/restricted-linux-01', self.root / 'schemas/inventory/resource.schema.json')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for revision, value in ((1, '30d'), (2, '15d')):
                requirement = copy.deepcopy(self.requirement)
                requirement['metadata'].update(id='review.same-objective', revision=revision)
                schema = {'$id': 'https://example.test/revision-age', 'type': 'string'}
                requirement['spec']['parameters'] = {'privileged_evidence_max_age': {
                    'required': True, 'binding_mode': 'fixed', 'value': value,
                    'representation': 'duration', 'schema': schema, 'schema_digest': pp.digest(schema)}}
                baseline = copy.deepcopy(self.baseline)
                baseline['metadata'].update(id=f'review.baseline-{revision}', revision=1)
                baseline['spec'] = {'requirements': [{'requirement': f'review.same-objective@{revision}',
                    'digest': pp.digest(requirement), 'required': True}]}
                for folder, document in (('requirements', requirement), ('requirement-baselines', baseline)):
                    (root / folder).mkdir(exist_ok=True)
                    (root / folder / f'{revision}.json').write_text(json.dumps(document))
            sources = (PolicySource('control-library', self.root / 'shared'), PolicySource('review', root))
            assignments[0]['baselines'] = ['review.baseline-1@1', 'review.baseline-2@1']
            for reverse in (False, True):
                if reverse:
                    assignments[0]['baselines'].reverse()
                plan = render_plan(subject, groups, assignments, sources)
                self.assertFalse(plan['coverage']['assessable'])
                self.assertTrue(any('stable parameter identity conflict' in e.get('message', '')
                                    for e in plan['resolution']['errors']))
            # Model an artifact emitted before stable-identity reconciliation existed.
            with patch.object(pp, 'reconcile_selected_slots'):
                legacy = render_plan(subject, groups, assignments, sources)
            self.assertTrue(legacy['coverage']['assessable'])
            legacy['id'] = artifact_digest(legacy)
            with self.assertRaisesRegex(ArtifactValidationError, 'stable parameter identity conflict'):
                validate_assessment_plan(legacy)

    @classmethod
    def setUpClass(cls):
        cls.root = fixture_root(cls)
        example = cls.root / "iam"
        verification_policy = (
            cls.root / "selection"
        )
        cls.requirement_path = (
            verification_policy
            / "requirements/company/company-role-based-access.json"
        )
        cls.baseline_path = (
            verification_policy
            / "requirement-baselines/company/company-iam-baseline.json"
        )
        cls.company_realization_path = (
            verification_policy
            / "realizations/company/company-linux-role-based-access.json"
        )
        cls.realization_path = (
            example
            / "policy/realizations/restricted/restricted-linux-role-based-access.json"
        )
        cls.results_path = example / "fixtures/technical-results-failing.json"
        cls.requirement = cls._load(cls.requirement_path)
        cls.baseline = cls._load(cls.baseline_path)
        cls.company_realization = cls._load(cls.company_realization_path)
        cls.realization = cls._load(cls.realization_path)
        cls.results = cls._load(cls.results_path)

    @staticmethod
    def _load(path):
        return json.loads(path.read_text(encoding="utf-8"))

    def test_example_policy_documents_satisfy_their_schemas(self):
        cases = (
            (self.requirement_path, "control-requirement.schema.json"),
            (self.baseline_path, "requirement-baseline.schema.json"),
            (self.company_realization_path, "control-realization.schema.json"),
            (self.realization_path, "control-realization.schema.json"),
        )
        for document_path, schema_name in cases:
            with self.subTest(document=document_path.name):
                schema = self._load(
                    self.root / "shared/schemas/policy" / schema_name
                )
                validator = Draft202012Validator(
                    schema,
                    format_checker=FormatChecker(),
                )
                errors = list(validator.iter_errors(self._load(document_path)))
                self.assertEqual(errors, [])

    def test_realization_pins_parent_and_covers_every_declared_check(self):
        self.assertEqual(validate_realization(self.requirement, self.realization), [])
        self.assertEqual(
            validate_realization_lineage(self.realization, self.company_realization),
            [],
        )

    def test_trusted_label_selects_exactly_one_complete_realization(self):
        restricted = select_realization(
            self.requirement,
            self.results["subject"],
            [self.company_realization, self.realization],
        )
        company_subject = {
            "id": "host/company-linux-01",
            "type": "linux-host",
            "labels": {"iam-profile": "company-linux"},
        }
        company = select_realization(
            self.requirement,
            company_subject,
            [self.company_realization, self.realization],
        )

        self.assertEqual(
            restricted["metadata"]["id"],
            "restricted.linux.central-role-access",
        )
        self.assertEqual(
            company["metadata"]["id"],
            "company.linux.central-role-access",
        )

    def test_missing_or_ambiguous_realization_selection_is_an_error(self):
        missing = copy.deepcopy(self.results["subject"])
        missing["labels"] = {}
        duplicate = copy.deepcopy(self.company_realization)
        duplicate["metadata"]["id"] = "company.linux.central-role-access-copy"
        duplicate["spec"]["applies_to"]["match_labels"] = {
            "iam-profile": "restricted-linux"
        }

        with self.assertRaisesRegex(ControlRealizationError, "not implemented"):
            select_realization(
                self.requirement,
                missing,
                [self.company_realization, self.realization],
            )
        with self.assertRaisesRegex(ControlRealizationError, "multiple realizations"):
            select_realization(
                self.requirement,
                self.results["subject"],
                [self.company_realization, self.realization, duplicate],
            )

    def test_failing_technical_check_fails_requirement_and_top_baseline(self):
        requirement_assessment = roll_up_realization(
            self.requirement,
            self.realization,
            self.results,
        )
        baseline_assessment = roll_up_requirement_baseline(
            self.baseline,
            [requirement_assessment],
        )

        self.assertEqual(requirement_assessment["status"], "fail")
        self.assertEqual(requirement_assessment["adoption"]["status"], "implemented")
        self.assertEqual(
            requirement_assessment["realization_based_on"]["realization"],
            "company.linux.central-role-access@1",
        )
        self.assertEqual(requirement_assessment["check_summary"]["pass"], 3)
        self.assertEqual(requirement_assessment["check_summary"]["fail"], 1)
        self.assertEqual(baseline_assessment["status"], "fail")

    def test_every_required_check_passing_awards_top_baseline_pass(self):
        results = copy.deepcopy(self.results)
        for result in results["results"]:
            result["status"] = "pass"

        requirement_assessment = roll_up_realization(
            self.requirement,
            self.realization,
            results,
        )
        baseline_assessment = roll_up_requirement_baseline(
            self.baseline,
            [requirement_assessment],
        )

        self.assertEqual(requirement_assessment["status"], "pass")
        self.assertEqual(baseline_assessment["status"], "pass")

    def test_missing_or_not_applicable_required_check_is_unknown_not_pass(self):
        missing = copy.deepcopy(self.results)
        missing["results"] = missing["results"][:-1]
        for result in missing["results"]:
            result["status"] = "pass"
        not_applicable = copy.deepcopy(self.results)
        for result in not_applicable["results"]:
            result["status"] = "pass"
        not_applicable["results"][0]["status"] = "not_applicable"

        self.assertEqual(
            roll_up_realization(self.requirement, self.realization, missing)["status"],
            "unknown",
        )
        self.assertEqual(
            roll_up_realization(
                self.requirement,
                self.realization,
                not_applicable,
            )["status"],
            "unknown",
        )

    def test_stale_parent_requirement_pin_is_rejected(self):
        realization = copy.deepcopy(self.realization)
        realization["spec"]["requirement"]["digest"] = "sha256:" + "0" * 64

        with self.assertRaisesRegex(ControlRealizationError, "does not match"):
            roll_up_realization(self.requirement, realization, self.results)

    def test_stale_based_on_pin_is_rejected_without_merging_content(self):
        realization = copy.deepcopy(self.realization)
        realization["spec"]["based_on"]["digest"] = "sha256:" + "0" * 64

        errors = validate_realization_lineage(realization, self.company_realization)

        self.assertEqual(len(errors), 1)
        self.assertIn("does not match", errors[0])

    def test_adoption_state_does_not_imply_a_pass(self):
        not_implemented = copy.deepcopy(self.realization)
        not_implemented["spec"]["adoption"] = {
            "status": "not_implemented",
            "method": "none",
            "owner": "restricted-environment-iam-team",
        }
        del not_implemented["spec"]["checks"]
        del not_implemented["spec"]["satisfaction"]
        not_applicable = copy.deepcopy(not_implemented)
        not_applicable["spec"]["adoption"] = {
            "status": "not_applicable",
            "method": "none",
            "owner": "restricted-environment-iam-team",
            "determination": {
                "rationale": "The illustrative subject is outside the IAM requirement scope.",
                "approval_ref": "governance/APP-001",
                "review_after": "2027-08-23",
            },
        }

        self.assertEqual(
            roll_up_realization(
                self.requirement,
                not_implemented,
                self.results,
            )["status"],
            "fail",
        )
        self.assertEqual(
            roll_up_realization(
                self.requirement,
                not_applicable,
                self.results,
            )["status"],
            "not_applicable",
        )

    def test_top_baseline_rejects_assessment_for_different_requirement_digest(self):
        assessment = roll_up_realization(
            self.requirement,
            self.realization,
            self.results,
        )
        assessment["requirement_digest"] = "sha256:" + "0" * 64

        with self.assertRaisesRegex(ControlRealizationError, "does not match baseline pin"):
            roll_up_requirement_baseline(self.baseline, [assessment])

    def test_unreferenced_technical_check_is_rejected_as_incomplete_mapping(self):
        realization = copy.deepcopy(self.realization)
        realization["spec"]["satisfaction"]["allOf"].pop()

        with self.assertRaisesRegex(ControlRealizationError, "omitted from satisfaction"):
            roll_up_realization(self.requirement, realization, self.results)

    def test_registered_iam_project_renders_restricted_realization(self):
        example = self.root / "iam"
        subject, groups, assignments = load_inventory_inputs(
            example / "inventory",
            example / "assignments",
            "host/restricted-linux-01",
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
                PolicySource("environment-private", example / "policy"),
            ),
        )

        self.assertEqual(plan["resolution"]["status"], "valid")
        self.assertEqual(plan["coverage"]["requirement_count"], 1)
        self.assertEqual(len(plan["controls"]), 4)
        self.assertEqual(
            plan["requirements"][0]["realization"]["reference"],
            "restricted.linux.central-role-access@1",
        )
        self.assertEqual(
            plan["requirements"][0]["realization"]["based_on"]["realization"],
            "company.linux.central-role-access@1",
        )

    def test_rendered_plan_results_roll_up_to_objective_and_baseline(self):
        example = self.root / "iam"
        subject, groups, assignments = load_inventory_inputs(
            example / "inventory",
            example / "assignments",
            "host/restricted-linux-01",
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
                PolicySource("environment-private", example / "policy"),
            ),
        )

        requirements, baselines = roll_up_plan_requirements(
            plan,
            self.results["results"],
        )

        self.assertEqual(requirements[0]["status"], "fail")
        self.assertEqual(requirements[0]["check_summary"]["pass"], 3)
        self.assertEqual(requirements[0]["check_summary"]["fail"], 1)
        self.assertEqual(baselines[0]["status"], "fail")

    def test_missing_realization_is_assessable_not_implemented_failure(self):
        example = self.root / "iam"
        subject, groups, assignments = load_inventory_inputs(
            example / "inventory",
            example / "assignments",
            "host/restricted-linux-01",
            self.root / "schemas/inventory/resource.schema.json",
        )
        subject["labels"]["iam-profile"] = "unrealized-linux"
        assignments[0]["target"]["group"] = "company-assets"

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
                PolicySource("environment-private", example / "policy"),
            ),
        )
        requirements, baselines = roll_up_plan_requirements(plan, [])

        self.assertEqual(plan["resolution"]["status"], "valid")
        self.assertTrue(plan["coverage"]["assessable"])
        self.assertEqual(plan["controls"], [])
        self.assertEqual(plan["requirements"][0]["adoption"]["status"], "not_implemented")
        self.assertEqual(requirements[0]["status"], "fail")
        self.assertEqual(baselines[0]["status"], "fail")


if __name__ == "__main__":
    unittest.main()
