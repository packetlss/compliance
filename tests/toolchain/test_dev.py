from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "toolchain/dev.py"
SPEC = importlib.util.spec_from_file_location("compliance_dev", SOURCE)
assert SPEC and SPEC.loader
dev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dev)


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


if __name__ == "__main__":
    unittest.main()
