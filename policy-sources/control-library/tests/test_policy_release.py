from __future__ import annotations

import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from policy_release import (  # noqa: E402
    ARCHIVE_FORMAT,
    CHECKSUMS_FILENAME,
    DISTRIBUTION_NAME,
    RELEASE_MANIFEST_FILENAME,
    RELEASE_MANIFEST_SCHEMA,
    PolicyReleaseError,
    canonical_content_identity,
    prepare_release_payload,
    release_tag_version,
    validate_release_manifest,
    verify_release_payload,
)
from tools.policy_source_release import (  # noqa: E402
    POLICY_SOURCE_ARCHIVE_FORMAT,
    POLICY_SOURCE_RELEASE_SCHEMA,
    normalize_policy_source_release,
    validate_policy_source_archive,
)
from tools.policy_sources import source_tree_digest  # noqa: E402
from tools.composition import POLICY_SOURCE_DIGEST_ALGORITHM  # noqa: E402


SOURCE_SHA = "a" * 40
OTHER_SOURCE_SHA = "b" * 40
VERSION = "0.4.0"
CANDIDATE_CONTENT_DIGEST = (
    "sha256:8a642adf280d3ee69e7d803c77f0fada1db81208939571691447bda0056edd6c"
)
CANDIDATE_ARCHIVE_SHA256 = (
    "sha256:cbdb576f79213882bf59e4351790d28df76198edb6970e6eedcbd0be7ba0d25c"
)


class PolicyReleaseTests(unittest.TestCase):
    def _policy_root(self, root: Path) -> Path:
        policy = root / "policies"
        controls = policy / "controls"
        schemas = policy / "schemas"
        controls.mkdir(parents=True)
        schemas.mkdir(parents=True)
        (controls / "example.rego").write_text(
            "package compliance.example\n",
            encoding="utf-8",
        )
        (schemas / "example.schema.json").write_text(
            '{"type":"object"}\n',
            encoding="utf-8",
        )
        return policy

    def _base_manifest(self) -> dict[str, object]:
        return {
            "schema": RELEASE_MANIFEST_SCHEMA,
            "distribution": DISTRIBUTION_NAME,
            "version": VERSION,
            "content": {
                "digest": "sha256:" + "2" * 64,
                "digestAlgorithm": POLICY_SOURCE_DIGEST_ALGORITHM,
            },
        }

    def test_forward_constants_are_the_accepted_generic_identity(self) -> None:
        self.assertEqual(DISTRIBUTION_NAME, "compliance-control-library")
        self.assertEqual(RELEASE_MANIFEST_SCHEMA, POLICY_SOURCE_RELEASE_SCHEMA)
        self.assertEqual(ARCHIVE_FORMAT, POLICY_SOURCE_ARCHIVE_FORMAT)
        self.assertEqual(
            POLICY_SOURCE_DIGEST_ALGORITHM,
            "compliance.example/policy-source-tree-digest/v1alpha1",
        )
        self.assertFalse(
            (ROOT / "release/policy-source-release-manifest.schema.json").exists()
        )

    def test_optional_source_metadata_tag_requires_strict_v_semver(self) -> None:
        self.assertEqual(release_tag_version("v0.4.0"), "0.4.0")
        self.assertEqual(
            release_tag_version("v1.2.3-rc.1+build.7"),
            "1.2.3-rc.1+build.7",
        )
        for invalid in ("0.4.0", "release-v0.4.0", "v01.2.0", "v1.2"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(PolicyReleaseError):
                    release_tag_version(invalid)

    def test_forward_manifest_uses_tooling_model_and_exact_semantic_projection(self) -> None:
        manifest = self._base_manifest()
        manifest["sourceMetadata"] = {"gitCommit": SOURCE_SHA}
        self.assertIs(validate_release_manifest(manifest), manifest)
        normalized = normalize_policy_source_release(manifest)
        self.assertEqual(
            normalized.semantic_document(),
            {
                "distribution": DISTRIBUTION_NAME,
                "version": VERSION,
                "content": manifest["content"],
            },
        )
        self.assertEqual(canonical_content_identity(manifest), manifest["content"])

        invalid = dict(manifest)
        invalid["repositoryUrl"] = "https://provider.invalid/source"
        with self.assertRaisesRegex(PolicyReleaseError, "schema validation failed"):
            validate_release_manifest(invalid)

    def test_descriptor_can_be_prepared_without_git_or_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            release_dir = Path(temporary) / "release"
            policy = self._policy_root(root)
            manifest = prepare_release_payload(
                root,
                version=VERSION,
                output_dir=release_dir,
            )
            self.assertEqual(
                verify_release_payload(release_dir, policy_root=policy),
                manifest,
            )
            self.assertEqual(
                {path.name for path in release_dir.iterdir()},
                {RELEASE_MANIFEST_FILENAME, CHECKSUMS_FILENAME},
            )
            self.assertNotIn("sourceMetadata", manifest)
            self.assertNotIn("representations", manifest)
            self.assertEqual(manifest["content"]["digest"], source_tree_digest(policy))

    def test_current_source_digest_is_path_and_raw_byte_based(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            policy = self._policy_root(Path(temporary))
            original = source_tree_digest(policy)
            target = policy / "controls/example.rego"

            target.write_bytes(b"package compliance.changed\n")
            self.assertNotEqual(original, source_tree_digest(policy))

            target.write_bytes(b"package compliance.example\n")
            target.rename(target.with_name("renamed.rego"))
            self.assertNotEqual(original, source_tree_digest(policy))

    def test_current_source_digest_ignores_filesystem_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            policy = self._policy_root(Path(temporary))
            original = source_tree_digest(policy)
            target = policy / "controls/example.rego"
            target.chmod(0o600)
            os.utime(target, (1_700_000_000, 1_700_000_000))
            self.assertEqual(original, source_tree_digest(policy))

    def test_forward_archive_is_generic_deterministic_and_has_only_policy_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            first_dir = Path(temporary) / "first"
            second_dir = Path(temporary) / "second"
            policy = self._policy_root(root)

            first = prepare_release_payload(
                root,
                version=VERSION,
                output_dir=first_dir,
                git_tag="v0.4.0",
                git_commit=SOURCE_SHA,
                include_archive=True,
            )
            second = prepare_release_payload(
                root,
                version=VERSION,
                output_dir=second_dir,
                git_tag="v0.4.0",
                git_commit=OTHER_SOURCE_SHA,
                include_archive=True,
            )

            first_release = normalize_policy_source_release(first)
            representation = first_release.representations[0]
            archive = first_dir / representation.filename
            validation = validate_policy_source_archive(
                first_release,
                representation,
                archive,
            )
            self.assertEqual(validation.content_digest, source_tree_digest(policy))
            self.assertEqual(representation.format, POLICY_SOURCE_ARCHIVE_FORMAT)
            self.assertEqual(representation.content_root, "policy")
            self.assertNotEqual(representation.sha256, first["content"]["digest"])

            second_representation = normalize_policy_source_release(second).representations[0]
            second_archive = second_dir / second_representation.filename
            self.assertEqual(archive.read_bytes(), second_archive.read_bytes())
            self.assertEqual(representation.sha256, second_representation.sha256)
            self.assertNotEqual(first["sourceMetadata"], second["sourceMetadata"])
            self.assertEqual(canonical_content_identity(first), canonical_content_identity(second))

            with tarfile.open(archive, mode="r:gz") as payload:
                names = [member.name.rstrip("/") for member in payload.getmembers()]
            self.assertEqual(names[0], "policy")
            self.assertTrue(all(name == "policy" or name.startswith("policy/") for name in names))
            self.assertNotIn("manifest.json", names)

    def test_archive_does_not_require_git_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            release_dir = Path(temporary) / "release"
            self._policy_root(root)
            manifest = prepare_release_payload(
                root,
                version=VERSION,
                output_dir=release_dir,
                include_archive=True,
            )
            self.assertNotIn("sourceMetadata", manifest)
            self.assertEqual(len(manifest["representations"]), 1)

    def test_v0_4_0_candidate_identities_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = prepare_release_payload(
                ROOT,
                version=VERSION,
                output_dir=Path(temporary) / "release",
                include_archive=True,
            )
            self.assertEqual(manifest["content"]["digest"], CANDIDATE_CONTENT_DIGEST)
            self.assertEqual(
                manifest["representations"][0]["sha256"],
                CANDIDATE_ARCHIVE_SHA256,
            )

    def test_payload_rejects_extra_files_and_tampered_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            release_dir = Path(temporary) / "release"
            self._policy_root(root)
            manifest = prepare_release_payload(
                root,
                version=VERSION,
                output_dir=release_dir,
                include_archive=True,
            )
            extra = release_dir / "provider-state.json"
            extra.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(PolicyReleaseError, "contain exactly"):
                verify_release_payload(release_dir)
            extra.unlink()

            archive = release_dir / manifest["representations"][0]["filename"]
            archive.write_bytes(archive.read_bytes() + b"tampered")
            with self.assertRaisesRegex(PolicyReleaseError, "SHA256SUMS mismatch"):
                verify_release_payload(release_dir)

    def test_archive_source_rejects_digest_exclusions_and_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            policy = self._policy_root(root)
            generated = policy / "build"
            generated.mkdir()
            (generated / "ignored.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(PolicyReleaseError, "excluded by the canonical"):
                prepare_release_payload(
                    root,
                    version=VERSION,
                    output_dir=Path(temporary) / "generated-release",
                    include_archive=True,
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            policy = self._policy_root(root)
            link = policy / "controls/linked.rego"
            try:
                link.symlink_to(policy / "controls/example.rego")
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            with self.assertRaisesRegex(PolicyReleaseError, "symbolic links"):
                prepare_release_payload(
                    root,
                    version=VERSION,
                    output_dir=Path(temporary) / "linked-release",
                    include_archive=True,
                )

    def test_source_release_version_is_exactly_v0_4_0(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "should-not-exist"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/policy-release.py"),
                    "prepare",
                    "--version",
                    "0.2.0",
                    "--output-dir",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2, completed)
            self.assertIn(
                "does not match source release version '0.4.0'",
                completed.stderr,
            )
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
