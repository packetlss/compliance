from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.policy_sources import PolicySource, source_tree_digest
from tools.project_config import (
    ProjectConfigError,
    _argument_uses_flag,
    load_config,
)
from tools.release import ToolingReleaseIdentity
from tools.release_lock import load_release_lock, validate_release_composition
from tools.tooling_source import TOOLING_SOURCE_DIGEST_ALGORITHM


class ReleaseLockFailureTests(unittest.TestCase):
    def _fixture(self, root: Path):
        policy = root / "policy"
        policy.mkdir()
        target = policy / "content.json"
        target.write_text('{"value":1}\n', encoding="utf-8")
        digest = source_tree_digest(policy)
        lock = root / "compliance.lock.yaml"
        lock.write_text(
            f"""\
schema: compliance.example/release-lock/v1alpha2
tooling:
  distribution: compliance-tooling
  version: 0.3.0
  source:
    digest: sha256:{'1' * 64}
    digestAlgorithm: {TOOLING_SOURCE_DIGEST_ALGORITHM}
  artifact:
    kind: python-wheel
    sha256: sha256:{'2' * 64}
policySources:
  shared:
    distribution: compliance-policy
    version: 0.2.0
    content:
      digest: {digest}
      digestAlgorithm: compliance.example/policy-source-tree-digest/v1alpha1
""",
            encoding="utf-8",
        )
        identity = ToolingReleaseIdentity(
            schema="compliance.example/tooling-release-metadata/v2",
            distribution="compliance-tooling",
            cli="compliance",
            version="0.3.0",
            source_digest="sha256:" + "1" * 64,
            source_digest_algorithm=TOOLING_SOURCE_DIGEST_ALGORITHM,
            tested_opa_version="1.18.2",
        )
        return policy, target, digest, load_release_lock(lock), identity

    def test_configured_digest_must_equal_locked_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            policy, _, _, lock, identity = self._fixture(Path(temporary))
            report = validate_release_composition(
                lock,
                (PolicySource("shared", policy, "sha256:" + "f" * 64),),
                installed_identity=identity,
            )
            self.assertFalse(report["valid"])
            self.assertIn(
                "configured-policy-digest-mismatch",
                {error["type"] for error in report["errors"]},
            )

    def test_materialized_bytes_must_equal_locked_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            policy, target, digest, lock, identity = self._fixture(Path(temporary))
            target.write_text('{"value":2}\n', encoding="utf-8")
            report = validate_release_composition(
                lock,
                (PolicySource("shared", policy, digest),),
                installed_identity=identity,
            )
            self.assertFalse(report["valid"])
            self.assertIn(
                "materialized-policy-digest-mismatch",
                {error["type"] for error in report["errors"]},
            )
            self.assertNotEqual(report["policy_sources"][0]["actual_digest"], digest)

    def test_v1alpha2_requires_every_policy_source_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "compliance.yaml"
            source.write_text(
                """\
schema: compliance.example/project-config/v1alpha2
policySources:
  - name: shared
    path: materialized/shared
paths:
  inventory: inventory
  assignments: assignments
  evidence: generated/evidence
  plan: generated/plans
  results: generated/results
  waivers: waivers
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ProjectConfigError, "digest.*required"):
                load_config(source)

    def test_v1alpha2_rejects_legacy_policies_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "compliance.yaml"
            source.write_text(
                f"""\
schema: compliance.example/project-config/v1alpha2
policySources:
  - name: shared
    path: materialized/shared
    digest: sha256:{'a' * 64}
paths:
  inventory: inventory
  assignments: assignments
  policies: legacy/policy
  evidence: generated/evidence
  plan: generated/plans
  results: generated/results
  waivers: waivers
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ProjectConfigError, "policies"):
                load_config(source)

    def test_locked_override_detection_covers_equals_form(self) -> None:
        for flag in ("--policy-source", "--policies", "--resource-schema"):
            self.assertTrue(_argument_uses_flag(flag, flag))
            self.assertTrue(_argument_uses_flag(flag + "=value", flag))
            self.assertFalse(_argument_uses_flag(flag + "-other", flag))


if __name__ == "__main__":
    unittest.main()
