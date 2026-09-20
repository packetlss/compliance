"""Frozen ParameterPolicy reconstruction and tamper refusal vectors."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools import policy_parameters as pp
from tools.artifact_validation import ArtifactValidationError, validate_assessment_plan
from tools.assessment_provenance import artifact_digest
from tools.policy_diff import build_policy_diff
from tools.policy_sources import PolicySource
from tools.render_plan import (
    baseline_semantic_digest,
    load_inventory_inputs,
    render_plan,
    resolve_baseline,
)
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

    @staticmethod
    def repin_consumer(plan, consumer):
        old_digest = consumer["digest"]
        consumer["digest"] = baseline_semantic_digest(consumer["document"])
        for baseline in plan["resolved_baselines"]:
            if baseline["reference"] == consumer["reference"]:
                baseline["digest"] = consumer["digest"]
            for ancestor in baseline["lineage"]:
                if (ancestor["reference"] == consumer["reference"]
                        and ancestor["digest"] == old_digest):
                    ancestor["digest"] = consumer["digest"]

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

    def test_unselected_realization_consumer_is_rejected(self):
        changed = copy.deepcopy(self.plan)
        changed["parameters"]["consumers"].append({
            "kind": "ControlRealization",
            "reference": "forged.unselected@1",
            "digest": "sha256:" + "0" * 64,
            "policy_sources": [{
                "policy_source": "verification-policy",
                "path": "realizations/forged.json",
            }],
        })
        changed["parameters"]["consumers"].sort(
            key=lambda item: (item["kind"], item["reference"])
        )
        self.resign(changed)

        with self.assertRaisesRegex(
            ArtifactValidationError,
            "realization consumer is not selected",
        ):
            validate_assessment_plan(changed)

    def test_independent_identical_direct_consumers_coalesce(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_root = Path(directory) / "policies"
            shutil.copytree(self.sources[1].path, policy_root)
            source_path = (
                policy_root
                / "baselines/company/company-authorized-software.json"
            )
            duplicate = json.loads(source_path.read_text(encoding="utf-8"))
            duplicate["metadata"]["id"] = "company.authorized-software-copy"
            target = source_path.with_name("company-authorized-software-copy.json")
            target.write_text(json.dumps(duplicate), encoding="utf-8")
            assignments = copy.deepcopy(self.assignments)
            managed = next(
                item for item in assignments
                if item["id"] == "managed-linux-software"
            )
            managed["baselines"].append("company.authorized-software-copy@1")
            plan = render_plan(
                self.subject,
                self.groups,
                assignments,
                (self.sources[0], PolicySource("verification-policy", policy_root)),
            )

        self.assertEqual(plan["resolution"]["status"], "valid")
        self.assertEqual(len(plan["controls"]), 1)
        self.assertEqual(len(pp.frozen_technical_links(plan)), 1)
        validate_assessment_plan(plan)
        for reference in (
            "company.authorized-software-check@1",
            "company.authorized-software-copy@1",
        ):
            changed = copy.deepcopy(plan)
            changed["parameters"]["consumers"] = [
                consumer for consumer in changed["parameters"]["consumers"]
                if consumer["reference"] != reference
            ]
            self.resign(changed)
            with self.subTest(reference=reference), self.assertRaisesRegex(
                ArtifactValidationError,
                "technical consumer owner is missing",
            ):
                validate_assessment_plan(changed)

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

    def test_direct_consumer_owner_and_source_match_retained_selection(self):
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

    def test_technical_consumer_reconstructs_authored_check_body(self):
        changed = copy.deepcopy(self.plan)
        consumer = changed["parameters"]["consumers"][0]
        consumer["document"]["spec"]["controls"][0]["parameters"]["allowed"] = [
            "telnet"
        ]
        self.repin_consumer(changed, consumer)
        self.resign(changed)

        with self.assertRaisesRegex(
            ArtifactValidationError,
            "consumer Check differs from retained owner",
        ):
            validate_assessment_plan(changed)

    def test_frozen_parameter_tailoring_rejects_invalid_governance_date(self):
        project = ROOT / "verification/fixtures/iam-private-boundary"
        subject, groups, assignments = load_inventory_inputs(
            project / "inventory",
            project / "assignments",
            "host/restricted-linux-01",
            ROOT / "tooling/schemas/inventory/resource.schema.json",
        )
        plan = render_plan(
            subject,
            groups,
            assignments,
            (
                self.sources[0],
                self.sources[1],
                PolicySource("environment-private", project / "policy"),
            ),
        )
        changed = copy.deepcopy(plan)
        parameter = next(
            item for item in changed["parameters"]["documents"]
            if item["reference"] == "restricted.iam.role-based-access@1"
        )
        parameter["document"]["spec"]["parameter_operations"][0]["deviation"][
            "review_after"
        ] = "not-a-date"
        parameter["digest"] = pp.resource_digest(parameter["document"])
        self.resign(changed)
        with self.assertRaisesRegex(
            ArtifactValidationError,
            "invalid parameter deviation date",
        ):
            validate_assessment_plan(changed)

    def test_objective_owner_sources_belong_to_planning_composition(self):
        project = ROOT / "verification/fixtures/iam-private-boundary"
        subject, groups, assignments = load_inventory_inputs(
            project / "inventory",
            project / "assignments",
            "host/restricted-linux-01",
            ROOT / "tooling/schemas/inventory/resource.schema.json",
        )
        plan = render_plan(
            subject,
            groups,
            assignments,
            (
                self.sources[0],
                self.sources[1],
                PolicySource("environment-private", project / "policy"),
            ),
        )
        records = (
            (plan["resolved_requirement_baselines"][0], "RequirementBaseline"),
            (plan["requirements"][0], "Objective"),
            (plan["requirements"][0]["realization"], "ControlRealization"),
        )
        for record, kind in records:
            changed = copy.deepcopy(plan)
            if kind == "RequirementBaseline":
                target = changed["resolved_requirement_baselines"][0]
            elif kind == "Objective":
                target = changed["requirements"][0]
            else:
                target = changed["requirements"][0]["realization"]
            target["policy_sources"] = [{
                "policy_source": "forged",
                "path": "fake.json",
            }]
            self.resign(changed)
            with self.subTest(kind=kind), self.assertRaisesRegex(
                ArtifactValidationError,
                f"frozen {kind} source is absent from planning composition",
            ):
                validate_assessment_plan(changed)

    def test_selected_nonconsuming_parent_can_be_retained_as_consumer_ancestry(self):
        source = self.plan["parameters"]["consumers"][0]
        parent = copy.deepcopy(source["document"])
        parent["metadata"]["id"] = "company.parameter-parent"
        parent["spec"].pop("parameter_links")
        parent_reference = "company.parameter-parent@1"
        parent_digest = baseline_semantic_digest(parent)
        overlay = {
            "apiVersion": "compliance.example/v1",
            "kind": "BaselineOverlay",
            "metadata": {"id": "company.parameter-child", "revision": 1},
            "spec": {
                "title": "Parameter consuming child",
                "extends": [{"baseline": parent_reference, "digest": parent_digest}],
                "operations": [],
                "parameter_links": copy.deepcopy(
                    source["document"]["spec"]["parameter_links"]
                ),
            },
        }
        overlay_reference = "company.parameter-child@1"
        overlay_digest = baseline_semantic_digest(overlay)
        locator = [{"policy_source": "test", "path": "policy.json"}]
        plan = {
            "parameters": {"consumers": [
                {"kind": "Baseline", "reference": parent_reference,
                 "digest": parent_digest, "policy_sources": locator,
                 "document": parent},
                {"kind": "BaselineOverlay", "reference": overlay_reference,
                 "digest": overlay_digest, "policy_sources": locator,
                 "document": overlay},
            ]},
            "resolved_baselines": [
                {"reference": parent_reference, "digest": parent_digest,
                 "lineage": [{"reference": parent_reference,
                              "digest": parent_digest, "policy_sources": locator}]},
                {"reference": overlay_reference, "digest": overlay_digest,
                 "lineage": [
                     {"reference": parent_reference, "digest": parent_digest,
                      "policy_sources": locator},
                     {"reference": overlay_reference, "digest": overlay_digest,
                      "policy_sources": locator},
                 ]},
            ],
        }

        self.assertEqual(len(pp.frozen_technical_links(plan)), 1)

    def test_excluded_direct_check_with_parameter_link_is_admissible(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_root = Path(directory) / "policies"
            shutil.copytree(self.sources[1].path, policy_root)
            parent_path = (
                policy_root
                / "baselines/company/company-authorized-software.json"
            )
            parent = json.loads(parent_path.read_text(encoding="utf-8"))
            parent_reference = "company.authorized-software-check@1"
            parent_digest = baseline_semantic_digest(parent)
            catalog_parent = {
                **copy.deepcopy(parent),
                "_digest": parent_digest,
                "_sources": [{"policy_source": "verification-policy",
                              "path": "baselines/company/company-authorized-software.json"}],
            }
            resolved = resolve_baseline(parent_reference, {
                parent_reference: catalog_parent,
            })
            instance_id = "company.linux.authorized-software.only-allowed"
            overlay = {
                "apiVersion": "compliance.example/v1",
                "kind": "BaselineOverlay",
                "metadata": {"id": "company.authorized-software-excluded", "revision": 1},
                "spec": {
                    "title": "Excluded authorized software check",
                    "extends": [{"baseline": parent_reference, "digest": parent_digest}],
                    "operations": [{
                        "op": "exclude",
                        "target": instance_id,
                        "expected_parent_fingerprint": resolved["controls"][instance_id][
                            "definition_fingerprint"
                        ],
                        "deviation": {
                            "id": "DEV-EXCLUDED-PARAMETER",
                            "classification": "temporary-exclusion",
                            "rationale": "Exercise frozen excluded consumer admission",
                            "approval_ref": "test/review",
                            "review_after": "2027-01-01",
                        },
                    }],
                },
            }
            overlay_path = policy_root / "baselines/company/excluded-parameter.json"
            overlay_path.write_text(json.dumps(overlay), encoding="utf-8")
            assignments = copy.deepcopy(self.assignments)
            next(item for item in assignments
                 if item["id"] == "managed-linux-software")["baselines"] = [
                     "company.authorized-software-excluded@1"
                 ]
            plan = render_plan(
                self.subject,
                self.groups,
                assignments,
                (self.sources[0], PolicySource("verification-policy", policy_root)),
            )

        self.assertEqual(plan["resolution"]["status"], "valid")
        self.assertEqual(plan["controls"], [])
        self.assertEqual(len(plan["excluded_controls"]), 1)
        validate_assessment_plan(plan)

    def test_invalid_parameter_policy_catalog_returns_admissible_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_root = Path(directory) / "policies"
            shutil.copytree(self.sources[1].path, policy_root)
            path = (
                policy_root
                / "parameter-policies/company/company-authorized-software-base.json"
            )
            resource = json.loads(path.read_text(encoding="utf-8"))
            resource["spec"]["parameter_operations"][0][
                "expected_parent_fingerprint"
            ] = "sha256:" + "0" * 64
            path.write_text(json.dumps(resource), encoding="utf-8")
            plan = render_plan(
                self.subject,
                self.groups,
                self.assignments,
                (self.sources[0], PolicySource("verification-policy", policy_root)),
            )

        self.assertEqual(plan["resolution"]["status"], "invalid")
        self.assertIn("parameter-policy-invalid", {
            error["type"] for error in plan["resolution"]["errors"]
        })
        self.assertEqual(
            plan["parameters"]["applicability"],
            [{"group": "database", "assignment": "database-software",
              "parameter_policy": "company.database-software@1"},
             {"group": "managed-linux", "assignment": "managed-linux-software",
              "parameter_policy": "company.authorized-software-base@1"}],
        )
        validate_assessment_plan(plan)
        self.assertEqual(
            build_policy_diff(self.plan, plan)["comparison"]["status"],
            "incomplete",
        )

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
