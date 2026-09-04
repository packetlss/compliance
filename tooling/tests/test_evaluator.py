from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.evaluator import EvaluatorIdentityError, opa_evaluator_identity, resolve_opa_evaluator


class EvaluatorIdentityTests(unittest.TestCase):
    def _fake_opa(self, root: Path, *, version: str, marker: str) -> Path:
        path = root / f"opa-{marker}"
        path.write_text(
            "#!/usr/bin/env sh\n"
            "if [ \"${1:-}\" = version ]; then\n"
            f"  printf 'Version: {version}\\nBuild Commit: synthetic-{marker}\\n'\n"
            "  exit 0\n"
            "fi\n"
            "printf '{}\\n'\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    def test_identity_hashes_exact_executable_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self._fake_opa(Path(temporary), version="1.18.2", marker="a")
            identity, resolved = resolve_opa_evaluator(str(path))
            expected = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(identity.name, "opa")
            self.assertEqual(identity.version, "1.18.2")
            self.assertEqual(identity.executable_sha256, expected)
            self.assertEqual(Path(resolved), path.resolve())
            self.assertNotIn("executable", identity.document())

    def test_different_bytes_change_execution_identity_even_at_same_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self._fake_opa(root, version="1.18.2", marker="a")
            second = self._fake_opa(root, version="1.18.2", marker="b")
            first_identity = opa_evaluator_identity(str(first))
            second_identity = opa_evaluator_identity(str(second))
            self.assertEqual(first_identity.version, second_identity.version)
            self.assertNotEqual(
                first_identity.executable_sha256,
                second_identity.executable_sha256,
            )

    def test_non_semver_version_output_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self._fake_opa(Path(temporary), version="development", marker="bad")
            with self.assertRaisesRegex(EvaluatorIdentityError, "semantic version"):
                opa_evaluator_identity(str(path))


if __name__ == "__main__":
    unittest.main()
