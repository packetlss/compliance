"""Exercise the destination-local, non-Git project validation assembly."""

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
        temporary = tempfile.TemporaryDirectory(prefix="project-validation-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / "destination"
        self.source.mkdir()
        git(self.source, "init", "--quiet")
        git(self.source, "config", "user.name", "Assembly test")
        git(self.source, "config", "user.email", "assembly@example.invalid")
        for relative in assembly.ASSEMBLY_ROOTS:
            (self.source / relative).mkdir(parents=True)
            (self.source / relative / "fixture").write_text(
                f"committed {relative}\n", encoding="utf-8"
            )
        for project in assembly.PROJECT_ENTRIES:
            (self.source / "projects" / project).mkdir()
            (self.source / "projects" / project / "compliance.yaml").write_text(
                f"project: {project}\n", encoding="utf-8"
            )
        registry = self.source / assembly.REGISTRY_PATH
        registry.parent.mkdir(parents=True)
        registry.write_text("synthetic registry\n", encoding="utf-8")
        git(self.source, "add", ".")
        git(self.source, "commit", "--quiet", "-m", "Synthetic destination")
        root_patch = patch.object(assembly, "REPOSITORY_ROOT", self.source)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        self.assembled = self.root / "assembled"

    def assemble(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            assembly.assemble(self.assembled)

    def test_exact_committed_roots_have_no_git_metadata(self) -> None:
        self.assemble()
        self.assertEqual(
            {path.name for path in self.assembled.iterdir()},
            assembly.TOP_LEVEL_ENTRIES,
        )
        self.assertFalse(any(path.name == ".git" for path in self.assembled.rglob(".git")))
        self.assertEqual(
            (self.assembled / "tooling/fixture").read_text(encoding="utf-8"),
            "committed tooling\n",
        )

    def test_dirty_destination_is_rejected_before_assembly(self) -> None:
        (self.source / "untracked").write_text("not committed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "commit destination changes"):
            assembly.assemble(self.assembled)

    def test_modified_or_extra_assembly_content_is_rejected(self) -> None:
        self.assemble()
        (self.assembled / "tooling/fixture").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "differ"):
            assembly.verify(self.assembled)
        shutil.rmtree(self.assembled)
        self.assemble()
        (self.assembled / "undeclared").mkdir()
        with self.assertRaisesRegex(ValueError, "only the registry"):
            assembly.verify(self.assembled)

    def test_missing_project_root_is_rejected(self) -> None:
        self.assemble()
        shutil.rmtree(self.assembled / "projects/server-personas")
        with self.assertRaisesRegex(ValueError, "separate project roots"):
            assembly.verify(self.assembled)

    def test_generated_project_output_is_rejected(self) -> None:
        self.assemble()
        generated = self.assembled / "projects/mock-fleet/generated/results"
        generated.mkdir(parents=True)
        (generated / "result.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "generated project output"):
            assembly.verify(self.assembled)

    def test_symlinked_inputs_are_rejected(self) -> None:
        self.assemble()
        fixture = self.assembled / "tooling/fixture"
        fixture.unlink()
        os.symlink(self.assembled / "projects/mock-fleet/compliance.yaml", fixture)
        with self.assertRaisesRegex(ValueError, "materialized, not symlinked"):
            assembly.verify(self.assembled)

    def test_assembly_can_be_relocated_without_changing_inputs(self) -> None:
        self.assemble()
        relocated = self.root / "different location" / "assembly"
        relocated.parent.mkdir()
        shutil.move(self.assembled, relocated)
        with contextlib.redirect_stdout(io.StringIO()):
            assembly.verify(relocated)

    def test_git_root_and_git_ancestor_are_rejected(self) -> None:
        for root in (self.source, self.source / "nested"):
            root.mkdir(exist_ok=True)
            with self.subTest(root=root), self.assertRaisesRegex(ValueError, "Git|git"):
                assembly.require_non_git_root(root)


if __name__ == "__main__":
    unittest.main()
