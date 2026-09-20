from __future__ import annotations

import contextlib
import importlib.util
import hashlib
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from io import StringIO
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
INTEGRATION_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/current-main-integration.yml"
INTEGRATION_WORKFLOW_VALIDATOR = REPOSITORY_ROOT / "scripts/validate-current-main-integration.sh"


def run_dev(*arguments: str, cwd: Path | None = None, env=None):
    return subprocess.run(
        [str(DEV_SCRIPT), *arguments],
        cwd=cwd or REPOSITORY_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def isolated_environment(cache: Path):
    environment = os.environ.copy()
    environment.pop(dev.LOCK_HELD_ENV, None)
    environment["COMPLIANCE_DEV_CACHE"] = str(cache)
    return environment


def temporary_dev_repository(root: Path, *, initialized: bool) -> tuple[Path, Path]:
    (root / "scripts").mkdir()
    (root / "toolchain").mkdir()
    shutil.copy2(DEV_SCRIPT, root / "scripts/dev")
    shutil.copy2(SOURCE, root / "toolchain/dev.py")
    shutil.copy2(
        REPOSITORY_ROOT / "toolchain/versions.env",
        root / "toolchain/versions.env",
    )
    (root / "tooling").mkdir()
    shutil.copy2(REPOSITORY_ROOT / "tooling/pyproject.toml", root / "tooling/pyproject.toml")
    shutil.copy2(REPOSITORY_ROOT / "tooling/uv.lock", root / "tooling/uv.lock")
    cache = root / "cache"
    pins = dev.pins()
    os_name, arch, checksum_key, _ = dev.target()
    uv = cache / f"uv-{pins['UV_VERSION']}" / "uv"
    uv.parent.mkdir(parents=True)
    uv.write_text(
        f"#!{sys.executable}\n"
        "import os, pathlib, sys, time\n"
        f"VERSION = {pins['UV_VERSION']!r}\n"
        "if sys.argv[1:] == ['--version']:\n"
        "    print(f'uv {VERSION} test')\n"
        "    raise SystemExit(0)\n"
        "if len(sys.argv) > 1 and sys.argv[1] == 'sync':\n"
        "    log = os.environ.get('FAKE_SYNC_LOG')\n"
        "    if log: pathlib.Path(log).parent.mkdir(parents=True, exist_ok=True); pathlib.Path(log).open('a').write('sync\\n')\n"
        "    started = os.environ.get('FAKE_SYNC_STARTED')\n"
        "    if started: pathlib.Path(started).write_text('started')\n"
        "    release = os.environ.get('FAKE_SYNC_RELEASE')\n"
        "    if release:\n"
        "        while not pathlib.Path(release).exists(): time.sleep(0.01)\n"
        "    if os.environ.get('FAKE_SYNC_FAIL'):\n"
        "        raise SystemExit(int(os.environ['FAKE_SYNC_FAIL']))\n"
        "    bin_directory = pathlib.Path(os.environ['UV_PROJECT_ENVIRONMENT']) / 'bin'\n"
        "    bin_directory.mkdir(parents=True, exist_ok=True)\n"
        "    python = bin_directory / 'python'; python.unlink(missing_ok=True)\n"
        f"    python.write_text(\"#!{sys.executable}\\nimport os, sys\\nif sys.argv[1:] == ['-c', 'import platform; print(platform.python_version())']: print({pins['PYTHON_VERSION']!r})\\nelse: os.execv({sys.executable!r}, [{sys.executable!r}, *sys.argv[1:]])\\n\")\n"
        "    python.chmod(0o755)\n"
        "    entrypoint = bin_directory / 'compliance'\n"
        f"    entrypoint.write_text(\"#!{sys.executable}\\nimport json, os, pathlib, sys, time\\nstarted = os.environ.get('FAKE_CLI_STARTED')\\nif started: pathlib.Path(started).write_text('started')\\nrelease = os.environ.get('FAKE_CLI_RELEASE')\\nif release:\\n    while not pathlib.Path(release).exists(): time.sleep(0.01)\\nprint(json.dumps({{'arguments': sys.argv[1:], 'cwd': os.getcwd(), 'path': os.environ['PATH'].split(os.pathsep)}}))\\n\")\n"
        "    entrypoint.chmod(0o755)\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(2)\n"
    )
    uv.chmod(0o755)
    opa = cache / f"opa-{pins['OPA_VERSION']}" / f"{os_name}-{arch}" / "opa"
    opa.parent.mkdir(parents=True)
    opa_contents = f"#!{sys.executable}\nprint('Version: {pins['OPA_VERSION']}')\n".encode()
    opa.write_bytes(opa_contents)
    opa.chmod(0o755)
    versions = root / "toolchain/versions.env"
    versions.write_text(
        versions.read_text().replace(
            f"{checksum_key}={pins[checksum_key]}",
            f"{checksum_key}={hashlib.sha256(opa_contents).hexdigest()}",
        )
    )
    script = root / "scripts/dev"
    if initialized:
        environment = isolated_environment(cache)
        result = subprocess.run([str(script), "setup"], cwd=root, env=environment, text=True, capture_output=True)
        if result.returncode:
            raise AssertionError(result.stderr)
    return script, cache


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
            environment = isolated_environment(cache)
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
            ["alder-forge-dcc-level3", "mock-fleet", "server-personas"],
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

    def test_missing_environment_is_repaired_before_cli_runs(self):
        with tempfile.TemporaryDirectory(prefix="compliance dev missing ") as temporary:
            root = Path(temporary)
            script, cache = temporary_dev_repository(root, initialized=False)
            environment = isolated_environment(cache)

            result = subprocess.run(
                [str(script), "cli", "config", "list"],
                cwd=root,
                env=environment,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / ".dev/setup-readiness.json").is_file())
            self.assertTrue((root / ".dev/venv/bin/compliance").is_file())
            self.assertTrue(cache.exists())

    def test_doctor_reports_missing_state_without_creating_it(self):
        with tempfile.TemporaryDirectory(prefix="compliance dev doctor ") as temporary:
            root = Path(temporary)
            script, cache = temporary_dev_repository(root, initialized=False)
            environment = isolated_environment(cache)

            result = subprocess.run([str(script), "doctor"], cwd=root, env=environment, text=True, capture_output=True)

            self.assertEqual(result.returncode, 1)
            self.assertIn("missing or stale", result.stderr)
            self.assertFalse((root / ".dev").exists())

    def test_stale_readiness_metadata_causes_a_frozen_resync(self):
        with tempfile.TemporaryDirectory(prefix="compliance dev stale ") as temporary:
            root = Path(temporary)
            script, cache = temporary_dev_repository(root, initialized=True)
            (root / "tooling/pyproject.toml").write_text(
                (root / "tooling/pyproject.toml").read_text() + "\n"
            )
            log = root / "sync.log"
            environment = isolated_environment(cache)
            environment.update(COMPLIANCE_DEV_CACHE=str(cache), FAKE_SYNC_LOG=str(log))

            result = subprocess.run([str(script), "cli", "config", "list"], cwd=root, env=environment, text=True, capture_output=True)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(log.read_text().splitlines(), ["sync"])

    def test_failed_setup_prevents_the_requested_cli_from_running(self):
        with tempfile.TemporaryDirectory(prefix="compliance dev failed setup ") as temporary:
            root = Path(temporary)
            script, cache = temporary_dev_repository(root, initialized=False)
            environment = isolated_environment(cache)
            environment.update(COMPLIANCE_DEV_CACHE=str(cache), FAKE_SYNC_FAIL="17")

            result = subprocess.run([str(script), "cli", "config", "list"], cwd=root, env=environment, text=True, capture_output=True)

            self.assertEqual(result.returncode, 17)
            self.assertIn("managed setup failed", result.stderr)
            self.assertFalse((root / ".dev/setup-readiness.json").exists())
            self.assertFalse((root / ".dev/venv/bin/compliance").exists())

    def test_concurrent_cli_callers_wait_for_one_successful_setup(self):
        with tempfile.TemporaryDirectory(prefix="compliance dev concurrent ") as temporary:
            root = Path(temporary)
            script, cache = temporary_dev_repository(root, initialized=False)
            started, release, log = root / "started", root / "release", root / "sync.log"
            environment = isolated_environment(cache)
            environment.update(
                COMPLIANCE_DEV_CACHE=str(cache),
                FAKE_SYNC_STARTED=str(started),
                FAKE_SYNC_RELEASE=str(release),
                FAKE_SYNC_LOG=str(log),
            )
            first = subprocess.Popen([str(script), "cli", "config", "list"], cwd=root, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for _ in range(100):
                if started.exists():
                    break
                time.sleep(0.01)
            self.assertTrue(started.exists(), "first setup did not start")
            second = subprocess.Popen([str(script), "cli", "config", "list"], cwd=root, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(0.05)
            self.assertIsNone(second.poll(), "second caller did not wait for setup")
            release.write_text("release")
            first_stdout, first_stderr = first.communicate(timeout=10)
            second_stdout, second_stderr = second.communicate(timeout=10)

            self.assertEqual(first.returncode, 0, first_stderr)
            self.assertEqual(second.returncode, 0, second_stderr)
            self.assertEqual(log.read_text().splitlines(), ["sync"])
            self.assertTrue(first_stdout)
            self.assertTrue(second_stdout)

    def test_explicit_setup_waits_until_a_managed_cli_exits(self):
        with tempfile.TemporaryDirectory(prefix="compliance dev setup waits ") as temporary:
            root = Path(temporary)
            script, cache = temporary_dev_repository(root, initialized=True)
            started, release, log = root / "cli-started", root / "cli-release", root / "sync.log"
            environment = isolated_environment(cache)
            environment.update(
                COMPLIANCE_DEV_CACHE=str(cache),
                FAKE_CLI_STARTED=str(started),
                FAKE_CLI_RELEASE=str(release),
                FAKE_SYNC_LOG=str(log),
            )
            cli = subprocess.Popen([str(script), "cli", "config", "list"], cwd=root, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for _ in range(100):
                if started.exists():
                    break
                time.sleep(0.01)
            self.assertTrue(started.exists(), "managed CLI did not start")
            (root / "tooling/pyproject.toml").write_text(
                (root / "tooling/pyproject.toml").read_text() + "\n"
            )
            setup = subprocess.Popen([str(script), "setup"], cwd=root, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(0.05)
            self.assertIsNone(setup.poll(), "setup did not wait for the managed CLI")
            release.write_text("release")
            cli_stdout, cli_stderr = cli.communicate(timeout=10)
            setup_stdout, setup_stderr = setup.communicate(timeout=10)

            self.assertEqual(cli.returncode, 0, cli_stderr)
            self.assertEqual(setup.returncode, 0, setup_stderr)
            self.assertEqual(log.read_text().splitlines(), ["sync"])
            self.assertTrue(cli_stdout)
            self.assertEqual(setup_stdout, "")


class CheckCommandTests(unittest.TestCase):
    def check(self, *, area: str, verbose: bool = False, selection: list[str] | None = None, returncodes: list[int] | None = None):
        calls = []
        results = iter(returncodes) if returncodes is not None else itertools.repeat(0)

        def record(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(returncode=next(results))

        with (
            mock.patch.object(dev, "managed_command_lock", return_value=contextlib.nullcontext()),
            mock.patch.object(dev, "ensure_ready_under_lock", return_value=0),
            mock.patch.object(dev, "selected", return_value=(Path("/managed/uv"), Path("/managed/opa"))),
            mock.patch.object(dev, "run", side_effect=record),
        ):
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

    def test_check_waits_for_readiness_before_constructing_its_compact_command(self):
        events = []

        @contextlib.contextmanager
        def lock():
            events.append("lock")
            yield

        def ready():
            events.append("ready")
            return 0

        def selected():
            events.append("selected")
            return Path("/managed/uv"), Path("/managed/opa")

        with (
            mock.patch.object(dev, "managed_command_lock", side_effect=lock),
            mock.patch.object(dev, "ensure_ready_under_lock", side_effect=ready),
            mock.patch.object(dev, "selected", side_effect=selected),
            mock.patch.object(dev, "run", return_value=SimpleNamespace(returncode=0)) as run,
        ):
            result = dev.check(SimpleNamespace(area="tooling", verbose=False, selection=[]))

        self.assertEqual(result, 0)
        self.assertEqual(events, ["lock", "ready", "selected"])
        self.assertNotIn("-v", run.call_args.args[0])


class ReadinessTests(unittest.TestCase):
    head = "a" * 40
    previous_head = "b" * 40
    base = "c" * 40
    previous_base = "d" * 40

    def pr(self, *, head=None, reviewed_head=None, rollup=None):
        return {
            "headRefOid": head or self.head,
            "baseRefName": "main",
            "body": "\n".join((
                f"- Reviewed head: {reviewed_head or head or self.head}",
                "- Reviewer/provider: independent test reviewer",
                "- Outcome and finding disposition: Pass",
            )),
            "statusCheckRollup": rollup or [
                {"name": name, "conclusion": "SUCCESS"}
                for name in dev.REQUIRED_HEAD_CONTEXTS
            ],
        }

    def run_readiness(self, *, pr, merge_base, statuses=None, merge_base_returncode=None):
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            if command[:3] == ["gh", "pr", "view"]:
                return SimpleNamespace(stdout=json.dumps(pr), returncode=0)
            if command[:3] == ["git", "ls-remote", "origin"]:
                return SimpleNamespace(stdout=f"{self.base}\trefs/heads/main\n", returncode=0)
            if command[:2] == ["git", "merge-base"]:
                return SimpleNamespace(
                    stdout=f"{merge_base}\n",
                    returncode=merge_base_returncode if merge_base_returncode is not None else (0 if merge_base == self.base else 1),
                )
            if command[:2] == ["gh", "api"]:
                return SimpleNamespace(stdout=json.dumps({"statuses": statuses or []}), returncode=0)
            raise AssertionError(f"unexpected command: {command}")

        stdout, stderr = StringIO(), StringIO()
        with (
            mock.patch.object(dev.shutil, "which", return_value="/usr/bin/gh"),
            mock.patch.object(dev, "run", side_effect=fake_run),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            result = dev.readiness(SimpleNamespace())
        return result, stdout.getvalue(), stderr.getvalue(), calls

    def integration_status(self, *, state="success", base=None, description=None):
        return {
            "context": dev.INTEGRATION_CONTEXT,
            "state": state,
            "description": description if description is not None else f"base={base or self.base}",
        }

    def test_current_head_containing_base_needs_only_review_and_head_ci(self):
        result, output, errors, calls = self.run_readiness(pr=self.pr(), merge_base=self.base)
        self.assertEqual(result, 0, errors)
        self.assertIn("READY:", output)
        self.assertFalse(any(command[:2] == ["gh", "api"] for command in calls))

    def test_stale_base_requires_current_base_integration_evidence(self):
        result, _, errors, _ = self.run_readiness(pr=self.pr(), merge_base=self.previous_base)
        self.assertEqual(result, 1)
        self.assertIn("integration evidence is missing", errors)

    def test_successful_commit_status_bound_to_current_base_makes_stale_branch_ready(self):
        result, output, errors, _ = self.run_readiness(
            pr=self.pr(), merge_base=self.previous_base, statuses=[self.integration_status()],
        )
        self.assertEqual(result, 0, errors)
        self.assertIn(f"Integration base: {self.base}", output)

    def test_absent_local_base_uses_matching_integration_evidence_without_mutating_git(self):
        result, output, errors, calls = self.run_readiness(
            pr=self.pr(), merge_base="", merge_base_returncode=128,
            statuses=[self.integration_status()],
        )
        self.assertEqual(result, 0, errors)
        self.assertIn("READY:", output)
        merge_base_call = next(command for command in calls if command[:2] == ["git", "merge-base"])
        self.assertEqual(merge_base_call, ["git", "merge-base", "--is-ancestor", self.base, self.head])
        self.assertFalse(any(command[0] == "git" and command[1] in {"fetch", "merge", "rebase", "update-ref"} for command in calls))

    def test_absent_local_base_without_integration_evidence_fails_closed(self):
        result, _, errors, _ = self.run_readiness(
            pr=self.pr(), merge_base="", merge_base_returncode=128,
        )
        self.assertEqual(result, 1)
        self.assertIn("integration evidence is missing", errors)

    def test_old_or_malformed_integration_base_fails_closed(self):
        for description in (f"base={self.previous_base}", "base=not-a-sha", "base=" + self.base + " extra"):
            with self.subTest(description=description):
                result, _, errors, _ = self.run_readiness(
                    pr=self.pr(), merge_base=self.previous_base,
                    statuses=[self.integration_status(description=description)],
                )
                self.assertEqual(result, 1)
                self.assertIn("not bound to current base", errors)

    def test_failed_pending_and_missing_integration_statuses_fail_closed(self):
        for state in ("failure", "pending"):
            with self.subTest(state=state):
                result, _, errors, _ = self.run_readiness(
                    pr=self.pr(), merge_base=self.previous_base,
                    statuses=[self.integration_status(state=state)],
                )
                self.assertEqual(result, 1)
                self.assertIn(f"integration: {state}", errors)

    def test_head_change_cannot_reuse_old_review_or_status_lookup(self):
        changed = "e" * 40
        result, _, errors, calls = self.run_readiness(
            pr=self.pr(head=changed, reviewed_head=self.previous_head),
            merge_base=self.previous_base,
            statuses=[self.integration_status()],
        )
        self.assertEqual(result, 1)
        self.assertIn("review is missing or stale", errors)
        api_call = next(command for command in calls if command[:2] == ["gh", "api"])
        self.assertIn(changed, api_call[-1])
        self.assertNotIn(self.previous_head, api_call[-1])

    def test_check_runs_and_commit_status_contexts_share_the_head_ci_parser(self):
        rollup = [
            {"name": "component-validation", "conclusion": "SUCCESS"},
            {"context": "verification-scenarios", "state": "success"},
            {"name": "installed-release-provenance", "conclusion": "SUCCESS"},
            {"context": "macos-portability", "state": "success"},
        ]
        result, _, errors, _ = self.run_readiness(pr=self.pr(rollup=rollup), merge_base=self.base)
        self.assertEqual(result, 0, errors)

    def test_integration_command_dispatches_without_branch_rewrite(self):
        commands = []

        def fake_run(command, **kwargs):
            commands.append(command)
            if command[:3] == ["gh", "pr", "view"]:
                return SimpleNamespace(stdout=json.dumps({"number": 196, "headRefOid": self.head, "baseRefName": "main"}), returncode=0)
            if command[:3] == ["git", "ls-remote", "origin"]:
                return SimpleNamespace(stdout=f"{self.base}\trefs/heads/main\n", returncode=0)
            if command[:4] == ["gh", "repo", "view", "--json"]:
                return SimpleNamespace(stdout=json.dumps({"defaultBranchRef": {"name": "main"}}), returncode=0)
            if command[:3] == ["gh", "workflow", "run"]:
                return SimpleNamespace(stdout="", returncode=0)
            raise AssertionError(f"unexpected command: {command}")

        with (
            mock.patch.object(dev.shutil, "which", return_value="/usr/bin/gh"),
            mock.patch.object(dev, "run", side_effect=fake_run),
        ):
            result = dev.integration(SimpleNamespace())
        self.assertEqual(result, 0)
        self.assertIn(["gh", "workflow", "run", "current-main-integration.yml", "--ref", "main", "-f", "pr_number=196"], commands)
        self.assertFalse(any(command[0] == "git" and command[1] in {"merge", "rebase", "push", "reset"} for command in commands))


class WorkflowContractTests(unittest.TestCase):
    def test_destination_jobs_remain_exact_pr_head_evidence(self):
        workflow = (REPOSITORY_ROOT / ".github/workflows/destination-validation.yml").read_text()
        for context in dev.REQUIRED_HEAD_CONTEXTS:
            self.assertIn(f"name: {context}", workflow)
        self.assertEqual(workflow.count("github.event.pull_request.head.sha || github.sha"), 12)

    def test_integration_workflow_uses_disposable_combined_candidates_and_isolates_status_writes(self):
        workflow = INTEGRATION_WORKFLOW.read_text()
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("git push", workflow)
        self.assertEqual(workflow.count("git merge --no-ff --no-edit refs/remotes/integration/head"), 4)
        self.assertEqual(workflow.count("persist-credentials: false"), 4)
        self.assertIn("statuses: write", workflow)
        self.assertIn("Publish final status without checking out PR code", workflow)
        for gate in ("scripts/dev gate repository", "scripts/dev gate scenarios", "scripts/dev gate package", "/bin/bash scripts/dev gate package"):
            self.assertIn(gate, workflow)

    def validate_integration_workflow(self, contents: str):
        with tempfile.TemporaryDirectory(prefix="compliance integration workflow ") as temporary:
            workflow = Path(temporary) / "current-main-integration.yml"
            workflow.write_text(contents)
            return subprocess.run(
                ["bash", str(INTEGRATION_WORKFLOW_VALIDATOR), str(workflow)],
                text=True,
                capture_output=True,
            )

    def test_integration_workflow_validator_accepts_the_trusted_split(self):
        result = self.validate_integration_workflow(INTEGRATION_WORKFLOW.read_text())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_integration_workflow_validator_rejects_candidate_token_or_write_permission(self):
        workflow = INTEGRATION_WORKFLOW.read_text()
        candidate_job = (
            "  verification-scenarios:\n"
            "    name: integration verification-scenarios\n"
            "    needs: resolve\n"
            "    runs-on: ubuntu-24.04\n"
            "    timeout-minutes: 30\n"
            "    permissions:\n"
            "      contents: read\n"
        )
        token_candidate = workflow.replace(
            candidate_job,
            candidate_job + "    env:\n      GH_TOKEN: ${{ github.token }}\n",
            1,
        )
        write_candidate = workflow.replace(
            candidate_job,
            candidate_job + "      statuses: write\n",
            1,
        )
        for mutation in (token_candidate, write_candidate):
            with self.subTest(mutation=mutation):
                result = self.validate_integration_workflow(mutation)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("verification-scenarios", result.stderr)


if __name__ == "__main__":
    unittest.main()
