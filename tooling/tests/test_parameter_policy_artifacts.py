"""Frozen ParameterPolicy reconstruction and tamper refusal vectors."""
import copy
import unittest
from pathlib import Path

from tools import policy_parameters as pp
from tools.artifact_validation import ArtifactValidationError, validate_assessment_plan
from tools.assessment_provenance import artifact_digest
from tools.policy_diff import build_policy_diff
from tools.policy_sources import PolicySource
from tools.render_plan import load_inventory_inputs, render_plan
from assessment_fixture import refresh_operation


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
        cls.subject = subject
        cls.groups = groups
        cls.assignments = assignments
        cls.sources = sources
        cls.plan = render_plan(subject, groups, assignments, sources)

    @staticmethod
    def resign(plan):
        refresh_operation(plan)
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
        changed.pop("id", None)
        changed["id"] = artifact_digest(changed)
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
        consumer = changed["parameters"]["consumers"][0]
        old_digest = consumer["digest"]
        consumer["document"]["spec"]["parameter_links"][0]["destination"]["path"] = "/missing"
        consumer["digest"] = pp.digest(consumer["document"])
        for baseline in changed["resolved_baselines"]:
            if baseline["reference"] == consumer["reference"]:
                baseline["digest"] = consumer["digest"]
            for ancestor in baseline["lineage"]:
                if ancestor["reference"] == consumer["reference"] and ancestor["digest"] == old_digest:
                    ancestor["digest"] = consumer["digest"]
        self.resign(changed)
        with self.assertRaises(ArtifactValidationError):
            validate_assessment_plan(changed)

    def test_direct_consumer_owner_and_source_are_authenticated(self):
        changed = copy.deepcopy(self.plan)
        changed["parameters"]["consumers"][0]["document"]["metadata"]["id"] = "forged.owner"
        self.resign(changed)
        with self.assertRaisesRegex(ArtifactValidationError, "consumer owner mismatch"):
            validate_assessment_plan(changed)

        changed = copy.deepcopy(self.plan)
        changed["parameters"]["consumers"][0]["policy_sources"][0]["policy_source"] = "forged"
        self.resign(changed)
        with self.assertRaisesRegex(ArtifactValidationError, "consumer source mismatch"):
            validate_assessment_plan(changed)

    def test_invalid_reconstruction_cannot_bypass_materialized_consumer_validation(self):
        changed = copy.deepcopy(self.plan)
        changed["parameters"]["documents"] = [
            item for item in changed["parameters"]["documents"]
            if item["reference"] != "company.database-software@1"
        ]
        changed["resolution"] = {
            "status": "invalid",
            "errors": [{"type": "parameter-resolution-failed"}],
        }
        changed["controls"][0]["parameters"]["allowed"] = ["telnet"]
        changed["controls"][0]["policy_inputs"]["instance"]["parameters"]["allowed"] = ["telnet"]
        self.resign(changed)
        with self.assertRaisesRegex(
            ArtifactValidationError,
            "unresolved ParameterPolicy cannot retain materialized consumers",
        ):
            validate_assessment_plan(changed)

    def test_frozen_parameter_documents_reject_unrecognized_wire_fields(self):
        mutations = (
            lambda document: document.update(apiVersion="compliance.example/v2"),
            lambda document: document.update(unrecognized=True),
            lambda document: document["spec"]["parameter_operations"][0].update(unrecognized=True),
        )
        for mutate in mutations:
            changed = copy.deepcopy(self.plan)
            record = next(
                item for item in changed["parameters"]["documents"]
                if item["reference"] == "company.authorized-software-base@1"
            )
            mutate(record["document"])
            record["digest"] = pp.resource_digest(record["document"])
            self.resign(changed)
            with self.subTest(mutation=mutate):
                with self.assertRaises(ArtifactValidationError):
                    validate_assessment_plan(changed)

    def test_additive_operation_content_pin_uses_catalog_normalization(self):
        changed = copy.deepcopy(self.plan)
        record = next(
            item for item in changed["parameters"]["documents"]
            if item["reference"] == "company.authorized-software-base@1"
        )
        record["document"]["spec"]["parameter_operations"][0]["to"].reverse()
        record["digest"] = pp.resource_digest(record["document"])
        self.resign(changed)

        with self.assertRaisesRegex(ArtifactValidationError, "content pin mismatch"):
            validate_assessment_plan(changed)

    def test_parameter_policy_source_must_belong_to_recorded_composition(self):
        changed = copy.deepcopy(self.plan)
        changed["parameters"]["documents"][0]["policy_sources"][0][
            "policy_source"
        ] = "forged-unexecuted-source"
        self.resign(changed)

        with self.assertRaisesRegex(ArtifactValidationError, "absent from planning composition"):
            validate_assessment_plan(changed)

    def test_technical_consumer_replays_every_authored_effective_link(self):
        changed = copy.deepcopy(self.plan)
        consumer = changed["parameters"]["consumers"][0]
        duplicate = copy.deepcopy(
            consumer["document"]["spec"]["parameter_links"][0]
        )
        duplicate["id"] = "second-allowed-software-link"
        consumer["document"]["spec"]["parameter_links"].append(duplicate)
        old_digest = consumer["digest"]
        consumer["digest"] = pp.digest(consumer["document"])
        for baseline in changed["resolved_baselines"]:
            if baseline["reference"] == consumer["reference"]:
                baseline["digest"] = consumer["digest"]
            for ancestor in baseline["lineage"]:
                if ancestor["reference"] == consumer["reference"] and ancestor["digest"] == old_digest:
                    ancestor["digest"] = consumer["digest"]
        self.resign(changed)

        with self.assertRaisesRegex(
            ArtifactValidationError,
            "ambiguous consumption destination",
        ):
            validate_assessment_plan(changed)

    def test_technical_consumer_document_rejects_unrecognized_wire_fields(self):
        changed = copy.deepcopy(self.plan)
        consumer = changed["parameters"]["consumers"][0]
        consumer["document"]["unrecognized"] = True
        old_digest = consumer["digest"]
        consumer["digest"] = pp.digest(consumer["document"])
        for baseline in changed["resolved_baselines"]:
            if baseline["reference"] == consumer["reference"]:
                baseline["digest"] = consumer["digest"]
            for ancestor in baseline["lineage"]:
                if ancestor["reference"] == consumer["reference"] and ancestor["digest"] == old_digest:
                    ancestor["digest"] = consumer["digest"]
        self.resign(changed)

        with self.assertRaisesRegex(
            ArtifactValidationError,
            "unsupported frozen technical consumer document syntax",
        ):
            validate_assessment_plan(changed)

    def test_policy_diff_treats_parameter_resolution_refusal_as_incomplete(self):
        assignments = copy.deepcopy(self.assignments)
        managed = next(item for item in assignments if item["id"] == "managed-linux-software")
        managed["parameter_policies"] = []
        invalid = render_plan(
            self.subject,
            self.groups,
            assignments,
            self.sources,
        )

        self.assertEqual(invalid["resolution"]["status"], "invalid")
        document = build_policy_diff(self.plan, invalid)
        self.assertEqual(document["comparison"]["status"], "incomplete")
        self.assertEqual(document["parameter_changes"], [])

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
