"""Reusable-source contracts, independent of any adopting project or policy."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from tools.policy_sources import PolicySource
from tools.render_plan import load_policy_catalogs, validate_rego_entrypoints

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ROOT / "policies"
EXPECTED_CONTROL_IDS = {
    "aws.account.number_at_least",
    "aws.account.setting_equals",
    "aws.s3.account_public_access_block_required",
    "linux.access.setting_equals",
    "linux.packages.required",
    "linux.sysctl.required",
    "macos.homebrew.formulae_required",
    "macos.security.setting_equals",
    "macos.system.minimum_version",
    "saas.tenant.number_at_least",
    "saas.tenant.setting_equals",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def external_refs(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "external_refs" and isinstance(item, list):
                yield from item
            else:
                yield from external_refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from external_refs(item)


class PolicyResourceTests(unittest.TestCase):
    def test_all_library_schemas_are_valid(self):
        schemas = sorted(POLICIES.rglob("*.schema.json"))
        schemas.extend(sorted((ROOT / "release").glob("*.schema.json")))
        self.assertTrue(schemas)
        for path in schemas:
            with self.subTest(path=path.relative_to(ROOT)):
                Draft202012Validator.check_schema(read_json(path))

    def test_reusable_catalog_and_rego_entrypoints(self):
        source = PolicySource("control-library", POLICIES)
        controls, baselines, errors = load_policy_catalogs(source)
        self.assertEqual(errors, [])
        self.assertEqual(baselines, {})
        manifests = sorted(POLICIES.rglob("control.json"))
        expected = {read_json(path)["metadata"]["id"] for path in manifests}
        self.assertEqual(expected, EXPECTED_CONTROL_IDS)
        self.assertEqual(len(expected), len(manifests), "control identities must be unique")
        self.assertEqual(set(controls), expected)
        self.assertEqual(validate_rego_entrypoints(source, controls), [])

    def test_schema_identities_are_unique(self):
        schemas = sorted(POLICIES.rglob("*.schema.json"))
        identities = [
            document["$id"]
            for path in schemas
            if "$id" in (document := read_json(path))
        ]
        self.assertTrue(identities)
        self.assertEqual(len(identities), len(set(identities)))

    def test_broken_library_contracts_are_rejected(self):
        # Mutate copies of this producer's actual resources. No consumer policy
        # or environment data is needed to prove the rejection boundary.
        cases = (
            ("controls/linux/sysctl-required/parameters.schema.json", None,
             "control-parameters-schema-unavailable"),
            ("schemas/evidence/linux-sysctl-v1.schema.json", None,
             "control-evidence-schema-missing"),
            ("controls/linux/sysctl-required/parameters.schema.json", {"type": "invalid"},
             "control-parameters-schema-invalid"),
            ("controls/linux/sysctl-required/control.json", {},
             "control-manifest-schema-invalid"),
        )
        for relative, replacement, expected in cases:
            with self.subTest(path=relative, expected=expected), tempfile.TemporaryDirectory() as temporary:
                policy = Path(temporary) / "policy"
                shutil.copytree(POLICIES, policy)
                target = policy / relative
                if replacement is None:
                    target.unlink()
                else:
                    target.write_text(json.dumps(replacement), encoding="utf-8")
                _, _, errors = load_policy_catalogs(PolicySource("control-library", policy))
                self.assertIn(expected, {error["type"] for error in errors}, errors)

    def test_configuration_facet_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            policy = Path(temporary) / "policy"
            shutil.copytree(POLICIES, policy)
            manifest_path = policy / "controls/linux/sysctl-required/control.json"
            manifest = read_json(manifest_path)
            manifest["spec"]["configuration"] = {
                "intent_type": "linux.sysctl.values/v1",
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            _, _, errors = load_policy_catalogs(PolicySource("control-library", policy))
            self.assertIn(
                "control-manifest-schema-invalid",
                {error["type"] for error in errors},
                errors,
            )

    def test_missing_rego_entrypoint_is_rejected(self):
        source = PolicySource("control-library", POLICIES)
        controls, _, errors = load_policy_catalogs(source)
        self.assertEqual(errors, [])
        controls["linux.sysctl.required"]["spec"]["entrypoint"] = "data.compliance.missing.result"
        self.assertTrue(validate_rego_entrypoints(source, controls))


class PolicySourceBoundaryTests(unittest.TestCase):
    def test_only_complete_reusable_controls_shared_rego_and_schemas_are_present(self):
        expected_control_files = {
            "control.json", "parameters.schema.json", "policy.rego", "policy_test.rego",
        }
        control_manifests = sorted((POLICIES / "controls").glob("*/*/control.json"))
        self.assertTrue(control_manifests)
        for manifest_path in control_manifests:
            with self.subTest(path=manifest_path.parent.relative_to(ROOT)):
                actual = {path.name for path in manifest_path.parent.iterdir() if path.is_file()}
                self.assertEqual(actual, expected_control_files)
                self.assertEqual(read_json(manifest_path)["kind"], "Control")

        expected_control_paths = {
            path
            for manifest_path in control_manifests
            for path in (
                manifest_path,
                manifest_path.parent / "parameters.schema.json",
                manifest_path.parent / "policy.rego",
                manifest_path.parent / "policy_test.rego",
            )
        }
        expected_control_paths.add(POLICIES / "controls/common/result.rego")
        actual_control_paths = {
            path for path in (POLICIES / "controls").rglob("*") if path.is_file()
        }
        self.assertEqual(actual_control_paths, expected_control_paths)

        schema_root = POLICIES / "schemas"
        schema_files = {path for path in schema_root.rglob("*") if path.is_file()}
        self.assertTrue(schema_files)
        self.assertTrue(all(path.name.endswith(".schema.json") for path in schema_files))
        self.assertTrue(all(path.parent.name in {"policy", "evidence"} for path in schema_files))
        self.assertFalse((schema_root / "configuration").exists())

        actual_policy_files = {path for path in POLICIES.rglob("*") if path.is_file()}
        self.assertEqual(actual_policy_files, actual_control_paths | schema_files)

    def test_controls_are_assessment_only_and_assurance_references_remain_available(self):
        manifests = sorted((POLICIES / "controls").glob("*/*/control.json"))
        self.assertEqual(
            {read_json(path)["metadata"]["id"] for path in manifests},
            EXPECTED_CONTROL_IDS,
        )
        for path in manifests:
            with self.subTest(path=path.relative_to(ROOT)):
                spec = read_json(path)["spec"]
                self.assertNotIn("configuration", spec)
                self.assertNotIn("intent_type", spec)
                self.assertEqual(spec["parameters_schema"], "parameters.schema.json")

        policy_schemas = POLICIES / "schemas/policy"
        for name in ("baseline.schema.json", "control-realization.schema.json"):
            with self.subTest(schema=name):
                control_instance = read_json(policy_schemas / name)["$defs"]["controlInstance"]
                self.assertEqual(
                    set(control_instance["required"]),
                    {"instance_id", "implementation"},
                )
                self.assertIn("parameters", control_instance["properties"])

        for name in (
            "baseline-overlay.schema.json",
            "baseline.schema.json",
            "control-realization.schema.json",
            "control-requirement.schema.json",
            "requirement-baseline.schema.json",
        ):
            with self.subTest(schema=name):
                self.assertTrue((policy_schemas / name).is_file())

    def test_no_adoption_specific_resources_are_authored_in_this_source(self):
        adoption_kinds = {
            "Baseline", "BaselineOverlay", "ControlRequirement", "ControlRealization",
            "RequirementBaseline",
        }
        authored_resources = [
            path for path in POLICIES.rglob("*.json")
            if not path.name.endswith(".schema.json")
        ]
        self.assertTrue(authored_resources)
        for path in authored_resources:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn(read_json(path).get("kind"), adoption_kinds)

    def test_external_adoption_mappings_remain_outside_this_source(self):
        for path in POLICIES.rglob("*.json"):
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertEqual(list(external_refs(read_json(path))), [])


if __name__ == "__main__":
    unittest.main()
