"""Exercise the destination-local IAM boundary assembly."""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import validation_inputs as assembly


def git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *arguments],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


class AssemblyTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="iam-boundary-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / "destination"
        self.source.mkdir()
        git(self.source, "init", "--quiet")
        git(self.source, "config", "user.name", "IAM assembly test")
        git(self.source, "config", "user.email", "iam@example.invalid")
        for relative in assembly.ASSEMBLY_ROOTS:
            (self.source / relative).mkdir(parents=True)
            (self.source / relative / "fixture").write_text(
                f"committed {relative}\n", encoding="utf-8"
            )
        private = self.source / assembly.PRIVATE_POLICY_PATH
        private.mkdir(parents=True)
        (private / "realization.json").write_text("{}\n", encoding="utf-8")
        self.expected_digest = assembly.source_tree_digest(private)
        git(self.source, "add", ".")
        git(self.source, "commit", "--quiet", "-m", "Synthetic destination")
        root_patch = patch.object(assembly, "REPOSITORY_ROOT", self.source)
        digest_patch = patch.object(
            assembly, "EXPECTED_PRIVATE_POLICY_DIGEST", self.expected_digest
        )
        root_patch.start()
        digest_patch.start()
        self.addCleanup(root_patch.stop)
        self.addCleanup(digest_patch.stop)
        self.assembled = self.root / "assembled"

    def assemble(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            assembly.assemble(self.assembled)

    def test_private_policy_is_copied_then_removed_from_execution_fixture(self) -> None:
        self.assemble()
        self.assertFalse((self.assembled / assembly.PRIVATE_POLICY_PATH).exists())
        materialized = self.assembled / assembly.MATERIALIZED_PRIVATE_PATH
        self.assertEqual(assembly.source_tree_digest(materialized), self.expected_digest)
        self.assertFalse(any(path.name == ".git" for path in self.assembled.rglob(".git")))

    def test_dirty_destination_is_rejected_before_assembly(self) -> None:
        (self.source / "untracked").write_text("not committed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "commit destination changes"):
            assembly.assemble(self.assembled)

    def test_modified_or_missing_private_materialization_is_rejected(self) -> None:
        self.assemble()
        materialized = self.assembled / assembly.MATERIALIZED_PRIVATE_PATH
        (materialized / "realization.json").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "digest differs"):
            assembly.verify(self.assembled)
        shutil.rmtree(materialized)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            assembly.verify(self.assembled)

    def test_symlinked_materialization_is_rejected(self) -> None:
        self.assemble()
        materialized = self.assembled / assembly.MATERIALIZED_PRIVATE_PATH
        target = materialized / "realization.json"
        target.unlink()
        os.symlink(self.source / assembly.PRIVATE_POLICY_PATH / "realization.json", target)
        with self.assertRaisesRegex(ValueError, "symlinked"):
            assembly.verify(self.assembled)

    def test_git_root_and_git_ancestor_are_rejected(self) -> None:
        for root in (self.source, self.source / "nested"):
            root.mkdir(exist_ok=True)
            with self.subTest(root=root), self.assertRaisesRegex(ValueError, "Git|git"):
                assembly.require_non_git_root(root)


if __name__ == "__main__":
    unittest.main()
