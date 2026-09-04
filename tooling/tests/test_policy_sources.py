from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.policy_sources import source_tree_digest
from tools.release_lock import POLICY_SOURCE_DIGEST_ALGORITHM


class PolicySourceIdentityTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
