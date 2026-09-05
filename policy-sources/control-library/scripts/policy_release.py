"""Prepare and verify standard control-library policy-source releases.

The generic manifest model, schema validation, archive validation, and canonical
policy-tree digest are owned by ``compliance-tooling``. This module contains
only the producer-specific construction and payload/checksum mechanics for the
``compliance-control-library`` distribution.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import re
import stat
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from tools.policy_source_release import (
    POLICY_SOURCE_ARCHIVE_FORMAT,
    POLICY_SOURCE_RELEASE_SCHEMA,
    PolicySourceArchiveRepresentation,
    PolicySourceRelease,
    PolicySourceReleaseError,
    normalize_policy_source_release,
    validate_policy_source_archive,
)
from tools.policy_sources import source_tree_digest
from tools.composition import POLICY_SOURCE_DIGEST_ALGORITHM


DISTRIBUTION_NAME = "compliance-control-library"
RELEASE_MANIFEST_SCHEMA = POLICY_SOURCE_RELEASE_SCHEMA
RELEASE_MANIFEST_FILENAME = "policy-source-release-manifest.json"
CHECKSUMS_FILENAME = "SHA256SUMS"
ARCHIVE_REPRESENTATION_KIND = "archive"
ARCHIVE_FORMAT = POLICY_SOURCE_ARCHIVE_FORMAT
CONTENT_ROOT = "policy"
EXCLUDED_SOURCE_COMPONENTS = frozenset({"build", "__pycache__"})
_CHECKSUM_LINE = re.compile(
    r"^(?P<digest>[0-9a-f]{64})  (?P<filename>[A-Za-z0-9._+-]+)$"
)


class PolicyReleaseError(ValueError):
    """Raised when a control-library release violates its producer contract."""


@dataclass(frozen=True)
class _TreeEntry:
    relative: PurePosixPath
    path: Path
    is_dir: bool


def _normalize_forward_manifest(document: Any) -> PolicySourceRelease:
    """Use the tooling-owned generic validator, then enforce producer identity."""
    try:
        release = normalize_policy_source_release(document)
    except PolicySourceReleaseError as error:
        raise PolicyReleaseError(str(error)) from error
    if release.manifest_schema != RELEASE_MANIFEST_SCHEMA:
        raise PolicyReleaseError(
            "forward control-library releases require manifest schema "
            f"{RELEASE_MANIFEST_SCHEMA!r}"
        )
    if release.distribution != DISTRIBUTION_NAME:
        raise PolicyReleaseError(
            f"unexpected control-library distribution: {release.distribution!r}"
        )
    return release


def _validate_version(version: str) -> None:
    _normalize_forward_manifest(
        {
            "schema": RELEASE_MANIFEST_SCHEMA,
            "distribution": DISTRIBUTION_NAME,
            "version": version,
            "content": {
                "digest": "sha256:" + "0" * 64,
                "digestAlgorithm": POLICY_SOURCE_DIGEST_ALGORITHM,
            },
        }
    )


def release_tag_version(tag: str) -> str:
    """Return the SemVer named by one ``v<SemVer>`` release tag."""
    if not isinstance(tag, str) or not tag.startswith("v"):
        raise PolicyReleaseError(f"release tag must be v<SemVer>: {tag!r}")
    version = tag[1:]
    try:
        _validate_version(version)
    except PolicyReleaseError as error:
        raise PolicyReleaseError(f"release tag must be v<SemVer>: {tag!r}") from error
    return version


def validate_release_manifest(document: Any) -> dict[str, Any]:
    """Validate one forward descriptor through the tooling-owned generic model."""
    if not isinstance(document, dict):
        raise PolicyReleaseError("policy-source release manifest must be an object")
    _normalize_forward_manifest(document)
    return document


def canonical_content_identity(document: Any) -> dict[str, str]:
    """Return the canonical policy content identity, excluding all metadata."""
    return _normalize_forward_manifest(document).content.document()


def _tree_entries(root: Path) -> tuple[_TreeEntry, ...]:
    if root.is_symlink():
        raise PolicyReleaseError(
            f"policy-source archive content root cannot be a symbolic link: {root}"
        )
    root = root.resolve()
    if not root.is_dir():
        raise PolicyReleaseError(f"policy source is not a directory: {root}")

    entries: list[_TreeEntry] = []
    pending = [(root, PurePosixPath("."))]
    while pending:
        directory, relative_directory = pending.pop()
        try:
            children = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as error:
            raise PolicyReleaseError(f"cannot inspect policy source {directory}: {error}") from error
        for child in children:
            relative = (
                PurePosixPath(child.name)
                if relative_directory == PurePosixPath(".")
                else relative_directory / child.name
            )
            if EXCLUDED_SOURCE_COMPONENTS.intersection(relative.parts):
                raise PolicyReleaseError(
                    "policy source contains a generated path excluded by the canonical "
                    f"digest contract: {relative.as_posix()}"
                )
            if child.is_symlink():
                raise PolicyReleaseError(
                    "policy-source archives do not support symbolic links: "
                    f"{relative.as_posix()}"
                )
            mode = child.stat(follow_symlinks=False).st_mode
            child_path = Path(child.path)
            if stat.S_ISDIR(mode):
                entries.append(_TreeEntry(relative, child_path, True))
                pending.append((child_path, relative))
            elif stat.S_ISREG(mode):
                entries.append(_TreeEntry(relative, child_path, False))
            else:
                raise PolicyReleaseError(
                    "policy-source archives support only regular files and directories: "
                    f"{relative.as_posix()}"
                )
    return tuple(sorted(entries, key=lambda entry: entry.relative.as_posix()))


def _tar_info(name: str, *, is_dir: bool, size: int = 0) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name=name + ("/" if is_dir and not name.endswith("/") else ""))
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mode = 0o755 if is_dir else 0o644
    info.type = tarfile.DIRTYPE if is_dir else tarfile.REGTYPE
    info.size = 0 if is_dir else size
    info.pax_headers = {}
    return info


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise PolicyReleaseError(f"cannot read release payload file {path}: {error}") from error
    return f"sha256:{digest.hexdigest()}"


def build_policy_source_archive(policy_root: Path, output_path: Path) -> str:
    """Build this producer's deterministic generic archive representation."""
    policy_root = policy_root.resolve()
    entries = _tree_entries(policy_root)
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.name + ".tmp")
    try:
        with temporary.open("wb") as raw:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw,
                compresslevel=9,
                mtime=0,
            ) as compressed:
                with tarfile.open(
                    fileobj=compressed,
                    mode="w",
                    format=tarfile.PAX_FORMAT,
                ) as archive:
                    archive.addfile(_tar_info(CONTENT_ROOT, is_dir=True))
                    for entry in entries:
                        archive_name = f"{CONTENT_ROOT}/{entry.relative.as_posix()}"
                        if entry.is_dir:
                            archive.addfile(_tar_info(archive_name, is_dir=True))
                            continue
                        payload = entry.path.read_bytes()
                        archive.addfile(
                            _tar_info(archive_name, is_dir=False, size=len(payload)),
                            io.BytesIO(payload),
                        )
        temporary.replace(output_path)
    except OSError as error:
        raise PolicyReleaseError(f"cannot build policy-source archive: {error}") from error
    finally:
        if temporary.exists():
            temporary.unlink()
    return _sha256(output_path)


def _checksum_entries(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise PolicyReleaseError(f"cannot read checksum file {path}: {error}") from error
    entries: dict[str, str] = {}
    for line in lines:
        match = _CHECKSUM_LINE.fullmatch(line)
        if match is None:
            raise PolicyReleaseError(f"invalid SHA256SUMS line: {line!r}")
        filename = match.group("filename")
        if filename in entries:
            raise PolicyReleaseError(f"duplicate SHA256SUMS entry: {filename}")
        entries[filename] = match.group("digest")
    return entries


def verify_release_payload(
    release_dir: Path,
    *,
    policy_root: Path | None = None,
) -> dict[str, Any]:
    """Verify descriptor/checksum bytes and every declared generic representation."""
    release_dir = release_dir.resolve()
    manifest_path = release_dir / RELEASE_MANIFEST_FILENAME
    checksums_path = release_dir / CHECKSUMS_FILENAME
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicyReleaseError(f"cannot read policy-source release manifest: {error}") from error
    release = _normalize_forward_manifest(document)

    representation_names = {item.filename for item in release.representations}
    expected_entries = representation_names | {
        RELEASE_MANIFEST_FILENAME,
        CHECKSUMS_FILENAME,
    }
    try:
        actual_paths = {path.name: path for path in release_dir.iterdir()}
    except OSError as error:
        raise PolicyReleaseError(f"cannot inspect release directory: {error}") from error
    if set(actual_paths) != expected_entries or any(
        not path.is_file() for path in actual_paths.values()
    ):
        raise PolicyReleaseError(
            "policy-source release payload must contain exactly its descriptor, "
            "SHA256SUMS, and declared representations; "
            f"expected {sorted(expected_entries)}, found {sorted(actual_paths)}"
        )

    checksum_entries = _checksum_entries(checksums_path)
    expected_checksum_names = representation_names | {RELEASE_MANIFEST_FILENAME}
    if set(checksum_entries) != expected_checksum_names:
        raise PolicyReleaseError(
            "SHA256SUMS must contain exactly the descriptor and declared "
            f"representations; expected {sorted(expected_checksum_names)}, "
            f"found {sorted(checksum_entries)}"
        )
    for filename in sorted(expected_checksum_names):
        actual = _sha256(release_dir / filename).removeprefix("sha256:")
        if checksum_entries[filename] != actual:
            raise PolicyReleaseError(
                f"SHA256SUMS mismatch for {filename}: "
                f"expected {checksum_entries[filename]}, actual {actual}"
            )

    for representation in release.representations:
        try:
            validate_policy_source_archive(
                release,
                representation,
                release_dir / representation.filename,
            )
        except PolicySourceReleaseError as error:
            raise PolicyReleaseError(str(error)) from error

    if policy_root is not None:
        try:
            materialized_digest = source_tree_digest(policy_root.resolve())
        except (OSError, ValueError) as error:
            raise PolicyReleaseError(
                f"cannot compute materialized policy content digest: {error}"
            ) from error
        if materialized_digest != release.content.digest:
            raise PolicyReleaseError(
                "materialized policy content digest mismatch: "
                f"manifest {release.content.digest}, actual {materialized_digest}"
            )
    return document


def prepare_release_payload(
    repository_root: Path,
    *,
    version: str,
    output_dir: Path,
    git_tag: str | None = None,
    git_commit: str | None = None,
    include_archive: bool = False,
) -> dict[str, Any]:
    """Prepare this producer's generic descriptor and optional archive."""
    repository_root = repository_root.resolve()
    output_dir = output_dir.resolve()
    _validate_version(version)
    if git_tag is not None and release_tag_version(git_tag) != version:
        raise PolicyReleaseError(
            f"source Git tag {git_tag!r} does not name release version {version!r}"
        )

    policy_root = repository_root / "policies"
    try:
        canonical_digest = source_tree_digest(policy_root)
    except (OSError, ValueError) as error:
        raise PolicyReleaseError(f"cannot identify policy content: {error}") from error

    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise PolicyReleaseError(f"release output directory must be empty: {output_dir}")

    manifest: dict[str, Any] = {
        "schema": RELEASE_MANIFEST_SCHEMA,
        "distribution": DISTRIBUTION_NAME,
        "version": version,
        "content": {
            "digest": canonical_digest,
            "digestAlgorithm": POLICY_SOURCE_DIGEST_ALGORITHM,
        },
    }
    source_metadata = {
        key: value
        for key, value in (("gitTag", git_tag), ("gitCommit", git_commit))
        if value is not None
    }
    if source_metadata:
        manifest["sourceMetadata"] = source_metadata

    if include_archive:
        archive_filename = f"{DISTRIBUTION_NAME}-{version}.tar.gz"
        archive_path = output_dir / archive_filename
        archive_digest = build_policy_source_archive(policy_root, archive_path)
        manifest["representations"] = [
            {
                "kind": ARCHIVE_REPRESENTATION_KIND,
                "format": ARCHIVE_FORMAT,
                "contentRoot": CONTENT_ROOT,
                "filename": archive_filename,
                "sha256": archive_digest,
            }
        ]

    release = _normalize_forward_manifest(manifest)
    if include_archive:
        representation_model: PolicySourceArchiveRepresentation = release.representations[0]
        try:
            validation = validate_policy_source_archive(
                release,
                representation_model,
                output_dir / representation_model.filename,
            )
        except PolicySourceReleaseError as error:
            raise PolicyReleaseError(str(error)) from error
        if validation.content_digest != canonical_digest:
            raise PolicyReleaseError(
                "archive materialization differs from canonical policy content"
            )

    manifest_path = output_dir / RELEASE_MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checksum_names = [RELEASE_MANIFEST_FILENAME]
    checksum_names.extend(item.filename for item in release.representations)
    checksums = {
        filename: _sha256(output_dir / filename).removeprefix("sha256:")
        for filename in checksum_names
    }
    (output_dir / CHECKSUMS_FILENAME).write_text(
        "".join(
            f"{digest}  {filename}\n"
            for filename, digest in sorted(checksums.items())
        ),
        encoding="utf-8",
    )
    return verify_release_payload(output_dir, policy_root=policy_root)
