from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from tools.tooling_source import (
    TOOLING_SOURCE_DIGEST_ALGORITHM,
    ToolingSourceError,
    tooling_source_digest,
)


ROOT = Path(__file__).resolve().parents[1]


class ToolingSourceDigestTests(unittest.TestCase):
    def test_active_algorithm_identifier_is_provisional(self) -> None:
        self.assertEqual(
            TOOLING_SOURCE_DIGEST_ALGORITHM,
            "compliance.example/tooling-source-tree-digest/v1alpha1",
        )

    def _copy_scope(self, destination: Path) -> None:
        (destination / "schemas/inventory").mkdir(parents=True)
        (destination / "schemas/waivers").mkdir(parents=True)
        (destination / "scripts").mkdir(parents=True)
        shutil.copy2(ROOT / "pyproject.toml", destination / "pyproject.toml")
        shutil.copy2(ROOT / "scripts/build-wheel.py", destination / "scripts/build-wheel.py")
        shutil.copy2(
            ROOT / "schemas/inventory/resource.schema.json",
            destination / "schemas/inventory/resource.schema.json",
        )
        shutil.copy2(
            ROOT / "schemas/waivers/resource.schema.json",
            destination / "schemas/waivers/resource.schema.json",
        )
        shutil.copytree(ROOT / "tools", destination / "tools")
        shutil.copytree(ROOT / "package-data", destination / "package-data")

    def test_digest_is_location_and_git_independent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "elsewhere/second"
            self._copy_scope(first)
            self._copy_scope(second)
            (first / ".git").mkdir()
            (first / ".git/HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (second / ".git").mkdir()
            (second / ".git/HEAD").write_text("different metadata\n", encoding="utf-8")
            self.assertEqual(tooling_source_digest(first), tooling_source_digest(second))

    def test_runtime_build_and_pyproject_changes_change_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            self._copy_scope(root)
            initial = tooling_source_digest(root)
            runtime = root / "tools/release.py"
            runtime.write_text(runtime.read_text(encoding="utf-8") + "\n# semantic change\n", encoding="utf-8")
            self.assertNotEqual(initial, tooling_source_digest(root))

            root2 = Path(temporary) / "source2"
            self._copy_scope(root2)
            initial2 = tooling_source_digest(root2)
            build = root2 / "scripts/build-wheel.py"
            build.write_text(build.read_text(encoding="utf-8") + "\n# build contract change\n", encoding="utf-8")
            self.assertNotEqual(initial2, tooling_source_digest(root2))

            root3 = Path(temporary) / "source3"
            self._copy_scope(root3)
            initial3 = tooling_source_digest(root3)
            pyproject = root3 / "pyproject.toml"
            pyproject.write_text(pyproject.read_text(encoding="utf-8").replace(
                '"PyYAML>=6.0,<7",', '"PyYAML>=6.0,<6.1",'
            ), encoding="utf-8")
            self.assertNotEqual(initial3, tooling_source_digest(root3))

    def test_release_metadata_docs_tests_and_lockfile_are_noncanonical(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            self._copy_scope(root)
            initial = tooling_source_digest(root)
            metadata = root / "tools/release-metadata.json"
            metadata.write_text('{"schema":"injected","source_digest":"different"}\n', encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs/note.md").write_text("presentation only\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests/test_note.py").write_text("# test only\n", encoding="utf-8")
            (root / "uv.lock").write_text("lock presentation\n", encoding="utf-8")
            self.assertEqual(initial, tooling_source_digest(root))

    def test_symlink_inside_canonical_scope_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            self._copy_scope(root)
            link = root / "tools/symlink.py"
            try:
                link.symlink_to(root / "tools/release.py")
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links unavailable on this platform")
            with self.assertRaisesRegex(ToolingSourceError, "symbolic links"):
                tooling_source_digest(root)


if __name__ == "__main__":
    unittest.main()
