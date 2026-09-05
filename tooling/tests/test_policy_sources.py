from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.policy_sources import PolicySource, source_pin_errors, source_tree_digest
from tools.release_lock import POLICY_SOURCE_DIGEST_ALGORITHM


class PolicySourceIdentityTests(unittest.TestCase):
    LOCATIONS = (
        Path("ordinary/policies"),
        Path("build/policies"),
        Path("__pycache__/policies"),
        Path("path with spaces/policies"),
        Path("root-is-build/build"),
        Path("root-is-cache/__pycache__"),
    )

    def _write_tree(self, root: Path) -> None:
        (root / "controls").mkdir(parents=True)
        (root / "controls/control.rego").write_bytes(b"package example\n")
        (root / "data.json").write_bytes(b'{"enabled":true}\n')

    def test_raw_path_and_byte_vector_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "nested").mkdir()
            (root / "a.txt").write_bytes(b"A\n")
            (root / "nested/b.json").write_bytes(b'{"z":1}\n')

            self.assertEqual(
                source_tree_digest(root),
                "sha256:83b22fd9f7935ef402ba731792e6c57a3ed93aab51af2ca0b01cf60e57aa3a4a",
            )
        self.assertEqual(
            POLICY_SOURCE_DIGEST_ALGORITHM,
            "compliance.example/policy-source-tree-digest/v1alpha1",
        )

    def test_identity_depends_only_on_content_below_the_supplied_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outer = Path(temporary)
            roots = [outer / location for location in self.LOCATIONS]
            for root in roots:
                self._write_tree(root)

            digests = {source_tree_digest(root) for root in roots}

            self.assertEqual(len(digests), 1)
            self.assertNotEqual(
                digests.pop(),
                "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991115fba0f1dd8e4",
            )

    def test_all_included_tree_changes_affect_identity_in_every_location(self) -> None:
        mutations = {
            "edit": lambda root: (root / "data.json").write_bytes(
                b'{"enabled":false}\n'
            ),
            "addition": lambda root: (root / "added.txt").write_bytes(b"added\n"),
            "removal": lambda root: (root / "data.json").unlink(),
            "rename": lambda root: (root / "data.json").rename(root / "renamed.json"),
        }
        with tempfile.TemporaryDirectory() as temporary:
            outer = Path(temporary)
            for location in self.LOCATIONS:
                for mutation_name, mutate in mutations.items():
                    root = outer / mutation_name / location
                    self._write_tree(root)
                    before = source_tree_digest(root)
                    mutate(root)
                    with self.subTest(location=location, mutation=mutation_name):
                        self.assertNotEqual(source_tree_digest(root), before)

    def test_source_internal_generated_directories_remain_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "build" / "policies"
            self._write_tree(root)
            before = source_tree_digest(root)

            for excluded in ("build", "__pycache__"):
                generated = root / "nested" / excluded / "generated.bin"
                generated.parent.mkdir(parents=True)
                generated.write_bytes(b"generated\n")

            self.assertEqual(source_tree_digest(root), before)

    def test_expected_digest_rejects_edit_beneath_build_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "build" / "policies"
            self._write_tree(root)
            expected = source_tree_digest(root)
            source = PolicySource("shared", root, expected)

            (root / "controls/control.rego").write_bytes(b"package changed\n")

            errors = source_pin_errors(source)
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0]["type"], "policy-source-digest-mismatch")
            self.assertEqual(errors[0]["expected"], expected)
            self.assertEqual(errors[0]["actual"], source_tree_digest(root))


if __name__ == "__main__":
    unittest.main()
