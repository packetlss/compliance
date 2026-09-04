from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.policy_sources import PolicySource, source_tree_digest
from tools.project_config import (
    CONFIG_SCHEMA,
    CONFIG_SCHEMA_V1ALPHA2,
    ProjectConfigError,
    load_config,
    release_validation,
    select_config,
)
from tools.release import (
    RELEASE_METADATA_SCHEMA,
    ToolingReleaseIdentity,
)
from tools.release_lock import (
    LockedPolicySource,
    LockedTooling,
    POLICY_SOURCE_DIGEST_ALGORITHM,
    RELEASE_LOCK_DIGEST_ALGORITHM,
    RELEASE_LOCK_SCHEMA,
    ReleaseLock,
    load_release_lock,
    release_lock_digest,
    validate_release_composition,
)
from tools.tooling_source import TOOLING_SOURCE_DIGEST_ALGORITHM


TOOLING_ARTIFACT = "sha256:" + "2" * 64
TOOLING_SOURCE = "sha256:" + "3" * 64


class ReleaseLockTests(unittest.TestCase):
    def test_fixed_jcs_release_lock_vector(self) -> None:
        self.assertEqual(
            RELEASE_LOCK_DIGEST_ALGORITHM,
            "compliance.example/release-lock-digest/v1alpha1",
        )
        lock = ReleaseLock(
            source=Path("ignored/compliance.lock.yaml"),
            schema=RELEASE_LOCK_SCHEMA,
            tooling=LockedTooling(
                distribution="compliance-tooling",
                version="0.4.0",
                source_digest="sha256:" + "1" * 64,
                source_digest_algorithm=TOOLING_SOURCE_DIGEST_ALGORITHM,
                artifact_kind="python-wheel",
                artifact_sha256="sha256:" + "2" * 64,
            ),
            policy_sources=(
                LockedPolicySource(
                    name="zeta",
                    distribution="policy-z",
                    version="2.0.0",
                    source_digest="sha256:" + "c" * 64,
                ),
                LockedPolicySource(
                    name="alpha",
                    distribution="policy-a",
                    version="1.0.0",
                    source_digest="sha256:" + "b" * 64,
                ),
            ),
        )
        # Fixed with the RFC 8785 Appendix A ECMAScript canonicalizer and Node SHA-256.
        self.assertEqual(
            lock.digest(),
            "sha256:f33215b10dc4046f3a6bba43a08f9a0f5f21f7a0bdde50740527d8ae6ea06bc7",
        )

    def _policy_tree(self, root: Path) -> tuple[Path, str]:
        policy = root / "materialized" / "shared"
        (policy / "controls").mkdir(parents=True)
        (policy / "schemas").mkdir(parents=True)
        (policy / "controls" / "result.rego").write_text(
            "package compliance.result\n",
            encoding="utf-8",
        )
        (policy / "schemas" / "example.json").write_text(
            '{"type":"object"}\n',
            encoding="utf-8",
        )
        return policy, source_tree_digest(policy)

    def _lock_text_v2(self, source_digest: str, *, reverse: bool = False) -> str:
        tooling = f"""\
tooling:
  distribution: compliance-tooling
  version: 0.3.0
  source:
    digestAlgorithm: {TOOLING_SOURCE_DIGEST_ALGORITHM}
    digest: {TOOLING_SOURCE}
  artifact:
    kind: python-wheel
    sha256: {TOOLING_ARTIFACT}
"""
        policy = f"""\
policySources:
  shared:
    distribution: compliance-policy
    version: 0.2.0
    content:
      digestAlgorithm: {POLICY_SOURCE_DIGEST_ALGORITHM}
      digest: {source_digest}
"""
        parts = (policy, tooling) if reverse else (tooling, policy)
        return "schema: compliance.example/release-lock/v1alpha2\n" + parts[0] + parts[1]

    def _project_text(self, policy_digest: str) -> str:
        return f"""\
schema: compliance.example/project-config/v1alpha2
policySources:
  - name: shared
    path: materialized/shared
    digest: {policy_digest}
paths:
  inventory: inventory
  assignments: assignments
  evidence: generated/evidence
  plan: generated/plans
  results: generated/results
  waivers: waivers
"""

    def _identity_v2(self) -> ToolingReleaseIdentity:
        return ToolingReleaseIdentity(
            schema=RELEASE_METADATA_SCHEMA,
            distribution="compliance-tooling",
            cli="compliance",
            version="0.3.0",
            source_digest=TOOLING_SOURCE,
            source_digest_algorithm=TOOLING_SOURCE_DIGEST_ALGORITHM,
            tested_opa_version="1.18.2",
        )

    def test_historical_v1alpha1_lock_is_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "compliance.lock.yaml"
            source.write_text(
                "schema: compliance.example/release-lock/v1alpha1\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                Exception,
                "unsupported release lock schema.*release-lock/v1alpha1",
            ):
                load_release_lock(source)

    def test_v1alpha2_digest_is_format_order_and_path_independent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, digest = self._policy_tree(root)
            first_dir = root / "one"
            second_dir = root / "other/two"
            first_dir.mkdir(parents=True)
            second_dir.mkdir(parents=True)
            first = first_dir / "compliance.lock.yaml"
            second = second_dir / "compliance.lock.yaml"
            first.write_text(self._lock_text_v2(digest), encoding="utf-8")
            second.write_text(
                "# layout is not semantic\n" + self._lock_text_v2(digest, reverse=True),
                encoding="utf-8",
            )
            first_lock = load_release_lock(first)
            second_lock = load_release_lock(second)
            self.assertEqual(first_lock.schema, RELEASE_LOCK_SCHEMA)
            self.assertEqual(first_lock.semantic_document(), second_lock.semantic_document())
            self.assertEqual(first_lock.digest(), second_lock.digest())
            self.assertTrue(first_lock.digest().startswith("sha256:"))

    def test_v1alpha2_validates_installed_content_identity_and_materialized_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            policy, digest = self._policy_tree(root)
            lock_path = root / "compliance.lock.yaml"
            lock_path.write_text(self._lock_text_v2(digest), encoding="utf-8")
            report = validate_release_composition(
                load_release_lock(lock_path),
                (PolicySource("shared", policy, digest),),
                installed_identity=self._identity_v2(),
            )
            self.assertTrue(report["valid"], report)
            self.assertEqual(report["errors"], [])
            self.assertEqual(report["lock_schema"], RELEASE_LOCK_SCHEMA)
            self.assertEqual(report["schema"], "compliance.example/release-validation/v1alpha2")
            self.assertEqual(report["locked_tooling"]["source"]["digest"], TOOLING_SOURCE)
            self.assertNotIn("sourceGitSha", report["locked_tooling"])
            self.assertEqual(report["policy_sources"][0]["locked"]["content"]["digest"], digest)

    def test_v1alpha2_schema_rejects_git_provider_and_transport_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, digest = self._policy_tree(root)
            base = self._lock_text_v2(digest)
            for insertion in (
                f"  sourceGitSha: {'a' * 40}\n",
                "  repositoryUrl: https://example.invalid/tooling.git\n",
                "  gitTag: v0.3.0\n",
            ):
                path = root / "compliance.lock.yaml"
                path.write_text(base.replace("tooling:\n", "tooling:\n" + insertion), encoding="utf-8")
                with self.subTest(insertion=insertion):
                    with self.assertRaisesRegex(Exception, "schema validation failed"):
                        load_release_lock(path)

    def test_v1alpha2_rejects_discarded_development_digest_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, digest = self._policy_tree(root)
            active = self._lock_text_v2(digest)
            for provisional in (
                TOOLING_SOURCE_DIGEST_ALGORITHM,
                POLICY_SOURCE_DIGEST_ALGORITHM,
            ):
                with self.subTest(provisional=provisional):
                    path = root / "compliance.lock.yaml"
                    path.write_text(
                        active.replace(provisional, provisional.removesuffix("alpha1")),
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        Exception, "schema validation failed"
                    ):
                        load_release_lock(path)

    def test_development_tooling_cannot_satisfy_locked_composition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            policy, digest = self._policy_tree(root)
            development = ToolingReleaseIdentity(
                schema=RELEASE_METADATA_SCHEMA,
                distribution="compliance-tooling",
                cli="compliance",
                version="0.3.0",
                tested_opa_version="1.18.2",
                source_digest=None,
                source_digest_algorithm=TOOLING_SOURCE_DIGEST_ALGORITHM,
            )
            lock_path = root / "compliance.lock.yaml"
            lock_path.write_text(self._lock_text_v2(digest), encoding="utf-8")
            report = validate_release_composition(
                load_release_lock(lock_path),
                (PolicySource("shared", policy, digest),),
                installed_identity=development,
            )
            self.assertFalse(report["valid"])
            self.assertIn("tooling-release-unrecorded", {e["type"] for e in report["errors"]})

    def test_project_config_v1alpha2_accepts_current_lock_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, digest = self._policy_tree(root)
            source = root / "compliance.yaml"
            source.write_text(self._project_text(digest), encoding="utf-8")

            lock_path = root / "compliance.lock.yaml"
            lock_path.write_text(self._lock_text_v2(digest), encoding="utf-8")
            config_v2 = load_config(source)
            report_v2 = release_validation(config_v2, installed_identity=self._identity_v2())
            self.assertEqual(config_v2.schema, CONFIG_SCHEMA_V1ALPHA2)
            self.assertTrue(report_v2["valid"], report_v2)

    def test_v1alpha1_project_config_remains_structurally_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "compliance.yaml"
            source.write_text(
                """\
schema: compliance.example/project-config/v1alpha1
paths:
  inventory: inventory
  assignments: assignments
  policies: policy
  evidence: generated/evidence
  plan: generated/plans
  results: generated/results
  waivers: waivers
  resourceSchema: schema.json
""",
                encoding="utf-8",
            )
            config = load_config(source)
            self.assertEqual(config.schema, CONFIG_SCHEMA)
            self.assertIsNone(config.release_lock)
            self.assertIsNotNone(config.path("resourceSchema"))

    def test_v1alpha2_rejects_legacy_resource_schema_and_requires_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, digest = self._policy_tree(root)
            source = root / "compliance.yaml"
            source.write_text(
                self._project_text(digest).replace(
                    "  waivers: waivers\n",
                    "  waivers: waivers\n  resourceSchema: sibling.json\n",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ProjectConfigError, "resourceSchema"):
                load_config(source)
            source.write_text(self._project_text(digest), encoding="utf-8")
            with self.assertRaisesRegex(ProjectConfigError, "compliance.lock.yaml"):
                load_config(source)

    def test_normal_selection_enforces_locked_release_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, digest = self._policy_tree(root)
            (root / "compliance.lock.yaml").write_text(
                self._lock_text_v2(digest),
                encoding="utf-8",
            )
            (root / "compliance.yaml").write_text(
                self._project_text(digest),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ProjectConfigError, "locked release validation failed"):
                select_config([], cwd=root)


if __name__ == "__main__":
    unittest.main()
