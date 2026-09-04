from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.release_artifacts import (
    CHECKSUMS_FILENAME,
    MANIFEST_FILENAME,
    RELEASE_MANIFEST_SCHEMA,
    ToolingReleaseError,
    release_tag_version,
    validate_release_manifest,
    verify_release_payload,
)
from tools.tooling_source import TOOLING_SOURCE_DIGEST_ALGORITHM


SOURCE_SHA = "a" * 40
SOURCE_DIGEST = "sha256:" + "3" * 64


class ToolingReleaseTests(unittest.TestCase):
    def _manifest_v2(self, wheel_name: str, wheel_digest: str, *, metadata: bool = True) -> dict:
        document = {
            "schema": RELEASE_MANIFEST_SCHEMA,
            "distribution": "compliance-tooling",
            "cli": "compliance",
            "version": "0.3.0",
            "source": {
                "digest": SOURCE_DIGEST,
                "digestAlgorithm": TOOLING_SOURCE_DIGEST_ALGORITHM,
            },
            "artifact": {
                "kind": "python-wheel",
                "filename": wheel_name,
                "sha256": f"sha256:{wheel_digest}",
            },
            "testedOpaVersion": "1.18.2",
        }
        if metadata:
            document["sourceMetadata"] = {
                "gitTag": "v0.3.0",
                "gitCommit": SOURCE_SHA,
            }
        return document

    def _write_wheel_v2(self, root: Path) -> Path:
        wheel = root / "compliance_tooling-0.3.0-py3-none-any.whl"
        dist_info = "compliance_tooling-0.3.0.dist-info"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr(
                f"{dist_info}/METADATA",
                "Metadata-Version: 2.4\nName: compliance-tooling\nVersion: 0.3.0\n",
            )
            archive.writestr(
                f"{dist_info}/entry_points.txt",
                "[console_scripts]\ncompliance = tools.cli:main\n",
            )
            archive.writestr(
                "tools/release-metadata.json",
                json.dumps({
                    "schema": "compliance.example/tooling-release-metadata/v2",
                    "source_digest": SOURCE_DIGEST,
                    "source_digest_algorithm": TOOLING_SOURCE_DIGEST_ALGORITHM,
                    "tested_opa_version": "1.18.2",
                }),
            )
        return wheel

    def _sha256(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _write_payload_v2(self, root: Path) -> tuple[Path, dict]:
        wheel = self._write_wheel_v2(root)
        manifest = self._manifest_v2(wheel.name, self._sha256(wheel))
        self._write_manifest_and_sums(root, wheel, manifest)
        return wheel, manifest

    def _write_manifest_and_sums(self, root: Path, wheel: Path, manifest: dict) -> None:
        manifest_path = root / MANIFEST_FILENAME
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        checksums = {
            wheel.name: self._sha256(wheel),
            MANIFEST_FILENAME: self._sha256(manifest_path),
        }
        (root / CHECKSUMS_FILENAME).write_text(
            "".join(
                f"{digest}  {filename}\n"
                for filename, digest in sorted(checksums.items())
            ),
            encoding="utf-8",
        )

    def test_release_tag_requires_strict_v_semver(self) -> None:
        self.assertEqual(release_tag_version("v0.2.0"), "0.2.0")
        self.assertEqual(release_tag_version("v1.2.3-rc.1+build.7"), "1.2.3-rc.1+build.7")
        for invalid in ("0.2.0", "release-v0.2.0", "v01.2.0", "v1.2"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ToolingReleaseError):
                    release_tag_version(invalid)

    def test_v2_manifest_is_content_addressed_and_git_metadata_optional(self) -> None:
        with_metadata = self._manifest_v2(
            "compliance_tooling-0.3.0-py3-none-any.whl",
            "1" * 64,
        )
        without_metadata = self._manifest_v2(
            "compliance_tooling-0.3.0-py3-none-any.whl",
            "1" * 64,
            metadata=False,
        )
        validate_release_manifest(with_metadata)
        validate_release_manifest(without_metadata)
        self.assertEqual(with_metadata["source"], without_metadata["source"])
        self.assertEqual(with_metadata["artifact"], without_metadata["artifact"])
        self.assertNotIn("tag", with_metadata)
        self.assertNotIn("sourceGitSha", with_metadata)

        for field in ("publisher", "githubReleaseId", "downloadUrl", "repositoryUrl"):
            invalid = dict(with_metadata)
            invalid[field] = "provider-specific"
            with self.subTest(field=field):
                with self.assertRaisesRegex(ToolingReleaseError, "schema validation failed"):
                    validate_release_manifest(invalid)

    def test_historical_v1_manifest_is_unsupported(self) -> None:
        with self.assertRaisesRegex(
            ToolingReleaseError,
            "unsupported tooling release manifest schema",
        ):
            validate_release_manifest({
                "schema": "compliance.example/tooling-release-manifest/v1",
            })

    def test_v2_git_tag_metadata_must_match_version(self) -> None:
        manifest = self._manifest_v2(
            "compliance_tooling-0.3.0-py3-none-any.whl",
            "1" * 64,
        )
        manifest["sourceMetadata"]["gitTag"] = "v0.3.1"
        with self.assertRaisesRegex(ToolingReleaseError, "does not match manifest version"):
            validate_release_manifest(manifest)

    def test_verifies_v2_exact_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, expected = self._write_payload_v2(root)
            self.assertEqual(verify_release_payload(root), expected)
            (root / "provider-state.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ToolingReleaseError, "exactly wheel, manifest"):
                verify_release_payload(root)

    def test_tampered_v2_wheel_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wheel, _ = self._write_payload_v2(root)
            wheel.write_bytes(wheel.read_bytes() + b"tampered")
            with self.assertRaisesRegex(ToolingReleaseError, "manifest wheel digest mismatch"):
                verify_release_payload(root)


if __name__ == "__main__":
    unittest.main()
