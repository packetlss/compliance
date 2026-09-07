"""Verification-policy contracts using only owned resources and explicit inputs."""

from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import shutil
import tempfile
import unittest

from tools.control_realization import roll_up_plan_requirements
from tools.policy_sources import PolicySource, policy_source_revisions, source_tree_digest
from tools.render_plan import (
    load_policy_catalogs,
    load_requirement_catalogs,
    render_plan,
    resolve_baseline,
)


ROOT = Path(__file__).resolve().parents[1]
CONTROL_LIBRARY = Path(os.environ["COMPLIANCE_CONTROL_LIBRARY_ROOT"]) / "policies"
check_source_boundary = runpy.run_path(str(ROOT / "scripts/check-source-boundary.py"))["check_source_boundary"]
BASELINE = Path("baselines/company/company-linux-server-operations.json")
REALIZATION = Path("realizations/company/company-linux-role-based-access.json")


def sources(root: Path) -> tuple[PolicySource, ...]:
    return (PolicySource("control-library", CONTROL_LIBRARY), PolicySource("verification-policy", root))


class VerificationPolicySourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "source"
        shutil.copytree(ROOT / "policies", self.root)

    def mutate(self, relative: Path, change) -> None:
        path = self.root / relative
        document = json.loads(path.read_text())
        change(document)
        path.write_text(json.dumps(document))

    def error_types(self) -> set[str]:
        _, _, errors = load_policy_catalogs(sources(self.root))
        return {error["type"] for error in errors}

    def test_every_owned_resource_validates_with_explicit_reusable_contracts(self) -> None:
        check_source_boundary(self.root)
        controls, baselines, errors = load_policy_catalogs(sources(self.root))
        self.assertEqual(errors, [])
        requirements, objectives, realizations, errors = load_requirement_catalogs(sources(self.root), controls)
        self.assertEqual(errors, [])
        self.assertEqual(set(baselines), {
            "benchmark.example.linux-server-hardening@2026.1",
            "benchmark.example.macos-hardening@2026.1",
            "company.aws-foundation@1",
            "company.aws-s3-public-access@1",
            "company.container-runtime-host@1",
            "company.developer-workstation@1",
            "company.linux-server-hardening@1",
            "company.linux-server-operations@1",
            "company.macos-policy@1",
            "company.saas-foundation@1",
            "managed-workstation@1",
            "profile.csa-ccm.aws-foundations@4.1-profile1",
            "profile.csa-ccm.saas-foundations@4.1-profile1",
            "verification.technical-packages-with-aide@1",
            "verification.technical-packages@1",
        })
        self.assertEqual(set(requirements), {
            "company.iam.role-based-access@1",
            "verification.operation.entity.o1@1",
            "verification.operation.entity.o2@1",
            "verification.operation.entity.o3@1",
            "verification.operation.system.o1@1",
        })
        self.assertEqual(set(objectives), {
            "company.identity-access-objectives@1",
            "verification.operation.entity@1",
            "verification.operation.system@1",
        })
        self.assertEqual(set(realizations), {
            "company.linux.central-role-access@1",
            "verification.operation.entity.o1.realization@1",
            "verification.operation.entity.o2.realization@1",
            "verification.operation.entity.o3.realization@1",
        })
        for catalog in (baselines, requirements, objectives, realizations):
            self.assertTrue(all(item["_source"].startswith("verification-policy:") for item in catalog.values()))
        self.assertTrue(all(item["_source"].startswith("control-library:") for item in controls.values()))

    def test_source_order_does_not_change_resources_or_named_identity(self) -> None:
        ordered = sources(self.root)
        reversed_sources = tuple(reversed(ordered))
        self.assertEqual(load_policy_catalogs(ordered), load_policy_catalogs(reversed_sources))
        self.assertEqual(policy_source_revisions(ordered), policy_source_revisions(reversed_sources))

    def test_identical_private_resource_coalesces_but_divergence_conflicts(self) -> None:
        private = Path(self.temporary.name) / "private"
        target = private / REALIZATION
        target.parent.mkdir(parents=True)
        shutil.copyfile(self.root / REALIZATION, target)
        combined = (
            PolicySource("control-library", CONTROL_LIBRARY),
            PolicySource("verification-policy", self.root),
            PolicySource("environment-private", private),
        )

        controls, _, errors = load_policy_catalogs(combined)
        self.assertEqual(errors, [])
        _, _, realizations, errors = load_requirement_catalogs(combined, controls)
        self.assertEqual(errors, [])
        self.assertEqual(
            [item["policy_source"] for item in realizations[
                "company.linux.central-role-access@1"
            ]["_sources"]],
            ["environment-private", "verification-policy"],
        )

        self.mutate_private(target, lambda item: item["metadata"].update(classification="restricted"))
        _, _, errors = load_policy_catalogs(combined)
        conflict = next(error for error in errors if error["type"] == "policy-resource-conflict")
        self.assertEqual(conflict["kind"], "ControlRealization")
        self.assertEqual(conflict["identity"], "company.linux.central-role-access@1")

    def test_retained_baseline_overlay_preserves_assessment_lineage(self) -> None:
        _, baselines, errors = load_policy_catalogs(sources(self.root))
        self.assertEqual(errors, [])
        resolved = resolve_baseline("company.container-runtime-host@1", baselines)
        forwarding = resolved["controls"][
            "benchmark.example.linux-server.ip-forwarding-disabled"
        ]

        self.assertEqual(forwarding["parameters"]["settings"][0]["value"], "1")
        self.assertEqual(forwarding["alignment"], "tailored")
        self.assertEqual(forwarding["deviations"][0]["id"], "DEV-LINUX-CONTAINER-001")
        self.assertEqual(
            [item["reference"] for item in resolved["lineage"]],
            [
                "benchmark.example.linux-server-hardening@2026.1",
                "company.linux-server-hardening@1",
                "company.container-runtime-host@1",
            ],
        )

    def test_retained_technical_assignment_conflict_fails_closed(self) -> None:
        subject = {
            "schema": "compliance.example/inventory-subject/v1",
            "id": "host/conflict",
            "type": "linux-host",
            "status": "active",
            "labels": {},
            "inventory": {
                "source": "verification-test",
                "external_id": "conflict",
                "observed_at": "2026-09-04T00:00:00Z",
            },
        }
        groups = [{"id": "linux", "parents": [], "members": [subject["id"]]}]
        assignments = [
            {
                "id": "container",
                "target": {"group": "linux"},
                "baselines": ["company.container-runtime-host@1"],
            },
            {
                "id": "standard",
                "target": {"group": "linux"},
                "baselines": ["company.linux-server-hardening@1"],
            },
        ]

        plan = render_plan(subject, groups, assignments, sources(self.root))

        self.assertEqual(plan["resolution"]["status"], "invalid")
        from tools.operation import plan_disposition
        self.assertEqual(plan_disposition(plan), "invalid")
        conflict = next(
            error
            for error in plan["resolution"]["errors"]
            if error["type"] == "control-instance-conflict"
        )
        self.assertEqual(
            conflict["instance_id"],
            "benchmark.example.linux-server.ip-forwarding-disabled",
        )

    def test_requirement_realization_selection_and_roll_up_are_evidence_backed(self) -> None:
        subject = {
            "schema": "compliance.example/inventory-subject/v1",
            "id": "host/iam",
            "type": "linux-host",
            "status": "active",
            "labels": {"iam-profile": "company-linux"},
            "inventory": {
                "source": "verification-test",
                "external_id": "iam",
                "observed_at": "2026-09-04T00:00:00Z",
            },
        }
        groups = [{"id": "iam", "parents": [], "members": [subject["id"]]}]
        assignments = [{
            "id": "iam-objectives",
            "target": {"group": "iam"},
            "baselines": ["company.identity-access-objectives@1"],
        }]
        plan = render_plan(subject, groups, assignments, sources(self.root))
        requirement = plan["requirements"][0]

        self.assertEqual(plan["resolution"]["status"], "valid")
        self.assertEqual(
            requirement["realization"]["reference"],
            "company.linux.central-role-access@1",
        )
        self.assertEqual(
            requirement["external_refs"],
            ["example-regulatory-framework:IAM-01"],
        )
        instance_ids = requirement["technical_instance_ids"]
        for expected, statuses in (
            ("pass", ["pass"] * len(instance_ids)),
            ("fail", ["fail", *["pass"] * (len(instance_ids) - 1)]),
            ("unknown", ["unknown", *["pass"] * (len(instance_ids) - 1)]),
        ):
            with self.subTest(expected=expected):
                technical = [
                    {"instance_id": instance_id, "status": status}
                    for instance_id, status in zip(instance_ids, statuses, strict=True)
                ]
                requirement_results, objective_results = roll_up_plan_requirements(
                    plan,
                    technical,
                )
                self.assertEqual(requirement_results[0]["status"], expected)
                self.assertEqual(objective_results[0]["status"], expected)

    def test_realization_selection_refuses_multiple_applicable_candidates(self) -> None:
        private = Path(self.temporary.name) / "private"
        target = private / REALIZATION
        target.parent.mkdir(parents=True)
        shutil.copyfile(self.root / REALIZATION, target)
        self.mutate_private(
            target,
            lambda item: item["metadata"].update(
                id="company.linux.alternate-role-access",
                classification="restricted",
            ),
        )
        combined = (*sources(self.root), PolicySource("environment-private", private))
        subject = {
            "schema": "compliance.example/inventory-subject/v1",
            "id": "host/iam",
            "type": "linux-host",
            "status": "active",
            "labels": {"iam-profile": "company-linux"},
            "inventory": {
                "source": "verification-test",
                "external_id": "iam",
                "observed_at": "2026-09-04T00:00:00Z",
            },
        }
        groups = [{"id": "iam", "parents": [], "members": [subject["id"]]}]
        assignments = [{
            "id": "iam-objectives",
            "target": {"group": "iam"},
            "baselines": ["company.identity-access-objectives@1"],
        }]

        plan = render_plan(subject, groups, assignments, combined)

        self.assertEqual(plan["resolution"]["status"], "invalid")
        conflict = next(
            error
            for error in plan["resolution"]["errors"]
            if error["type"] == "multiple-control-realizations"
        )
        self.assertEqual(
            conflict["realizations"],
            [
                "company.linux.alternate-role-access@1",
                "company.linux.central-role-access@1",
            ],
        )

    def test_content_identity_is_independent_of_location_and_sensitive_to_bytes(self) -> None:
        original = source_tree_digest(ROOT / "policies")
        self.assertEqual(source_tree_digest(self.root), original)
        with (self.root / BASELINE).open("a") as stream:
            stream.write("\n")
        self.assertNotEqual(source_tree_digest(self.root), original)

    def test_boundary_rejects_reusable_controls_and_schemas_even_when_empty(self) -> None:
        for name in ("controls", "schemas"):
            with self.subTest(name=name):
                path = self.root / name
                path.mkdir()
                with self.assertRaisesRegex(ValueError, "must not own reusable"):
                    check_source_boundary(self.root)
                path.rmdir()

    def test_boundary_rejects_nested_rego(self) -> None:
        (self.root / "baselines/copied-helper.rego").write_text("package forbidden\n")
        with self.assertRaisesRegex(ValueError, "must not copy reusable Rego"):
            check_source_boundary(self.root)

    def test_boundary_rejects_broken_reusable_symlink(self) -> None:
        (self.root / "schemas").symlink_to(self.root / "absent")
        with self.assertRaisesRegex(ValueError, "must not own reusable"):
            check_source_boundary(self.root)

    def test_invalid_baseline_schema_is_rejected(self) -> None:
        self.mutate(BASELINE, lambda item: item.pop("spec"))
        self.assertIn("baseline-schema-invalid", self.error_types())

    def test_missing_reusable_control_is_rejected(self) -> None:
        self.mutate(BASELINE, lambda item: item["spec"]["controls"][0].update(implementation="synthetic.missing.control"))
        self.assertIn("unknown-control", self.error_types())

    def test_invalid_control_parameters_are_rejected(self) -> None:
        self.mutate(BASELINE, lambda item: item["spec"]["controls"][0].update(parameters={"required": "invalid"}))
        self.assertIn("control-parameters-invalid", self.error_types())

    def test_missing_requirement_reference_is_rejected(self) -> None:
        self.mutate(REALIZATION, lambda item: item["spec"]["requirement"].update(requirement="synthetic.missing.requirement@1"))
        self.assertIn("unknown-requirement", self.error_types())

    def test_requirement_digest_mismatch_is_rejected(self) -> None:
        self.mutate(REALIZATION, lambda item: item["spec"]["requirement"].update(digest="sha256:" + "0" * 64))
        self.assertIn("requirement-digest-mismatch", self.error_types())

    @staticmethod
    def mutate_private(path: Path, change) -> None:
        document = json.loads(path.read_text())
        change(document)
        path.write_text(json.dumps(document))


if __name__ == "__main__":
    unittest.main()
