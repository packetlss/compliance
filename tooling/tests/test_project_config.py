import copy
import tempfile
import unittest
from pathlib import Path

import yaml

from tools.project_config import (
    ProjectConfigError,
    discover_config,
    load_config,
    select_config,
)


VALID_CONFIG = """\
schema: compliance.example/project-config/v1alpha3
policySources:
  - name: company-shared
    path: ../shared/policies
paths:
  inventory: inventory
  assignments: assignments
  evidence: generated/evidence
  plan: generated/plans
  results: generated/results
  waivers: waivers
"""

MULTI_SOURCE_CONFIG = """\
schema: compliance.example/project-config/v1alpha3
policySources:
  - name: company-shared
    path: ../shared/policies
  - name: environment-private
    path: policy
    expectedContent:
      digestAlgorithm: compliance.example/policy-source-tree-digest/v1alpha1
      digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
paths:
  inventory: inventory
  assignments: assignments
  evidence: generated/evidence
  plan: generated/plans
  results: generated/results
  waivers: waivers
"""

PROJECT_REGISTRY = """\
schema: compliance.example/project-registry/v1alpha1
defaultProject: macbook
projects:
  macbook:
    config: projects/macbook.yaml
  mock-fleet:
    config: projects/mock-fleet.yaml
"""


class ProjectConfigTests(unittest.TestCase):
    def _write_project_registry(self, root: Path) -> Path:
        projects = root / "projects"
        projects.mkdir()
        (projects / "macbook.yaml").write_text(VALID_CONFIG, encoding="utf-8")
        (projects / "mock-fleet.yaml").write_text(
            VALID_CONFIG.replace("inventory: inventory", "inventory: mock-inventory"),
            encoding="utf-8",
        )
        source = root / "compliance.yaml"
        source.write_text(PROJECT_REGISTRY, encoding="utf-8")
        return source

    def test_discovers_nearest_config_and_resolves_paths_from_its_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nested = root / "operations" / "workstations"
            nested.mkdir(parents=True)
            source = root / "compliance.yaml"
            source.write_text(VALID_CONFIG, encoding="utf-8")

            config = select_config([], cwd=nested, validate_runtime=False)

            self.assertEqual(discover_config(nested), source.resolve())
            self.assertEqual(config.source, source.resolve())
            self.assertEqual(config.path("inventory"), (root / "inventory").resolve())
            self.assertEqual(config.policy_sources[0].path, (root.parent / "shared/policies").resolve())

    def test_explicit_config_wins_over_automatic_discovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            automatic = root / "compliance.yaml"
            automatic.write_text(VALID_CONFIG, encoding="utf-8")
            alternate = root / "alternate.yaml"
            alternate.write_text(
                VALID_CONFIG.replace("inventory: inventory", "inventory: alternate-inventory"),
                encoding="utf-8",
            )

            config = select_config(["--config", "alternate.yaml"], cwd=root, validate_runtime=False)

            self.assertEqual(config.source, alternate.resolve())
            self.assertEqual(config.path("inventory"), (root / "alternate-inventory").resolve())

    def test_resolves_named_policy_sources_and_optional_digest_pin(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "compliance.yaml"
            source.write_text(MULTI_SOURCE_CONFIG, encoding="utf-8")

            config = load_config(source)

        self.assertEqual(
            [policy_source.name for policy_source in config.policy_sources],
            ["company-shared", "environment-private"],
        )
        self.assertEqual(
            config.expected_content["environment-private"]["digest"],
            "sha256:" + "a" * 64,
        )

    def test_rejects_framework_declarations_inside_a_policy_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "compliance.yaml"
            source.write_text(
                VALID_CONFIG + "  frameworkDeclarations: ../shared/policies/framework-obligations\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProjectConfigError, "outside every policy-source path"):
                load_config(source)

    def test_rejects_legacy_and_named_policy_sources_together(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "compliance.yaml"
            source.write_text(
                MULTI_SOURCE_CONFIG.replace(
                    "  evidence: generated/evidence",
                    "  policies: legacy/policies\n  evidence: generated/evidence",
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProjectConfigError, "Additional properties"):
                load_config(source)

    def test_no_config_disables_discovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "compliance.yaml").write_text(VALID_CONFIG, encoding="utf-8")

            config = select_config(["--no-config"], cwd=root, validate_runtime=False)

            self.assertIsNone(config.source)
            self.assertEqual(config.paths, {})

    def test_rejects_unknown_path_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "compliance.yaml"
            source.write_text(
                VALID_CONFIG.replace("inventory: inventory", "inventroy: inventory"),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProjectConfigError, "inventroy"):
                load_config(source)

    def test_rejects_removed_configuration_output_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "compliance.yaml"
            source.write_text(
                VALID_CONFIG.replace(
                    "  results: generated/results\n",
                    "  results: generated/results\n"
                    "  configuration: generated/configuration\n",
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProjectConfigError, "configuration"):
                load_config(source)

    def test_rejects_incomplete_project_path_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "compliance.yaml"
            source.write_text(
                VALID_CONFIG.replace("  results: generated/results\n", ""),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProjectConfigError, "results.*required"):
                load_config(source)

    def test_rejects_project_without_waiver_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "compliance.yaml"
            source.write_text(
                VALID_CONFIG.replace("  waivers: waivers\n", ""),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProjectConfigError, "waivers.*required"):
                load_config(source)

    def test_project_registry_selects_default_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self._write_project_registry(root)

            config = select_config([], cwd=root, validate_runtime=False)

            self.assertEqual(config.project_registry_source, source.resolve())
            self.assertEqual(config.project_name, "macbook")
            self.assertEqual(config.default_project, "macbook")
            self.assertEqual(config.source, (root / "projects/macbook.yaml").resolve())
            self.assertEqual(sorted(config.available_projects), ["macbook", "mock-fleet"])

    def test_project_registry_selects_named_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_project_registry(root)

            config = select_config(["--project", "mock-fleet"], cwd=root, validate_runtime=False)

            self.assertEqual(config.project_name, "mock-fleet")
            self.assertEqual(
                config.path("inventory"),
                (root / "projects/mock-inventory").resolve(),
            )

    def test_project_registry_rejects_unknown_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_project_registry(root)

            with self.assertRaisesRegex(ProjectConfigError, "unknown project 'missing'"):
                select_config(["--project", "missing"], cwd=root, validate_runtime=False)

    def test_project_selection_requires_project_registry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "compliance.yaml").write_text(VALID_CONFIG, encoding="utf-8")

            with self.assertRaisesRegex(ProjectConfigError, "requires a project registry"):
                select_config(["--project", "macbook"], cwd=root, validate_runtime=False)

    def test_project_registry_default_must_name_a_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self._write_project_registry(root)
            source.write_text(
                PROJECT_REGISTRY.replace("defaultProject: macbook", "defaultProject: missing"),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProjectConfigError, "defaultProject 'missing'"):
                load_config(source)

    def test_registry_rejects_retired_and_invalid_discriminators(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self._write_project_registry(Path(temporary))
            for schema in ("compliance.example/workspace-config/v1alpha1",
                           "compliance.example/project-registry/v99", None):
                with self.subTest(schema=schema):
                    document = yaml.safe_load(PROJECT_REGISTRY)
                    document["schema"] = schema
                    source.write_text(yaml.safe_dump(document), encoding="utf-8")
                    with self.assertRaisesRegex(ProjectConfigError, "unsupported configuration schema"):
                        load_config(source)

    def test_registry_rejects_malformed_documents_and_references(self):
        valid = yaml.safe_load(PROJECT_REGISTRY)
        invalid = [
            {**valid, "unexpected": True},
            {key: value for key, value in valid.items() if key != "defaultProject"},
            {**valid, "defaultProject": ""},
            {**valid, "projects": {}},
            {**valid, "projects": {"Invalid Name": {"config": "project.yaml"}}},
        ]
        for reference in ({}, {"config": " "}, {"config": 42},
                          {"config": "project.yaml", "merge": True}, "project.yaml"):
            document = copy.deepcopy(valid)
            document["projects"]["macbook"] = reference
            invalid.append(document)
        with tempfile.TemporaryDirectory() as temporary:
            source = self._write_project_registry(Path(temporary))
            for document in invalid:
                with self.subTest(document=document):
                    source.write_text(yaml.safe_dump(document), encoding="utf-8")
                    with self.assertRaisesRegex(ProjectConfigError, "schema validation failed"):
                        load_config(source)
            for text, error in (("- not-an-object", "unsupported configuration schema"),
                                (PROJECT_REGISTRY + "---\n{}\n", "exactly one YAML document"),
                                ("projects: [", "cannot read configuration")):
                with self.subTest(text=text):
                    source.write_text(text, encoding="utf-8")
                    with self.assertRaisesRegex(ProjectConfigError, error):
                        load_config(source)

    def test_registry_rejects_missing_selected_config_and_nested_registry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self._write_project_registry(root)
            selected = root / "projects/macbook.yaml"
            selected.unlink()
            with self.assertRaisesRegex(ProjectConfigError, "cannot read configuration"):
                load_config(source)
            selected.write_text(PROJECT_REGISTRY, encoding="utf-8")
            with self.assertRaisesRegex(ProjectConfigError, "unsupported project config schema"):
                load_config(source)

    def test_direct_default_explicit_and_relocated_registry_inputs_are_equivalent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_project_registry(root)
            direct = load_config(root / "projects/macbook.yaml")
            relocated = root / "lookup/registry.yaml"
            relocated.parent.mkdir()
            relocated.write_text(
                PROJECT_REGISTRY.replace("config: projects/", "config: ../projects/")
                .replace("  mock-fleet:\n    config: ../projects/mock-fleet.yaml\n", ""),
                encoding="utf-8",
            )
            nested = root / "operations/nested"
            nested.mkdir(parents=True)
            for selected in (select_config([], cwd=nested, validate_runtime=False),
                             select_config(["--config", "../../compliance.yaml", "--project", "macbook"], cwd=nested, validate_runtime=False),
                             load_config(relocated)):
                with self.subTest(registry=selected.project_registry_source):
                    self.assertEqual(selected.schema, direct.schema)
                    self.assertEqual(selected.source, direct.source)
                    self.assertEqual(selected.paths, direct.paths)
                    self.assertEqual(selected.policy_sources, direct.policy_sources)
                    self.assertEqual(selected.composition_lock, direct.composition_lock)

    def test_project_cannot_be_selected_when_config_is_disabled(self):
        with self.assertRaisesRegex(ProjectConfigError, "cannot be used with --no-config"):
            select_config(["--no-config", "--project", "macbook"])


if __name__ == "__main__":
    unittest.main()
