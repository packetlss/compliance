import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker

from contract_fixtures import fixture_root

from tools.control_realization import (
    compact_plan_outcomes,
    roll_up_plan_requirements,
    validate_realization,
    validate_realization_lineage,
)
from tools.render_plan import load_inventory_inputs, render_plan
from tools.policy_sources import PolicySource
from tools.operation import plan_disposition


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
                schema = {
                    '$id': 'https://compliance.example/schemas/requirements/review.same-objective/parameters/privileged_evidence_max_age/v1.schema.json',
                    'type': 'string',
                }
                requirement['spec']['parameters'] = {'privileged_evidence_max_age': {
                    'required': True, 'binding_mode': 'fixed', 'value': value,
                    'representation': 'duration', 'schema': schema, 'schema_digest': pp.digest(schema)}}
                baseline = copy.deepcopy(self.baseline)
                baseline['metadata'].update(id=f'review.baseline-{revision}', revision=1)
                baseline['spec'] = {
                    'title': f'Review baseline {revision}',
                    'requirements': [{
                        'requirement': f'review.same-objective@{revision}',
                        'digest': pp.digest(requirement),
                        'required': True,
                    }],
                }
                for folder, document in (('requirements', requirement), ('requirement-baselines', baseline)):
                    (root / folder).mkdir(exist_ok=True)
                    (root / folder / f'{revision}.json').write_text(json.dumps(document))
            sources = (PolicySource('control-library', self.root / 'shared'), PolicySource('review', root))
            assignments[0]['baselines'] = ['review.baseline-1@1', 'review.baseline-2@1']
            for reverse in (False, True):
                if reverse:
                    assignments[0]['baselines'].reverse()
                plan = render_plan(subject, groups, assignments, sources)
                self.assertEqual(plan_disposition(plan), 'invalid')
                self.assertTrue(any('stable parameter identity conflict' in e.get('message', '')
                                    for e in plan['resolution']['errors']))
            # Model an artifact emitted before stable-identity reconciliation existed.
            with patch.object(pp, 'reconcile_selected_slots'):
                unreconciled = render_plan(subject, groups, assignments, sources)
            self.assertEqual(plan_disposition(unreconciled), 'result_required')
            unreconciled['id'] = artifact_digest(unreconciled)
            with self.assertRaisesRegex(ArtifactValidationError, 'stable parameter identity conflict'):
                validate_assessment_plan(unreconciled)

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

    def _render_iam_plan(self, profile="restricted-linux", *, private_root=None, reverse=False):
        example = self.root / "iam"
        subject, groups, assignments = load_inventory_inputs(
            example / "inventory", example / "assignments",
            "host/restricted-linux-01",
            self.root / "schemas/inventory/resource.schema.json",
        )
        subject["labels"]["iam-profile"] = profile
        sources = (
            PolicySource("control-library", self.root / "shared"),
            PolicySource("verification-policy", self.root / "selection"),
            PolicySource("environment-private", private_root or example / "policy"),
        )
        return render_plan(subject, groups, assignments, sources[::-1] if reverse else sources)

    def test_trusted_label_selects_exactly_one_complete_realization(self):
        for reverse in (False, True):
            for profile, expected in (
                ("restricted-linux", "restricted.linux.central-role-access@1"),
                ("company-linux", "company.linux.central-role-access@1"),
            ):
                with self.subTest(profile=profile, reverse=reverse):
                    plan = self._render_iam_plan(profile, reverse=reverse)
                    self.assertEqual(plan_disposition(plan), "result_required")
                    self.assertEqual(len(plan["requirements"]), 1)
                    requirement = plan["requirements"][0]
                    self.assertEqual(requirement["realization"]["reference"], expected)
                    self.assertEqual(len(plan["controls"]), 4)
                    self.assertEqual(
                        set(requirement["technical_instance_ids"]),
                        {item["instance_id"] for item in plan["controls"]},
                    )

    def test_ambiguous_realization_selection_is_a_plan_error(self):
        duplicate = copy.deepcopy(self.company_realization)
        duplicate["metadata"]["id"] = "company.linux.central-role-access-copy"
        duplicate["spec"]["applies_to"]["match_labels"] = {
            "iam-profile": "restricted-linux"
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "realizations").mkdir()
            # Reverse file order independently of named-source order.
            for documents in ((duplicate, self.realization), (self.realization, duplicate)):
                for index, document in enumerate(documents):
                    (root / "realizations" / f"{index}.json").write_text(json.dumps(document))
                for reverse in (False, True):
                    with self.subTest(first=documents[0]["metadata"]["id"], reverse=reverse):
                        plan = self._render_iam_plan(private_root=root, reverse=reverse)
                        self.assertEqual(plan_disposition(plan), "invalid")
                        errors = [item for item in plan["resolution"]["errors"]
                                  if item["type"] == "multiple-control-realizations"]
                        self.assertEqual(len(errors), 1)
                        self.assertEqual(errors[0]["realizations"], [
                            "company.linux.central-role-access-copy@1",
                            "restricted.linux.central-role-access@1",
                        ])

    def test_failing_technical_check_fails_requirement_and_top_baseline(self):
        plan = self._render_iam_plan()
        requirements, baselines = compact_plan_outcomes(plan, self.results["results"])
        self.assertEqual(requirements[0]["status"], "fail")
        self.assertEqual(baselines[0]["status"], "fail")
        self.assertEqual(plan["requirements"][0]["adoption"]["status"], "implemented")
        self.assertEqual(
            plan["requirements"][0]["realization"]["based_on"]["realization"],
            "company.linux.central-role-access@1",
        )

    def test_every_required_check_passing_awards_top_baseline_pass(self):
        results = copy.deepcopy(self.results["results"])
        for result in results:
            result["status"] = "pass"
        requirements, baselines = compact_plan_outcomes(self._render_iam_plan(), results)
        self.assertEqual(requirements[0]["status"], "pass")
        self.assertEqual(baselines[0]["status"], "pass")

    def test_missing_or_not_applicable_required_check_is_unknown_not_pass(self):
        plan = self._render_iam_plan()
        passing = copy.deepcopy(self.results["results"])
        for result in passing:
            result["status"] = "pass"
        not_applicable = copy.deepcopy(passing)
        not_applicable[0]["status"] = "not_applicable"
        # An incomplete result list is conservative here; artifact admission
        # separately refuses incomplete persisted plan/result pairs.
        for results in (passing[:-1], not_applicable):
            with self.subTest(results=results):
                requirements, baselines = compact_plan_outcomes(plan, results)
                self.assertEqual(requirements[0]["status"], "unknown")
                self.assertEqual(baselines[0]["status"], "unknown")

    def test_stale_parent_requirement_pin_is_rejected(self):
        realization = copy.deepcopy(self.realization)
        realization["spec"]["requirement"]["digest"] = "sha256:" + "0" * 64
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "realizations").mkdir()
            (root / "realizations/invalid.json").write_text(json.dumps(realization))
            plan = self._render_iam_plan(private_root=root)
        self.assertEqual(plan_disposition(plan), "invalid")
        self.assertTrue(any(item["type"] == "requirement-digest-mismatch"
                            for item in plan["resolution"]["errors"]))

    def test_stale_based_on_pin_is_rejected_without_merging_content(self):
        realization = copy.deepcopy(self.realization)
        realization["spec"]["based_on"]["digest"] = "sha256:" + "0" * 64

        errors = validate_realization_lineage(realization, self.company_realization)

        self.assertEqual(len(errors), 1)
        self.assertIn("does not match", errors[0])

    def test_explicit_not_applicable_realization_preserves_approved_determination(self):
        realization = copy.deepcopy(self.realization)
        realization["spec"]["adoption"] = {
            "status": "not_applicable", "method": "none",
            "owner": "restricted-environment-iam-team",
            "determination": {
                "rationale": "The illustrative subject is outside the IAM requirement scope.",
                "approval_ref": "governance/APP-001", "review_after": "2027-08-23",
            },
        }
        del realization["spec"]["checks"]
        del realization["spec"]["satisfaction"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "realizations").mkdir()
            (root / "realizations/adoption.json").write_text(json.dumps(realization))
            plan = self._render_iam_plan(private_root=root)
        self.assertEqual(plan_disposition(plan), "result_required")
        self.assertEqual(plan["requirements"][0]["adoption"], realization["spec"]["adoption"])
        self.assertEqual(
            plan["requirements"][0]["realization"]["reference"],
            "restricted.linux.central-role-access@1",
        )
        self.assertEqual(plan["controls"], [])
        requirements, baselines = compact_plan_outcomes(plan, [])
        self.assertEqual(requirements[0]["status"], "not_applicable")
        self.assertEqual(baselines[0]["status"], "not_applicable")

    def test_unreferenced_technical_check_is_rejected_as_incomplete_mapping(self):
        realization = copy.deepcopy(self.realization)
        omitted = realization["spec"]["satisfaction"]["allOf"].pop()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "realizations").mkdir()
            (root / "realizations/invalid.json").write_text(json.dumps(realization))
            plan = self._render_iam_plan(private_root=root)
        self.assertEqual(plan_disposition(plan), "invalid")
        errors = [item for item in plan["resolution"]["errors"]
                  if item["type"] == "incomplete-realization-satisfaction"]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["unreferenced"], [omitted])

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
        self.assertEqual(len(plan["requirements"]), 1)
        self.assertEqual(len(plan["controls"]), 4)
        self.assertEqual(
            plan["requirements"][0]["realization"]["reference"],
            "restricted.linux.central-role-access@1",
        )
        self.assertNotIn("classification", plan["requirements"][0]["realization"])
        self.assertNotIn("classification", self.realization["metadata"])
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
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                plan = self._render_iam_plan("unrealized-linux", reverse=reverse)
                requirements, baselines = compact_plan_outcomes(plan, [])
                self.assertEqual(plan["resolution"]["status"], "valid")
                self.assertEqual(plan_disposition(plan), "result_required")
                self.assertEqual(plan["controls"], [])
                self.assertEqual(plan["requirements"][0]["adoption"]["status"], "not_implemented")
                self.assertNotIn("realization", plan["requirements"][0])
                self.assertEqual(requirements[0]["status"], "fail")
                self.assertEqual(baselines[0]["status"], "fail")


if __name__ == "__main__":
    unittest.main()
