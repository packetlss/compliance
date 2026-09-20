"""Frozen ParameterPolicy reconstruction and tamper refusal vectors."""
import copy
import unittest
from pathlib import Path

from tools import policy_parameters as pp
from tools.artifact_validation import ArtifactValidationError, validate_assessment_plan
from tools.assessment_provenance import artifact_digest
from tools.policy_sources import PolicySource
from tools.render_plan import load_inventory_inputs, render_plan


ROOT = Path(__file__).resolve().parents[2]


class ParameterPolicyArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project = ROOT / "verification/scenarios/projects/authorized-software-composition"
        sources = (
            PolicySource("control-library", ROOT / "policy-sources/control-library/policies"),
            PolicySource("verification-policy", ROOT / "policy-sources/verification-policy/policies"),
        )
        subject, groups, assignments = load_inventory_inputs(
            project / "inventory", project / "assignments",
            "host/authorized-database",
            ROOT / "tooling/schemas/inventory/resource.schema.json",
        )
        cls.plan = render_plan(subject, groups, assignments, sources)

    @staticmethod
    def resign(plan):
        plan.pop("id", None)
        plan["id"] = artifact_digest(plan)

    def test_direct_technical_plan_has_no_objective_or_derived_parameter_copies(self):
        validate_assessment_plan(self.plan)
        self.assertEqual(self.plan["requirements"], [])
        encoded = str(self.plan)
        self.assertNotIn("parameter_facts", encoded)
        self.assertNotIn("parameter_derivation", encoded)
        state = pp.reconstruct_frozen_parameters(self.plan)[0][
            "company.authorized-software@1"
        ]["allowed_software"]
        self.assertEqual(state["value"], ["auditd", "curl", "postgresql"])
        self.assertEqual(len(state["composition"]["contributions"]), 1)

    def test_old_current_representation_is_rejected(self):
        changed = copy.deepcopy(self.plan)
        changed["requirements"] = [{"parameter_facts": {}}]
        self.resign(changed)
        with self.assertRaises(ArtifactValidationError):
            validate_assessment_plan(changed)

    def test_document_content_and_pin_tampering_is_reconstructed(self):
        changed = copy.deepcopy(self.plan)
        record = next(item for item in changed["parameters"]["documents"]
                      if item["reference"] == "company.database-software@1")
        record["document"]["spec"]["parameter_contributions"][0]["members"] = ["changed"]
        record["digest"] = pp.resource_digest(record["document"])
        self.resign(changed)
        with self.assertRaisesRegex(ArtifactValidationError, "materialized destination"):
            validate_assessment_plan(changed)

    def test_applicability_and_complete_contribution_membership_are_checked(self):
        changed = copy.deepcopy(self.plan)
        changed["parameters"]["applicability"].pop()
        self.resign(changed)
        with self.assertRaisesRegex(ArtifactValidationError, "applicability"):
            validate_assessment_plan(changed)

    def test_authored_operation_and_materialized_destination_are_checked(self):
        changed = copy.deepcopy(self.plan)
        record = next(item for item in changed["parameters"]["documents"]
                      if item["reference"] == "company.authorized-software-base@1")
        record["document"]["spec"]["parameter_operations"][0]["to"] = ["auditd"]
        record["digest"] = pp.resource_digest(record["document"])
        self.resign(changed)
        with self.assertRaisesRegex(ArtifactValidationError, "materialized destination"):
            validate_assessment_plan(changed)

    def test_symbolic_consumer_interface_is_checked(self):
        changed = copy.deepcopy(self.plan)
        changed["parameters"]["consumers"][0]["links"][0]["destination"]["path"] = "/missing"
        self.resign(changed)
        with self.assertRaises(ArtifactValidationError):
            validate_assessment_plan(changed)

    def test_materialized_value_is_not_a_second_policy_authority(self):
        changed = copy.deepcopy(self.plan)
        control = changed["controls"][0]
        control["parameters"]["allowed"] = ["auditd"]
        control["policy_inputs"]["instance"]["parameters"]["allowed"] = ["auditd"]
        self.resign(changed)
        with self.assertRaises(ArtifactValidationError):
            validate_assessment_plan(changed)


if __name__ == "__main__":
    unittest.main()
