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


if __name__ == "__main__":
    unittest.main()
