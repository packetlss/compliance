import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


class JsonSchemaTests(unittest.TestCase):
    def test_every_json_schema_is_a_valid_draft_2020_12_schema(self):
        root = Path(__file__).resolve().parents[1]
        schemas = sorted(path for path in root.rglob("*.schema.json")
                         if not {".git", ".venv"}.intersection(path.parts))
        self.assertTrue(schemas)

        for path in schemas:
            with self.subTest(path=path.relative_to(root)):
                schema = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(
                    schema.get("$schema"),
                    "https://json-schema.org/draft/2020-12/schema",
                )
                Draft202012Validator.check_schema(schema)

    def test_platform_schema_contracts_use_canonical_role_uris(self):
        root = Path(__file__).resolve().parents[1]
        expected = {
            "tools/schemas/assessment-plan-v4.schema.json": "assessment-plan/v4",
            "tools/schemas/assessment-provenance-v1alpha1.schema.json": "assessment-provenance/v1alpha1",
            "tools/schemas/assessment-results-v4.schema.json": "assessment-results/v4",
            "tools/schemas/composition-lock-v1alpha1.schema.json": "composition-lock/v1alpha1",
            "tools/schemas/composition.schema.json": "composition/v1alpha1",
            "tools/schemas/framework-obligation-declaration-v1alpha1.schema.json": "framework-obligation-declaration/v1alpha1",
            "tools/schemas/policy-diff-set.schema.json": "policy-diff-set/v1alpha1",
            "tools/schemas/policy-diff.schema.json": "policy-diff/v1alpha1",
            "tools/schemas/policy-source-release-manifest.schema.json": "policy-source-release-manifest/v1",
            "tools/schemas/project-config-v1alpha3.schema.json": "project-config/v1alpha3",
            "tools/schemas/project-registry.schema.json": "project-registry/v1alpha1",
            "tools/schemas/tooling-release-manifest-v2.schema.json": "tooling-release-manifest/v2",
            "schemas/inventory/resource.schema.json": "inventory/v1alpha1",
            "schemas/waivers/resource.schema.json": "waivers/v1alpha1",
            "package-data/schemas/inventory/resource.schema.json": "inventory/v1alpha1",
            "package-data/schemas/waivers/resource.schema.json": "waivers/v1alpha1",
        }
        actual = {
            path.relative_to(root).as_posix(): json.loads(
                path.read_text(encoding="utf-8")
            )["$id"]
            for path in root.rglob("*.schema.json")
            if ".venv" not in path.parts
        }
        self.assertEqual(set(actual), set(expected))
        for relative, suffix in expected.items():
            self.assertEqual(
                actual[relative],
                f"https://compliance.example/schemas/platform/{suffix}.schema.json",
            )


if __name__ == "__main__":
    unittest.main()
