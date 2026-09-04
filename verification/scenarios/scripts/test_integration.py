"""Exercise destination-local assembly and fail-closed guards."""

import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import integration


def git(root, *arguments):
    return subprocess.check_output(
        ["git", "-C", str(root), *arguments],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def init(root):
    root.mkdir(parents=True)
    git(root, "init", "--quiet")
    git(root, "config", "user.name", "Integration test")
    git(root, "config", "user.email", "integration@example.invalid")


def commit(root):
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "Synthetic fixture")
    return git(root, "rev-parse", "HEAD")


class PersistentIntegrationContractTests(unittest.TestCase):
    def test_assembly_uses_only_explicit_destination_roots(self):
        self.assertEqual(
            integration.ASSEMBLY_ROOTS,
            (
                Path("tooling"),
                Path("policy-sources/control-library"),
                Path("policy-sources/verification-policy"),
                Path("projects"),
                Path("verification/fixtures/iam-private-boundary"),
                Path("verification/scenarios"),
            ),
        )
        self.assertFalse(
            (integration.SCENARIOS_ROOT / "integration/components.json").exists()
        )

    def test_registry_excludes_retired_configuration_project(self):
        registry = (
            integration.SCENARIOS_ROOT / "integration/compliance.yaml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("configuration-demo", registry)
        for project in (
            "linux-hardening-rollout",
            "mock-fleet",
            "server-personas",
            "iam-realization",
        ):
            self.assertIn(f"  {project}:\n", registry)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="scenario-integration-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.repository = self.root / "repository"
        init(self.repository)
        self._write_fixture()
        commit(self.repository)
        repository_patch = patch.object(
            integration, "REPOSITORY_ROOT", self.repository
        )
        repository_patch.start()
        self.addCleanup(repository_patch.stop)
        scenarios_patch = patch.object(
            integration,
            "SCENARIOS_ROOT",
            self.repository / "verification/scenarios",
        )
        scenarios_patch.start()
        self.addCleanup(scenarios_patch.stop)
        self.assembly = self.root / "assembly"

    def _write_fixture(self):
        for source in integration.ASSEMBLY_ROOTS:
            (self.repository / source).mkdir(parents=True, exist_ok=True)
            (self.repository / source / "owned-source").write_text(
                f"{source.as_posix()}\n"
            )
        fixture = self.repository / integration.FIXTURE_PATH
        (fixture / "policy/realizations").mkdir(parents=True)
        (fixture / "policy/realizations/private.json").write_text("{}\n")
        scenario_integration = self.repository / "verification/scenarios/integration"
        scenario_integration.mkdir(parents=True)
        (scenario_integration / "compliance.yaml").write_text("synthetic registry\n")

    def assemble(self):
        with contextlib.redirect_stdout(io.StringIO()):
            integration.assemble(self.assembly)

    def test_exact_committed_destination_inputs_and_no_git_metadata(self):
        self.assemble()
        self.assertFalse(any(path.name == ".git" for path in self.assembly.rglob(".git")))
        self.assertEqual(
            (self.assembly / "compliance.yaml").read_text(),
            "synthetic registry\n",
        )
        self.assertEqual(
            (
                self.assembly
                / "external-sources/environment-private/realizations/private.json"
            ).read_text(),
            "{}\n",
        )
        self.assertFalse(
            (self.assembly / integration.PRIVATE_POLICY_PATH).exists()
        )

    def test_uncommitted_and_untracked_inputs_are_not_copied(self):
        selected = self.repository / "projects/owned-source"
        selected.write_text("uncommitted change\n")
        (self.repository / "projects/untracked").write_text("untracked\n")
        with self.assertRaisesRegex(ValueError, "commit destination changes"):
            integration.assemble(self.assembly)

    def test_git_root_and_git_ancestor_are_rejected(self):
        for root in (self.repository, self.repository / "nested"):
            root.mkdir(exist_ok=True)
            with self.subTest(root=root), self.assertRaisesRegex(ValueError, "Git|git"):
                integration.require_non_git_root(root)

    def test_extra_root_entry_is_rejected(self):
        self.assemble()
        (self.assembly / "undeclared-input").mkdir()
        with self.assertRaisesRegex(ValueError, "only the registry"):
            integration.verify(self.assembly)

    def test_registry_change_is_rejected(self):
        self.assemble()
        (self.assembly / "compliance.yaml").write_text("changed registry\n")
        with self.assertRaisesRegex(ValueError, "registry differs"):
            integration.verify(self.assembly)

    def test_fixture_private_path_reintroduction_is_rejected(self):
        self.assemble()
        path = self.assembly / integration.PRIVATE_POLICY_PATH
        path.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "fixture policy path"):
            integration.verify(self.assembly)

    def test_assembly_byte_change_is_rejected(self):
        self.assemble()
        (self.assembly / "projects/owned-source").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "differs from the transformed"):
            integration.verify(self.assembly)


if __name__ == "__main__":
    unittest.main()
