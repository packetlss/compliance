from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATION_SCRIPTS = (
    "validate-package.sh",
    "validate-locked-artifacts-package.sh",
    "validate-release-preparation.sh",
    "validate-policy-release-compatibility.sh",
)


class ReleaseValidationInputTests(unittest.TestCase):
    def test_build_backend_is_exactly_pinned(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(pyproject["build-system"]["requires"], ["uv_build==0.12.5"])

    def test_locked_installer_exports_hashes_and_installs_wheel_without_deps(self) -> None:
        helper = (ROOT / "scripts/install-locked-wheel.py").read_text(encoding="utf-8")
        for argument in (
            '"--frozen"',
            '"--no-dev"',
            '"--no-emit-project"',
            '"--require-hashes"',
            '"--no-deps"',
        ):
            self.assertIn(argument, helper)

    def test_every_installed_release_gate_uses_locked_installer(self) -> None:
        direct_install = re.compile(r"uv\s+pip\s+install")
        for name in VALIDATION_SCRIPTS:
            with self.subTest(script=name):
                script = (ROOT / "scripts" / name).read_text(encoding="utf-8")
                self.assertIn('scripts/install-locked-wheel.py"', script)
                self.assertIsNone(direct_install.search(script))

    def test_package_gate_exercises_clean_and_populated_cache(self) -> None:
        script = (ROOT / "scripts/validate-package.sh").read_text(encoding="utf-8")
        self.assertEqual(script.count('scripts/install-locked-wheel.py"'), 2)
        self.assertEqual(script.count('--cache-dir "$temporary/uv-cache"'), 2)


if __name__ == "__main__":
    unittest.main()
