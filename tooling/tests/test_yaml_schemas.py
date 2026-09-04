import json
import re
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from tools.release_lock import RELEASE_LOCK_FILENAME, load_release_lock


SCHEMA_DIRECTIVE = re.compile(r"^# yaml-language-server: \$schema=(?P<path>\S+)$")
GITHUB_WORKFLOW_SCHEMA = "https://json.schemastore.org/github-workflow.json"


class YamlSchemaDeclarationTests(unittest.TestCase):
    def test_every_authored_yaml_file_declares_and_satisfies_a_schema(self):
        root = Path(__file__).resolve().parents[1]
        yaml_files = sorted(
            path
            for pattern in ("*.yaml", "*.yml")
            for path in root.rglob(pattern)
            if not {".git", ".venv", "generated"}.intersection(path.parts)
        )
        self.assertTrue(yaml_files)

        for path in yaml_files:
            with self.subTest(path=path.relative_to(root)):
                if path.name == RELEASE_LOCK_FILENAME:
                    load_release_lock(path)
                    continue

                text = path.read_text(encoding="utf-8")
                first_line = text.splitlines()[0]
                match = SCHEMA_DIRECTIVE.fullmatch(first_line)
                self.assertIsNotNone(match, "missing yaml-language-server schema directive")
                schema_reference = match.group("path")
                documents = list(yaml.safe_load_all(text))
                self.assertTrue(documents)

                if ".github" in path.parts and "workflows" in path.parts:
                    self.assertEqual(
                        schema_reference,
                        GITHUB_WORKFLOW_SCHEMA,
                        "GitHub workflows must declare the canonical external workflow schema",
                    )
                    # GitHub validates workflow semantics when the workflow is loaded/run.
                    # Keep this repository test offline rather than fetching a mutable
                    # external schema during the unit suite.
                    continue

                schema_path = (path.parent / schema_reference).resolve()
                self.assertTrue(schema_path.is_file(), f"schema does not exist: {schema_path}")
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                validator = Draft202012Validator(schema, format_checker=FormatChecker())
                for index, document in enumerate(documents, start=1):
                    errors = sorted(
                        validator.iter_errors(document),
                        key=lambda error: tuple(str(part) for part in error.absolute_path),
                    )
                    self.assertEqual(
                        errors,
                        [],
                        f"document {index}: "
                        + "; ".join(error.message for error in errors),
                    )


if __name__ == "__main__":
    unittest.main()
