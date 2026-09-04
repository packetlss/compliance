import tempfile
import unittest
from pathlib import Path

from tools.project_config import (
    ProjectConfigError,
    discover_config,
    load_config,
    select_config,
)


VALID_CONFIG = """\
schema: compliance.example/project-config/v1alpha1
paths:
  inventory: inventory
  assignments: assignments
  policies: ../shared/policies
  evidence: generated/evidence
  plan: generated/plans
  results: generated/results
  waivers: waivers
  resourceSchema: schemas/inventory.json
"""

MULTI_SOURCE_CONFIG = """\
schema: compliance.example/project-config/v1alpha1
policySources:
  - name: company-shared
    path: ../shared/policies
  - name: environment-private
    path: policy
    digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
paths:
  inventory: inventory
  assignments: assignments
  evidence: generated/evidence
  plan: generated/plans
  results: generated/results
  waivers: waivers
  resourceSchema: schemas/inventory.json
"""

WORKSPACE_CONFIG = """\
schema: compliance.example/workspace-config/v1alpha1
defaultProject: macbook
projects:
  macbook:
    config: projects/macbook.yaml
  mock-fleet:
    config: projects/mock-fleet.yaml
"""


class ProjectConfigTests(unittest.TestCase):
    def _write_workspace(self, root: Path) -> Path:
        projects = root / "projects"
        projects.mkdir()
        (projects / "macbook.yaml").write_text(VALID_CONFIG, encoding="utf-8")
        (projects / "mock-fleet.yaml").write_text(
            VALID_CONFIG.replace("inventory: inventory", "inventory: mock-inventory"),
            encoding="utf-8",
        )
        source = root / "compliance.yaml"
        source.write_text(WORKSPACE_CONFIG, encoding="utf-8")
        return source

    def test_discovers_nearest_config_and_resolves_paths_from_its_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nested = root / "operations" / "workstations"
            nested.mkdir(parents=True)
            source = root / "compliance.yaml"
            source.write_text(VALID_CONFIG, encoding="utf-8")

            config = select_config([], cwd=nested)

            self.assertEqual(discover_config(nested), source.resolve())
            self.assertEqual(config.source, source.resolve())
            self.assertEqual(config.path("inventory"), (root / "inventory").resolve())
            self.assertEqual(config.path("policies"), (root.parent / "shared/policies").resolve())

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

            config = select_config(["--config", "alternate.yaml"], cwd=root)

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
            config.policy_sources[1].expected_digest,
            "sha256:" + "a" * 64,
        )

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

            with self.assertRaisesRegex(ProjectConfigError, "valid under each"):
                load_config(source)

    def test_no_config_disables_discovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "compliance.yaml").write_text(VALID_CONFIG, encoding="utf-8")

            config = select_config(["--no-config"], cwd=root)

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

    def test_workspace_selects_default_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self._write_workspace(root)

            config = select_config([], cwd=root)

            self.assertEqual(config.workspace_source, source.resolve())
            self.assertEqual(config.project_name, "macbook")
            self.assertEqual(config.default_project, "macbook")
            self.assertEqual(config.source, (root / "projects/macbook.yaml").resolve())
            self.assertEqual(sorted(config.available_projects), ["macbook", "mock-fleet"])

    def test_workspace_selects_named_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_workspace(root)

            config = select_config(["--project", "mock-fleet"], cwd=root)

            self.assertEqual(config.project_name, "mock-fleet")
            self.assertEqual(
                config.path("inventory"),
                (root / "projects/mock-inventory").resolve(),
            )

    def test_workspace_rejects_unknown_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_workspace(root)

            with self.assertRaisesRegex(ProjectConfigError, "unknown project 'missing'"):
                select_config(["--project", "missing"], cwd=root)

    def test_project_selection_requires_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "compliance.yaml").write_text(VALID_CONFIG, encoding="utf-8")

            with self.assertRaisesRegex(ProjectConfigError, "requires a workspace"):
                select_config(["--project", "macbook"], cwd=root)

    def test_workspace_default_must_name_a_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self._write_workspace(root)
            source.write_text(
                WORKSPACE_CONFIG.replace("defaultProject: macbook", "defaultProject: missing"),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProjectConfigError, "defaultProject 'missing'"):
                load_config(source)

    def test_project_cannot_be_selected_when_config_is_disabled(self):
        with self.assertRaisesRegex(ProjectConfigError, "cannot be used with --no-config"):
            select_config(["--no-config", "--project", "macbook"])



if __name__ == "__main__":
    unittest.main()
