from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
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


class ReadinessTests(unittest.TestCase):
    head = "a" * 40
    previous_head = "b" * 40
    base = "c" * 40
    previous_base = "d" * 40

    def pr(self, *, head=None, reviewed_head=None, rollup=None):
        return {
            "number": 196,
            "state": "OPEN",
            "headRefOid": head or self.head,
            "baseRefName": "main",
            "files": [],
            "changedFiles": 0,
            "body": "\n".join((
                f"- Reviewed head: {reviewed_head or head or self.head}",
                "- Reviewed target: main",
                "- Reviewer/provider: independent test reviewer",
                "- Outcome and finding disposition: Pass",
            )),
            "statusCheckRollup": rollup or [
                {"name": name, "conclusion": "SUCCESS"}
                for name in dev.REQUIRED_HEAD_CONTEXTS
            ],
        }

    def run_readiness(self, *, pr, merge_base, statuses=None, merge_base_returncode=None,
                      final_pr=None, final_base=None, target=None):
        calls = []
        pr_reads = 0
        base_reads = 0

        def fake_run(command, **kwargs):
            nonlocal pr_reads, base_reads
            calls.append(command)
            if command[:3] == ["gh", "pr", "view"]:
                pr_reads += 1
                return SimpleNamespace(stdout=json.dumps(final_pr if pr_reads > 1 and final_pr else pr), returncode=0)
            if command[:3] == ["git", "ls-remote", "origin"]:
                base_reads += 1
                sha = final_base if base_reads > 1 and final_base else self.base
                return SimpleNamespace(stdout=f"{sha}\trefs/heads/{pr['baseRefName']}\n", returncode=0)
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
            result = dev.readiness(SimpleNamespace(target=target))
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

    def successor_pr(self, *, shared=False):
        pr = self.pr()
        pr["baseRefName"] = "successor"
        pr["body"] = pr["body"].replace("Reviewed target: main", "Reviewed target: successor")
        pr["files"] = [{"path": "scripts/dev" if shared else "successor/README.md"}]
        pr["changedFiles"] = 1
        if not shared:
            pr["statusCheckRollup"] = []
        pr["statusCheckRollup"].append({"name": "successor-foundation", "conclusion": "SUCCESS"})
        return pr

    def test_successor_only_and_shared_head_responsibilities(self):
        for shared in (False, True):
            with self.subTest(shared=shared):
                pr = self.successor_pr(shared=shared)
                result, output, errors, _ = self.run_readiness(pr=pr, merge_base=self.base)
                self.assertEqual(result, 0, errors)
                self.assertIn("Integration target: successor", output)
                if shared:
                    pr["statusCheckRollup"] = pr["statusCheckRollup"][-1:]
                    result, _, errors, _ = self.run_readiness(pr=pr, merge_base=self.base)
                    self.assertEqual(result, 1)
                    self.assertIn("component-validation", errors)

    def test_successor_cannot_reuse_main_integration_or_review(self):
        pr = self.successor_pr()
        result, _, errors, _ = self.run_readiness(
            pr=pr, merge_base=self.previous_base, statuses=[self.integration_status()])
        self.assertEqual(result, 1)
        self.assertIn("integration evidence is missing", errors)
        status = self.integration_status()
        status["context"] = "integration-current-successor"
        result, _, errors, _ = self.run_readiness(pr=pr, merge_base=self.previous_base, statuses=[status])
        self.assertEqual(result, 0, errors)
        pr["body"] = pr["body"].replace("Reviewed target: successor", "Reviewed target: main")
        result, _, errors, _ = self.run_readiness(pr=pr, merge_base=self.base)
        self.assertEqual(result, 1)
        self.assertIn("review target", errors)

    def test_final_readiness_rechecks_head_target_state_and_base(self):
        for field, value in (("headRefOid", self.previous_head), ("baseRefName", "successor"), ("state", "CLOSED")):
            final = self.pr()
            final[field] = value
            result, _, errors, _ = self.run_readiness(pr=self.pr(), merge_base=self.base, final_pr=final)
            self.assertEqual(result, 1, field)
            self.assertIn("during readiness", errors)
        result, _, errors, _ = self.run_readiness(pr=self.pr(), merge_base=self.base, final_base=self.previous_base)
        self.assertEqual(result, 1)
        self.assertIn("base advanced", errors)

    def test_explicit_wrong_target_refuses_readiness(self):
        result, _, errors, calls = self.run_readiness(pr=self.pr(), merge_base=self.base, target="successor")
        self.assertEqual(result, 1)
        self.assertIn("requested target", errors)
        self.assertEqual(len(calls), 1)

    def test_all_non_success_head_states_and_duplicate_names_fail_closed(self):
        for state in ("FAILURE", "CANCELLED", "SKIPPED", "NEUTRAL", "", "TIMED_OUT"):
            pr = self.successor_pr()
            pr["statusCheckRollup"][0]["conclusion"] = state
            result, _, errors, _ = self.run_readiness(pr=pr, merge_base=self.base)
            self.assertEqual(result, 1, state)
        pr = self.successor_pr()
        pr["statusCheckRollup"] *= 2
        result, _, errors, _ = self.run_readiness(pr=pr, merge_base=self.base)
        self.assertEqual(result, 1)
        self.assertIn("ambiguous duplicate", errors)

    def test_successor_dispatch_uses_actual_target_not_default_or_head(self):
        commands = []
        def fake_run(command, **kwargs):
            commands.append(command)
            if command[:3] == ["gh", "pr", "view"]:
                return SimpleNamespace(stdout=json.dumps({"number": 210, "headRefOid": self.head, "baseRefName": "successor"}))
            if command[:3] == ["git", "ls-remote", "origin"]:
                return SimpleNamespace(stdout=f"{self.base}\trefs/heads/successor\n")
            if command[:3] == ["gh", "workflow", "run"]:
                return SimpleNamespace(returncode=0)
            raise AssertionError(command)
        with mock.patch.object(dev.shutil, "which", return_value="gh"), mock.patch.object(dev, "run", side_effect=fake_run):
            self.assertEqual(dev.integration(SimpleNamespace(target="successor")), 0)
        self.assertIn(["gh", "workflow", "run", "current-main-integration.yml", "--ref", "successor", "-f", "pr_number=210"], commands)


class WorkflowContractTests(unittest.TestCase):
    def test_destination_jobs_remain_exact_pr_head_evidence(self):
        workflow = (REPOSITORY_ROOT / ".github/workflows/destination-validation.yml").read_text()
        for context in dev.REQUIRED_HEAD_CONTEXTS:
            self.assertIn(f"name: {context}", workflow)
        self.assertEqual(workflow.count("github.event.pull_request.head.sha || github.sha"), 15)

    def test_integration_workflow_uses_disposable_combined_candidates_and_isolates_status_writes(self):
        workflow = INTEGRATION_WORKFLOW.read_text()
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("git push", workflow)
        self.assertEqual(workflow.count("git merge --no-ff --no-edit refs/remotes/integration/head"), 6)
        self.assertEqual(workflow.count("persist-credentials: false"), 6)
        self.assertIn("statuses: write", workflow)
        self.assertIn("Publish final status without checking out PR code", workflow)
        for gate in ("scripts/dev gate repository", "scripts/dev gate scenarios", "scripts/dev gate package", "/bin/bash scripts/dev gate package"):
            self.assertIn(gate, workflow)

def workflow_job(workflow: str, job: str) -> str:
    return re.search(rf"^  {re.escape(job)}:\n(.*?)(?=^  [\w-]+:|\Z)", workflow, re.M | re.S).group(1)


def workflow_script(workflow: str, step: str) -> str:
    block = workflow.split(f"- name: {step}\n", 1)[1]
    block = block.split("        run: |\n", 1)[1]
    lines = []
    for line in block.splitlines():
        if line and not line.startswith("          "):
            break
        lines.append(line[10:])
    return "\n".join(lines) + "\n"


class LaneRoutingTests(unittest.TestCase):
    def test_fixed_scope_positive_and_negative_routes(self):
        self.assertTrue(dev.legacy_required("main", ["tooling/src/anything.py"]))
        self.assertFalse(dev.legacy_required("successor", ["successor/README.md", "docs/SUCCESSOR_ARCHITECTURE.md"]))
        for path in dev.SHARED_FILES:
            self.assertTrue(dev.legacy_required("successor", [path]), path)
        for path in ("tooling/src/example.py", "policy-sources/control-library/policies/example.json",
                     "verification/scenarios/scripts/fixture.py", "projects/mock-fleet/README.md",
                     "toolchain/versions.env", "successor/go.mod", "successor/../tooling/example.py",
                     "new-workflow.yml", "successor/runtime.py"):
            with self.subTest(path=path), self.assertRaisesRegex(SystemExit, "separately reviewed"):
                dev.legacy_required("successor", [path])
        with self.assertRaisesRegex(SystemExit, "unsupported integration target"):
            dev.legacy_required("experiment", [])

    def test_route_rejects_malformed_revisions(self):
        for revision in ("main", "HEAD", "a" * 39, "--output=file"):
            with self.assertRaisesRegex(SystemExit, "exact 40-hex"):
                dev.changed_paths(revision, "a" * 40)

    def test_move_out_of_legacy_is_not_hidden_by_rename_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
            git("init", "-b", "main")
            git("config", "user.name", "test")
            git("config", "user.email", "test@example.invalid")
            (root / "tooling").mkdir()
            (root / "tooling/legacy.md").write_text("legacy")
            git("add", "."); git("commit", "-m", "base")
            base = git("rev-parse", "HEAD")
            (root / "successor").mkdir()
            git("mv", "tooling/legacy.md", "successor/README.md")
            git("commit", "-m", "move")
            with mock.patch.object(dev, "ROOT", root):
                paths = dev.changed_paths(base, git("rev-parse", "HEAD"))
            self.assertEqual(set(paths), {"tooling/legacy.md", "successor/README.md"})
            with self.assertRaisesRegex(SystemExit, "tooling/legacy.md"):
                dev.legacy_required("successor", paths)

    def test_successor_setup_and_foundation_never_provision_legacy(self):
        with mock.patch.object(dev, "setup_lock", side_effect=AssertionError("legacy setup")):
            self.assertEqual(dev.setup(SimpleNamespace(target="successor")), 0)
        with mock.patch.object(dev, "run", return_value=SimpleNamespace(returncode=0)) as run:
            self.assertEqual(dev.foundation(SimpleNamespace()), 0)
        self.assertEqual(run.call_args.args[0], [sys.executable, "-m", "unittest", "discover", "-s", "tests/toolchain", "-p", "test_lanes.py"])

    def test_task_requires_explicit_supported_target_and_reports_exact_base(self):
        with mock.patch.object(dev, "run", return_value=SimpleNamespace(stdout="a" * 40 + "\trefs/heads/successor\n")) as run:
            with contextlib.redirect_stdout(StringIO()) as output:
                self.assertEqual(dev.task(SimpleNamespace(target="successor")), 0)
        self.assertIn("Integration target: successor", output.getvalue())
        self.assertIn("a" * 40, output.getvalue())
        self.assertEqual(run.call_args.args[0], ["git", "ls-remote", "origin", "refs/heads/successor"])

    def test_bootstrap_contains_instructions_only_and_routes_to_existing_owners(self):
        root = REPOSITORY_ROOT
        paths = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "successor/"],
                               cwd=root, capture_output=True, text=True, check=True).stdout.splitlines()
        self.assertEqual(set(paths), {"successor/AGENTS.md", "successor/README.md"})
        for path in paths:
            self.assertFalse((root / path).is_symlink())
            content = (root / path).read_text()
            for reference in ("SUCCESSOR_ARCHITECTURE.md", "DEVELOPMENT_WORKFLOW.md", "0025-trusted-snapshot-successor.md"):
                self.assertIn(reference, content)
            for link in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", content):
                self.assertTrue((root / path).parent.joinpath(link).is_file(), link)
        self.assertIn("successor/AGENTS.md", (root / "AGENTS.md").read_text())
        t3 = json.loads((root / "t3.json").read_text())
        self.assertFalse(any(script.get("runOnWorktreeCreate") for script in t3["scripts"]))


class ExecutedWorkflowTests(unittest.TestCase):
    head = "a" * 40
    base = "b" * 40

    def run_script(self, script, **values):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gh = root / "gh"
            gh.write_text(f"#!{sys.executable}\n" + '''import json, os, sys
if "POST" in sys.argv:
    with open(os.environ["PUBLISHED"], "w") as output:
        json.dump(sys.argv[1:], output)
elif any("/pulls/" in arg for arg in sys.argv):
    print(os.environ["PR_JSON"])
else:
    print(os.environ["CURRENT_BASE"])
''')
            gh.chmod(0o755)
            output = root / "outputs"
            output.touch()
            published = root / "published.json"
            environment = dict(os.environ, PATH=f"{root}:{os.environ['PATH']}",
                GITHUB_OUTPUT=str(output), PUBLISHED=str(published),
                GITHUB_REPOSITORY="packetlss/compliance", GITHUB_SERVER_URL="https://github.com",
                GITHUB_RUN_ID="123", GITHUB_REF="refs/heads/main", WORKFLOW_SHA=self.base,
                PR_NUMBER="210", HEAD=self.head, BASE=self.base, TARGET="main", LEGACY="true",
                ROUTE="success", FOUNDATION="success", COMPONENT="success", SCENARIOS="success",
                RELEASE="success", MACOS="success", CURRENT_BASE=self.base,
                PR_JSON=json.dumps({"state": "open", "head": {"sha": self.head}, "base": {"ref": "main"}}))
            environment.update(values)
            result = subprocess.run(["bash", "-c", script], cwd=root, env=environment, capture_output=True, text=True)
            return result, output.read_text(), json.loads(published.read_text()) if published.exists() else None

    def test_actual_foundation_aggregation_requires_all_affected_jobs(self):
        workflow = (REPOSITORY_ROOT / ".github/workflows/destination-validation.yml").read_text()
        script = workflow_script(workflow, "Require every affected responsibility")
        result, _, _ = self.run_script(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        for key in ("ROUTE", "COMPONENT", "SCENARIOS", "RELEASE", "MACOS"):
            for state in ("failure", "cancelled", "skipped", ""):
                result, _, _ = self.run_script(script, **{key: state})
                self.assertNotEqual(result.returncode, 0, (key, state))
        result, _, _ = self.run_script(script, TARGET="successor", LEGACY="false",
            COMPONENT="skipped", SCENARIOS="skipped", RELEASE="skipped", MACOS="skipped")
        self.assertEqual(result.returncode, 0)
        for target, legacy in (("main", "false"), ("other", "true"), ("successor", "")):
            result, _, _ = self.run_script(script, TARGET=target, LEGACY=legacy)
            self.assertNotEqual(result.returncode, 0)

    def test_trusted_resolver_rejects_wrong_dispatch_ref_stale_workflow_and_bad_metadata(self):
        script = workflow_script(INTEGRATION_WORKFLOW.read_text(), "Resolve the open PR and current base")
        for target in ("main", "successor"):
            pr = {"state": "open", "head": {"sha": self.head}, "base": {"ref": target}}
            result, output, _ = self.run_script(script, GITHUB_REF=f"refs/heads/{target}", PR_JSON=json.dumps(pr))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"target={target}", output)
        for values in ({"GITHUB_REF": "refs/heads/unreviewed"}, {"WORKFLOW_SHA": "c" * 40},
                       {"PR_NUMBER": "1;exit 0"}, {"CURRENT_BASE": "missing"},
                       {"PR_JSON": json.dumps({"state": "closed", "head": {"sha": self.head}, "base": {"ref": "main"}})},
                       {"PR_JSON": json.dumps({"state": "open", "head": {"sha": self.head}, "base": {"ref": "other"}})}):
            result, _, _ = self.run_script(script, **values)
            self.assertNotEqual(result.returncode, 0, values)

    def test_publisher_fails_non_success_or_stale_evidence_and_uses_separate_context(self):
        script = workflow_script(INTEGRATION_WORKFLOW.read_text(), "Publish final status without checking out PR code")
        result, _, status = self.run_script(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("state=success", status)
        self.assertIn("context=integration-current-main", status)
        for key in ("ROUTE", "FOUNDATION", "COMPONENT", "SCENARIOS", "RELEASE", "MACOS"):
            for state in ("failure", "cancelled", "skipped", ""):
                result, _, status = self.run_script(script, **{key: state})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("state=failure", status, (key, state))
        for values in ({"CURRENT_BASE": "c" * 40}, {"HEAD": "c" * 40}, {"TARGET": "successor"}, {"LEGACY": "false"}):
            _, _, status = self.run_script(script, **values)
            self.assertIn("state=failure", status, values)
        pr = {"state": "open", "head": {"sha": self.head}, "base": {"ref": "successor"}}
        _, _, status = self.run_script(script, TARGET="successor", LEGACY="false", PR_JSON=json.dumps(pr),
            COMPONENT="skipped", SCENARIOS="skipped", RELEASE="skipped", MACOS="skipped")
        self.assertIn("state=success", status)
        self.assertIn("context=integration-current-successor", status)
        self.assertIn(f"description=base={self.base}", status)

    def test_combined_candidate_rejects_moved_head_and_merge_conflict(self):
        script = workflow_script(INTEGRATION_WORKFLOW.read_text(), "Build disposable combined candidate")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote, source, candidate = (root / name for name in ("remote.git", "source", "candidate"))
            def git(cwd, *args, check=True):
                return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check).stdout.strip()
            git(root, "init", "--bare", str(remote))
            git(root, "init", "-b", "main", str(source))
            git(source, "config", "user.name", "test"); git(source, "config", "user.email", "test@example.invalid")
            (source / "file").write_text("original\n")
            git(source, "add", "."); git(source, "commit", "-m", "initial")
            initial = git(source, "rev-parse", "HEAD")
            (source / "file").write_text("base\n"); git(source, "commit", "-am", "base")
            base = git(source, "rev-parse", "HEAD")
            git(source, "checkout", "-b", "proposal", initial)
            (source / "file").write_text("proposal\n"); git(source, "commit", "-am", "proposal")
            head = git(source, "rev-parse", "HEAD")
            git(source, "push", str(remote), "main", "HEAD:refs/pull/210/head")
            git(root, "clone", "-b", "main", str(remote), str(candidate))
            output = root / "output"; output.touch()
            env = dict(os.environ, PR_NUMBER="210", HEAD="c" * 40, GITHUB_OUTPUT=str(output))
            moved = subprocess.run(["bash", "-c", script], cwd=candidate, env=env, capture_output=True)
            self.assertNotEqual(moved.returncode, 0)
            env["HEAD"] = head
            conflict = subprocess.run(["bash", "-c", script], cwd=candidate, env=env, capture_output=True)
            self.assertNotEqual(conflict.returncode, 0)
            self.assertEqual(output.read_text(), "")
            self.assertEqual(git(candidate, "rev-parse", "HEAD"), base)
            git(candidate, "merge", "--abort")
            git(candidate, "update-ref", "-d", "refs/remotes/integration/head")
            # A genuine nonconflicting candidate succeeds without updating either remote ref.
            git(source, "checkout", "-b", "clean", initial)
            (source / "new").write_text("proposal\n"); git(source, "add", "."); git(source, "commit", "-m", "clean proposal")
            clean_head = git(source, "rev-parse", "HEAD")
            git(source, "push", str(remote), "HEAD:refs/pull/211/head")
            env.update(PR_NUMBER="211", HEAD=clean_head)
            success = subprocess.run(["bash", "-c", script], cwd=candidate, env=env, capture_output=True)
            self.assertEqual(success.returncode, 0, success.stderr)
            self.assertTrue(output.read_text().startswith("sha="))
            self.assertEqual(git(remote, "rev-parse", "refs/heads/main"), base)
            self.assertEqual(git(remote, "rev-parse", "refs/pull/211/head"), clean_head)

    def test_workflow_routing_and_credential_execution_separation(self):
        destination = (REPOSITORY_ROOT / ".github/workflows/destination-validation.yml").read_text()
        integration = INTEGRATION_WORKFLOW.read_text()
        self.assertIn("branches: [main, successor]", destination)
        self.assertIn("types: [opened, synchronize, reopened, edited]", destination)
        for workflow in (destination, integration):
            self.assertNotRegex(workflow, r"(?m)^\s+paths(-ignore)?:")
            self.assertNotIn("pull_request_target", workflow)
            self.assertNotIn("secrets.", workflow)
            for action in re.findall(r"(?m)^\s+(?:- )?uses: ([^\n]+)", workflow):
                self.assertRegex(action, r"@[0-9a-f]{40}(?: |$)")
        for job in dev.REQUIRED_HEAD_CONTEXTS:
            for workflow in (destination, integration):
                block = workflow_job(workflow, job)
                self.assertIn("needs.route.outputs.legacy == 'true'", block)
        for job in ("resolve", "publish"):
            block = workflow_job(integration, job)
            self.assertIn("statuses: write", block)
            self.assertNotRegex(block, r"(?m)^\s+(?:- )?uses:")
            self.assertNotIn("scripts/dev", block)
        for job in (*dev.REQUIRED_HEAD_CONTEXTS, "route", "successor-foundation"):
            block = workflow_job(integration, job)
            self.assertNotIn("statuses: write", block)
            self.assertNotIn("github.token", block)
            self.assertIn("persist-credentials: false", block)
        self.assertIn("if: ${{ always() }}", workflow_job(destination, "successor-foundation"))
        self.assertIn("scripts/dev foundation", workflow_job(integration, "successor-foundation"))


if __name__ == "__main__":
    unittest.main()
