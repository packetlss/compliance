from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from tools.policy_source_release import (
    POLICY_SOURCE_ARCHIVE_FORMAT,
    POLICY_SOURCE_RELEASE_SCHEMA,
    PolicySourceReleaseError,
    load_policy_source_release,
    normalize_policy_source_release,
    policy_source_release_schema_path,
    validate_policy_source_archive,
)
from tools.policy_sources import source_tree_digest
from tools.release_lock import POLICY_SOURCE_DIGEST_ALGORITHM


ZERO_DIGEST = "sha256:" + "0" * 64


def archive_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def policy_digest(files: dict[str, bytes]) -> str:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for relative, content in files.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        return source_tree_digest(root)


def write_archive(
    path: Path,
    entries: list[tuple[str, bytes | None, bytes]],
    *,
    mtime: int = 0,
    uid: int = 0,
    gid: int = 0,
    uname: str = "",
    gname: str = "",
    directory_mode: int = 0o755,
    file_mode: int = 0o644,
    pax_headers: dict[str, str] | None = None,
    gzip_mtime: int = 0,
    gzip_filename: str = "",
    gzip_os: int = 255,
    compresslevel: int = 9,
) -> None:
    """Write (name, content, tar type) entries for validation fixtures."""
    with path.open("wb") as raw:
        with gzip.GzipFile(
            filename=gzip_filename,
            mode="wb",
            fileobj=raw,
            compresslevel=compresslevel,
            mtime=gzip_mtime,
        ) as compressed:
            with tarfile.open(
                fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT
            ) as archive:
                for name, content, entry_type in entries:
                    if entry_type == tarfile.DIRTYPE and not name.endswith("/"):
                        name += "/"
                    info = tarfile.TarInfo(name)
                    info.type = entry_type
                    info.mtime = mtime
                    info.uid = uid
                    info.gid = gid
                    info.uname = uname
                    info.gname = gname
                    info.pax_headers = dict(pax_headers or {})
                    if entry_type == tarfile.DIRTYPE:
                        info.mode = directory_mode
                        archive.addfile(info)
                    elif entry_type == tarfile.REGTYPE:
                        assert content is not None
                        info.mode = file_mode
                        info.size = len(content)
                        archive.addfile(info, io.BytesIO(content))
                    else:
                        info.mode = file_mode
                        if entry_type in {tarfile.SYMTYPE, tarfile.LNKTYPE}:
                            info.linkname = "policy/target"
                        archive.addfile(info)
    if gzip_os != 255:
        archive_bytes = bytearray(path.read_bytes())
        archive_bytes[9] = gzip_os
        path.write_bytes(archive_bytes)


def generic_manifest(
    *,
    distribution: str = "org.example/policy-pack",
    version: str = "1.2.3",
    digest: str = ZERO_DIGEST,
    representations: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    document: dict[str, object] = {
        "schema": POLICY_SOURCE_RELEASE_SCHEMA,
        "distribution": distribution,
        "version": version,
        "content": {
            "digest": digest,
            "digestAlgorithm": POLICY_SOURCE_DIGEST_ALGORITHM,
        },
    }
    if representations is not None:
        document["representations"] = representations
    return document


def archive_representation(filename: str, digest: str) -> dict[str, str]:
    return {
        "kind": "archive",
        "format": POLICY_SOURCE_ARCHIVE_FORMAT,
        "contentRoot": "policy",
        "filename": filename,
        "sha256": digest,
    }


class PolicySourceReleaseManifestTests(unittest.TestCase):
    def test_arbitrary_distribution_identities_use_the_same_model(self) -> None:
        first = normalize_policy_source_release(
            generic_manifest(distribution="Vendor/Pack")
        )
        second = normalize_policy_source_release(
            generic_manifest(distribution="internal.source:Blue-Team")
        )

        self.assertEqual(type(first), type(second))
        self.assertEqual(first.distribution, "Vendor/Pack")
        self.assertEqual(second.distribution, "internal.source:Blue-Team")
        self.assertEqual(set(first.semantic_document()), {"distribution", "version", "content"})

    def test_invalid_generic_semantic_fields_fail_visibly(self) -> None:
        invalid_documents: list[tuple[str, dict[str, object]]] = []
        empty_distribution = generic_manifest(distribution="")
        invalid_documents.append(("distribution", empty_distribution))
        invalid_documents.append(("version", generic_manifest(version="01.2.3")))
        malformed_digest = generic_manifest()
        malformed_digest["content"] = {
            "digest": "sha256:ABC",
            "digestAlgorithm": POLICY_SOURCE_DIGEST_ALGORITHM,
        }
        invalid_documents.append(("digest", malformed_digest))
        wrong_algorithm = generic_manifest()
        wrong_algorithm["content"] = {
            "digest": ZERO_DIGEST,
            "digestAlgorithm": "compliance.example/other/v1",
        }
        invalid_documents.append(("digestAlgorithm", wrong_algorithm))
        discarded_algorithm = generic_manifest()
        discarded_algorithm["content"] = {
            "digest": ZERO_DIGEST,
            "digestAlgorithm": "compliance.example/policy-source-tree-digest/v1",
        }
        invalid_documents.append(("discarded digestAlgorithm", discarded_algorithm))

        for field, document in invalid_documents:
            with self.subTest(field=field):
                with self.assertRaisesRegex(
                    PolicySourceReleaseError, "schema validation failed"
                ):
                    normalize_policy_source_release(document)

    def test_unsafe_filename_and_unsupported_format_fail(self) -> None:
        for filename in (
            "",
            ".",
            "..",
            "/absolute",
            "C:drive-relative",
            "nested/archive",
            "nested\\archive",
        ):
            with self.subTest(filename=filename):
                document = generic_manifest(
                    representations=[archive_representation(filename, ZERO_DIGEST)]
                )
                with self.assertRaisesRegex(PolicySourceReleaseError, "schema validation failed"):
                    normalize_policy_source_release(document)

        representation = archive_representation("opaque.asset", ZERO_DIGEST)
        representation["format"] = "compliance.example/unsupported/v1"
        with self.assertRaisesRegex(PolicySourceReleaseError, "schema validation failed"):
            normalize_policy_source_release(
                generic_manifest(representations=[representation])
            )

    def test_conflicting_representations_for_one_filename_fail(self) -> None:
        first = archive_representation("opaque.asset", ZERO_DIGEST)
        second = archive_representation("opaque.asset", "sha256:" + "1" * 64)
        with self.assertRaisesRegex(PolicySourceReleaseError, "conflicting representations"):
            normalize_policy_source_release(
                generic_manifest(representations=[first, second])
            )

    def test_provider_role_and_compatibility_metadata_are_not_in_v1(self) -> None:
        for field in (
            "downloadUrl",
            "providerUrl",
            "repository",
            "sourceRole",
            "policySourceDependencies",
            "toolingCompatibility",
            "signature",
        ):
            with self.subTest(field=field):
                document = generic_manifest()
                document[field] = "not part of the generic contract"
                with self.assertRaisesRegex(
                    PolicySourceReleaseError, "schema validation failed"
                ):
                    normalize_policy_source_release(document)

        document = generic_manifest()
        document["sourceMetadata"] = {"repositoryUrl": "not source navigation"}
        with self.assertRaisesRegex(PolicySourceReleaseError, "schema validation failed"):
            normalize_policy_source_release(document)

    def test_source_metadata_is_noncanonical_and_fields_are_independent(self) -> None:
        base = generic_manifest()
        without = normalize_policy_source_release(base)
        for metadata in (
            {},
            {"gitTag": "release-navigation"},
            {"gitCommit": "a" * 40},
            {"gitTag": "release-navigation", "gitCommit": "b" * 64},
        ):
            with self.subTest(metadata=metadata):
                document = copy.deepcopy(base)
                document["sourceMetadata"] = metadata
                release = normalize_policy_source_release(document)
                self.assertEqual(release.semantic_document(), without.semantic_document())
                self.assertEqual(
                    release.release_lock_policy_source(), without.release_lock_policy_source()
                )

        invalid = copy.deepcopy(base)
        invalid["sourceMetadata"] = {"gitCommit": "abbreviated"}
        with self.assertRaisesRegex(PolicySourceReleaseError, "schema validation failed"):
            normalize_policy_source_release(invalid)

    def test_producer_specific_historical_manifests_are_unsupported(self) -> None:
        for schema_name, distribution in (
            ("compliance.example/policy-release-manifest/v1", "compliance-policy"),
            (
                "compliance.example/verification-policy-release-manifest/v1",
                "compliance-verification-policy",
            ),
        ):
            with self.subTest(schema=schema_name):
                document = generic_manifest(distribution=distribution)
                document["schema"] = schema_name
                with self.assertRaisesRegex(
                    PolicySourceReleaseError,
                    "unsupported policy-source release manifest schema",
                ):
                    normalize_policy_source_release(document)
                with tempfile.TemporaryDirectory() as temporary:
                    manifest = Path(temporary) / "historical-manifest.json"
                    manifest.write_text(json.dumps(document), encoding="utf-8")
                    with self.assertRaisesRegex(
                        PolicySourceReleaseError,
                        "unsupported policy-source release manifest schema",
                    ):
                        load_policy_source_release(manifest)

    def test_schema_resolution_is_package_relative(self) -> None:
        path = policy_source_release_schema_path()
        self.assertTrue(path.is_file(), path)
        self.assertEqual(path.parent.name, "schemas")


class PolicySourceArchiveTests(unittest.TestCase):
    def test_different_archive_bytes_can_represent_identical_content(self) -> None:
        files = {"controls/example.rego": b"package example\n"}
        digest = policy_digest(files)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_path = root / "first.local"
            second_path = root / "second.local"
            entries = [
                ("policy", None, tarfile.DIRTYPE),
                ("policy/controls", None, tarfile.DIRTYPE),
                ("policy/controls/example.rego", files["controls/example.rego"], tarfile.REGTYPE),
            ]
            write_archive(first_path, entries, compresslevel=1)
            write_archive(second_path, entries, compresslevel=9)
            self.assertNotEqual(first_path.read_bytes(), second_path.read_bytes())

            document = generic_manifest(
                distribution="CaseSensitive/Distribution",
                digest=digest,
                representations=[
                    archive_representation("opaque-one.asset", archive_sha256(first_path)),
                    archive_representation("opaque-two.asset", archive_sha256(second_path)),
                ],
            )
            release = normalize_policy_source_release(document)
            first = validate_policy_source_archive(
                release, release.representations[0], first_path
            )
            destination = root / "build" / "consumer-selected-source"
            second = validate_policy_source_archive(
                release,
                release.representations[1],
                second_path,
                materialize_to=destination,
            )

            self.assertEqual(first.content_digest, digest)
            self.assertEqual(second.content_digest, digest)
            self.assertEqual(source_tree_digest(destination), digest)
            self.assertEqual(second.materialized_path, destination.resolve())

    def test_non_normalized_gzip_metadata_fails(self) -> None:
        invalid_metadata = {
            "timestamp": {"gzip_mtime": 1},
            "embedded-filename": {"gzip_filename": "policy-source.tar"},
            "platform-os": {"gzip_os": 3},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, options in invalid_metadata.items():
                with self.subTest(name=name):
                    archive_path = root / name
                    write_archive(
                        archive_path,
                        [
                            ("policy", None, tarfile.DIRTYPE),
                            ("policy/content", b"content", tarfile.REGTYPE),
                        ],
                        **options,
                    )
                    release = normalize_policy_source_release(
                        generic_manifest(
                            representations=[
                                archive_representation(name, archive_sha256(archive_path))
                            ]
                        )
                    )
                    with self.assertRaisesRegex(
                        PolicySourceReleaseError, "gzip metadata is not normalized"
                    ):
                        validate_policy_source_archive(
                            release, release.representations[0], archive_path
                        )

    def test_non_normalized_tar_metadata_fails(self) -> None:
        invalid_metadata = {
            "timestamp": {"mtime": 1},
            "user-id": {"uid": 1},
            "group-id": {"gid": 1},
            "user-name": {"uname": "owner"},
            "group-name": {"gname": "group"},
            "directory-mode": {"directory_mode": 0o700},
            "file-mode": {"file_mode": 0o600},
            "pax-metadata": {"pax_headers": {"comment": "not canonical"}},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, options in invalid_metadata.items():
                with self.subTest(name=name):
                    archive_path = root / name
                    write_archive(
                        archive_path,
                        [
                            ("policy", None, tarfile.DIRTYPE),
                            ("policy/content", b"content", tarfile.REGTYPE),
                        ],
                        **options,
                    )
                    release = normalize_policy_source_release(
                        generic_manifest(
                            representations=[
                                archive_representation(name, archive_sha256(archive_path))
                            ]
                        )
                    )
                    with self.assertRaisesRegex(
                        PolicySourceReleaseError, "tar metadata is not normalized"
                    ):
                        validate_policy_source_archive(
                            release, release.representations[0], archive_path
                        )

    def test_missing_root_and_non_normalized_member_order_fail(self) -> None:
        invalid_archives = {
            "missing-root": (
                [("policy/content", b"content", tarfile.REGTYPE)],
                {},
                "lacks policy/ content root",
            ),
            "unsorted": (
                [
                    ("policy", None, tarfile.DIRTYPE),
                    ("policy/z", b"z", tarfile.REGTYPE),
                    ("policy/a", b"a", tarfile.REGTYPE),
                ],
                {},
                "entries are not in normalized order",
            ),
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, (entries, options, expected_error) in invalid_archives.items():
                with self.subTest(name=name):
                    archive_path = root / name
                    write_archive(archive_path, entries, **options)
                    release = normalize_policy_source_release(
                        generic_manifest(
                            representations=[
                                archive_representation(name, archive_sha256(archive_path))
                            ]
                        )
                    )
                    with self.assertRaisesRegex(
                        PolicySourceReleaseError, expected_error
                    ):
                        validate_policy_source_archive(
                            release, release.representations[0], archive_path
                        )

    def test_representation_digest_mismatch_fails_before_archive_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "not-an-archive"
            archive_path.write_bytes(b"not a tar archive")
            release = normalize_policy_source_release(
                generic_manifest(
                    representations=[archive_representation("opaque", ZERO_DIGEST)]
                )
            )
            with self.assertRaisesRegex(
                PolicySourceReleaseError, "representation digest mismatch"
            ):
                validate_policy_source_archive(
                    release, release.representations[0], archive_path
                )

    def test_content_digest_mismatch_fails_after_exact_archive_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "archive"
            write_archive(
                archive_path,
                [
                    ("policy", None, tarfile.DIRTYPE),
                    ("policy/content.txt", b"actual", tarfile.REGTYPE),
                ],
            )
            release = normalize_policy_source_release(
                generic_manifest(
                    digest=ZERO_DIGEST,
                    representations=[
                        archive_representation("opaque", archive_sha256(archive_path))
                    ],
                )
            )
            with self.assertRaisesRegex(PolicySourceReleaseError, "content digest mismatch"):
                validate_policy_source_archive(
                    release, release.representations[0], archive_path
                )

    def test_unsafe_paths_generated_content_and_special_entries_fail(self) -> None:
        invalid_entries = {
            "traversal": ("policy/../escape", b"bad", tarfile.REGTYPE),
            "absolute": ("/policy/escape", b"bad", tarfile.REGTYPE),
            "outside-root": ("other/escape", b"bad", tarfile.REGTYPE),
            "build": ("policy/build/generated", b"bad", tarfile.REGTYPE),
            "pycache": ("policy/controls/__pycache__/generated", b"bad", tarfile.REGTYPE),
            "symlink": ("policy/link", None, tarfile.SYMTYPE),
            "hard-link": ("policy/link", None, tarfile.LNKTYPE),
            "fifo": ("policy/pipe", None, tarfile.FIFOTYPE),
            "device": ("policy/device", None, tarfile.CHRTYPE),
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, invalid_entry in invalid_entries.items():
                with self.subTest(name=name):
                    archive_path = root / f"{name}.archive"
                    write_archive(
                        archive_path,
                        [("policy", None, tarfile.DIRTYPE), invalid_entry],
                    )
                    release = normalize_policy_source_release(
                        generic_manifest(
                            representations=[
                                archive_representation(
                                    f"opaque-{name}", archive_sha256(archive_path)
                                )
                            ]
                        )
                    )
                    with self.assertRaises(PolicySourceReleaseError):
                        validate_policy_source_archive(
                            release, release.representations[0], archive_path
                        )

    def test_archive_filename_does_not_select_distribution_or_version(self) -> None:
        files = {"content.txt": b"content"}
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "local-cache-name"
            write_archive(
                archive_path,
                [
                    ("policy", None, tarfile.DIRTYPE),
                    ("policy/content.txt", files["content.txt"], tarfile.REGTYPE),
                ],
            )
            release = normalize_policy_source_release(
                generic_manifest(
                    distribution="Unrelated/Distribution",
                    version="9.8.7",
                    digest=policy_digest(files),
                    representations=[
                        archive_representation("totally-opaque.asset", archive_sha256(archive_path))
                    ],
                )
            )
            result = validate_policy_source_archive(
                release, release.representations[0], archive_path
            )

            self.assertEqual(release.distribution, "Unrelated/Distribution")
            self.assertEqual(release.version, "9.8.7")
            self.assertEqual(result.representation_sha256, archive_sha256(archive_path))


if __name__ == "__main__":
    unittest.main()
