from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]

UNITTEST_RUNNERS = (
    "tooling/scripts/validate-tooling.sh",
    "scripts/validate-repository.sh",
    "scripts/development-projects/validate-all-development-projects.sh",
    "scripts/validate-iam-private-boundary.sh",
    "scripts/validate-verification-scenarios.sh",
    "policy-sources/verification-policy/scripts/validate-verification-policy.sh",
    "policy-sources/control-library/scripts/validate-shared-policy.sh",
    "policy-sources/control-library/scripts/validate-policy-release.sh",
)


class CanonicalValidationOutputTests(unittest.TestCase):
    def test_unittest_runners_use_compact_native_output(self):
        for relative_path in UNITTEST_RUNNERS:
            with self.subTest(script=relative_path):
                content = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("unittest discover", content)
                invocation = content.split("unittest discover", maxsplit=1)[1].split(
                    "\n\n", maxsplit=1
                )[0]
                self.assertNotIn(" -v", invocation)

    def test_rego_runner_uses_compact_native_output(self):
        content = (
            ROOT
            / "policy-sources/control-library/scripts/validate-shared-policy.sh"
        ).read_text(encoding="utf-8")
        invocation = next(line for line in content.splitlines() if line.startswith("opa test"))
        self.assertEqual(invocation, 'opa test "$POLICY_ROOT/policies/controls"')


if __name__ == "__main__":
    unittest.main()
