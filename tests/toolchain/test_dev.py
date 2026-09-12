from __future__ import annotations

import importlib.util
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest import mock

SOURCE = Path(__file__).resolve().parents[2] / "toolchain/dev.py"
SPEC = importlib.util.spec_from_file_location("compliance_dev", SOURCE)
assert SPEC and SPEC.loader
dev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dev)


REPOSITORY_ROOT = SOURCE.parents[1]
DEV_SCRIPT = REPOSITORY_ROOT / "scripts/dev"


def run_dev(*arguments: str, cwd: Path | None = None, env=None):
    return subprocess.run(
        [str(DEV_SCRIPT), *arguments],
        cwd=cwd or REPOSITORY_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def temporary_dev_repository(root: Path, *, initialized: bool) -> tuple[Path, Path]:
    (root / "scripts").mkdir()
    (root / "toolchain").mkdir()
    shutil.copy2(DEV_SCRIPT, root / "scripts/dev")
    shutil.copy2(SOURCE, root / "toolchain/dev.py")
    shutil.copy2(
        REPOSITORY_ROOT / "toolchain/versions.env",
        root / "toolchain/versions.env",
    )
    cache = root / "cache"
    if initialized:
        bin_directory = root / ".dev/venv/bin"
        bin_directory.mkdir(parents=True)
        (bin_directory / "python").symlink_to(sys.executable)
        entrypoint = bin_directory / "compliance"
        entrypoint.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "print(json.dumps({'arguments': sys.argv[1:], "
            "'cwd': os.getcwd(), 'path': os.environ['PATH'].split(os.pathsep)}))\n"
        )
        entrypoint.chmod(0o755)
        pins = dev.pins()
        os_name, arch, _, _ = dev.target()
        opa = cache / f"opa-{pins['OPA_VERSION']}" / f"{os_name}-{arch}" / "opa"
        opa.parent.mkdir(parents=True)
        opa.write_text("fake pinned OPA")
        opa.chmod(0o755)
    return root / "scripts/dev", cache


class PortabilityTests(unittest.TestCase):
    def test_paths_with_spaces_and_macos_temporary_roots(self):
        with tempfile.TemporaryDirectory(prefix="compliance path with spaces ") as temporary:
            root = Path(temporary)
            (root / "nested path").mkdir()
            (root / "nested path/file.json").write_text("{}")
            self.assertEqual(dev.portability_collisions(root), [])

    def test_case_collision_is_rejected(self):
        self.assertEqual(len(dev.normalized_name_collisions(["Policy.json", "policy.json"])), 1)

    def test_unicode_normalization_collision_is_rejected(self):
        self.assertEqual(len(dev.normalized_name_collisions(["café.json", "cafe\N{COMBINING ACUTE ACCENT}.json"])), 1)


class CliAdapterTests(unittest.TestCase):
    def test_arguments_pass_through_unchanged_from_repository_root(self):
        with tempfile.TemporaryDirectory(prefix="compliance dev cli ") as temporary:
            root = Path(temporary)
            script, cache = temporary_dev_repository(root, initialized=True)
            invocation_directory = root / "nested/caller"
            invocation_directory.mkdir(parents=True)
            environment = os.environ.copy()
            environment["COMPLIANCE_DEV_CACHE"] = str(cache)
            arguments = ("--literal=one", "value with spaces", "--", "-x", "")

            result = subprocess.run(
                [str(script), "cli", *arguments],
                cwd=invocation_directory,
                env=environment,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            document = json.loads(result.stdout)
            self.assertEqual(document["arguments"], list(arguments))
            self.assertEqual(Path(document["cwd"]), root.resolve())
            self.assertEqual(Path(document["path"][0]), next(cache.glob("opa-*/**/opa")).parent)

    def test_root_config_discovery_and_representative_coverage_command(self):
        config_result = run_dev("cli", "config", "list", "--format", "json")
        self.assertEqual(config_result.returncode, 0, config_result.stderr)
        config = json.loads(config_result.stdout)
        self.assertEqual(
            Path(config["project_registry"]), REPOSITORY_ROOT / "compliance.yaml"
        )
        self.assertEqual(config["selected_project"], "mock-fleet")
        self.assertEqual(
            [project["name"] for project in config["projects"]],
            ["mock-fleet", "server-personas"],
        )

        coverage_result = run_dev(
            "cli", "coverage", "list", "assets", "--format", "json"
        )
        self.assertEqual(coverage_result.returncode, 0, coverage_result.stderr)
        coverage = json.loads(coverage_result.stdout)
        self.assertEqual(
            [asset["asset_id"] for asset in coverage["assets"]],
            [
                "cloud-account/aws-111122223333",
                "cloud-account/aws-444455556666",
                "saas/acme-projects/company",
            ],
        )

    def test_real_cli_nonzero_status_is_propagated(self):
        result = run_dev("cli", "not-a-compliance-command")
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid choice", result.stderr)

    def test_missing_environment_fails_without_implicit_setup_or_install(self):
        with tempfile.TemporaryDirectory(prefix="compliance dev missing ") as temporary:
            root = Path(temporary)
            script, cache = temporary_dev_repository(root, initialized=False)
            environment = os.environ.copy()
            environment["COMPLIANCE_DEV_CACHE"] = str(cache)

            result = subprocess.run(
                [str(script), "cli", "config", "list"],
                cwd=root,
                env=environment,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("run scripts/dev setup", result.stderr)
            self.assertFalse((root / ".dev").exists())
            self.assertFalse(cache.exists())


class CheckCommandTests(unittest.TestCase):
    def check(self, *, area: str, verbose: bool = False, selection: list[str] | None = None, returncodes: list[int] | None = None):
        calls = []
        results = iter(returncodes) if returncodes is not None else itertools.repeat(0)

        def record(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(returncode=next(results))

        with mock.patch.object(dev, "selected", return_value=(Path("/managed/uv"), Path("/managed/opa"))), mock.patch.object(dev, "run", side_effect=record):
            result = dev.check(SimpleNamespace(area=area, verbose=verbose, selection=selection or []))
        return result, calls

    def test_default_checks_use_compact_unittest_output(self):
        for area, command in dev.COMMANDS.items():
            with self.subTest(area=area):
                result, calls = self.check(area=area)
                self.assertEqual(result, 0)
                self.assertEqual(calls[0][0], ["/managed/uv", "run", "--project", "tooling", "--frozen", *command])
                self.assertNotIn("-v", calls[0][0])

    def test_verbose_checks_request_per_test_output(self):
        result, calls = self.check(area="policy", verbose=True)
        self.assertEqual(result, 0)
        self.assertEqual(calls[0][0][-1], "-v")

    def test_named_tooling_selection_is_preserved(self):
        result, calls = self.check(area="tooling", selection=["test_canonical_json.py", "test_schemas.py"])
        self.assertEqual(result, 0)
        self.assertEqual([call[0][-2:] for call in calls], [["-p", "test_canonical_json.py"], ["-p", "test_schemas.py"]])
        self.assertTrue(all("-v" not in call[0] for call in calls))

    def test_named_tooling_selection_supports_verbose_output(self):
        result, calls = self.check(area="tooling", verbose=True, selection=["test_canonical_json.py"])
        self.assertEqual(result, 0)
        self.assertEqual(calls[0][0][-3:], ["-p", "test_canonical_json.py", "-v"])

    def test_failing_check_status_is_propagated(self):
        result, calls = self.check(area="tooling", selection=["test_canonical_json.py", "test_schemas.py"], returncodes=[1])
        self.assertEqual(result, 1)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
