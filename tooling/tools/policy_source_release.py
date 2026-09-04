"""Generic policy-source release manifests and local archive validation."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator

from .policy_sources import source_tree_digest
from .release_lock import POLICY_SOURCE_DIGEST_ALGORITHM


POLICY_SOURCE_RELEASE_SCHEMA = (
    "compliance.example/policy-source-release-manifest/v1"
)
POLICY_SOURCE_ARCHIVE_FORMAT = "compliance.example/policy-source-archive/v1"
_SCHEMA_FILENAME = "policy-source-release-manifest.schema.json"
_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")
_GENERATED_COMPONENTS = {"build", "__pycache__"}
_GZIP_HEADER_SIZE = 10
_GZIP_DEFLATE_METHOD = 8
_GZIP_NORMALIZED_FLAGS = 0
_GZIP_NORMALIZED_OS = 255
_ARCHIVE_DIRECTORY_MODE = 0o755
_ARCHIVE_FILE_MODE = 0o644


class PolicySourceReleaseError(ValueError):
    """A policy-source release manifest or representation is invalid."""


@dataclass(frozen=True)
class PolicySourceContentIdentity:
    digest: str
    digest_algorithm: str = POLICY_SOURCE_DIGEST_ALGORITHM

    def document(self) -> dict[str, str]:
        return {
            "digest": self.digest,
            "digestAlgorithm": self.digest_algorithm,
        }


@dataclass(frozen=True)
class PolicySourceMetadata:
    git_tag: str | None = None
    git_commit: str | None = None


@dataclass(frozen=True)
class PolicySourceArchiveRepresentation:
    kind: str
    format: str
    content_root: str
    filename: str
    sha256: str

    def document(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "format": self.format,
            "contentRoot": self.content_root,
            "filename": self.filename,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class PolicySourceRelease:
    """Normalized release identity plus noncanonical navigation/acquisition data."""

    manifest_schema: str
    distribution: str
    version: str
    content: PolicySourceContentIdentity
    source_metadata: PolicySourceMetadata | None = None
    representations: tuple[PolicySourceArchiveRepresentation, ...] = ()

    def semantic_document(self) -> dict[str, Any]:
        """Return exact semantic release identity, excluding metadata/representations."""
        return {
            "distribution": self.distribution,
            "version": self.version,
            "content": self.content.document(),
        }

    def release_lock_policy_source(self) -> dict[str, Any]:
        """Project a generic release to release-lock/v1alpha2."""
        if self.content.digest_algorithm != POLICY_SOURCE_DIGEST_ALGORITHM:
            raise PolicySourceReleaseError(
                "policy-source digest algorithm is not valid for active "
                "release-lock/v1alpha2"
            )
        return self.semantic_document()


@dataclass(frozen=True)
class PolicySourceArchiveValidation:
    representation_sha256: str
    content_digest: str
    file_count: int
    materialized_path: Path | None = None


def policy_source_release_schema_path() -> Path:
    """Resolve the generic manifest schema from installed tooling package data."""
    return Path(__file__).resolve().parent / "schemas" / _SCHEMA_FILENAME


def _schema_errors(document: Any) -> list[str]:
    schema_path = policy_source_release_schema_path()
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicySourceReleaseError(
            f"cannot read policy-source release schema {schema_path}: {error}"
        ) from error
    return [
        f"/{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
        for error in sorted(
            Draft202012Validator(schema).iter_errors(document),
            key=lambda item: (
                tuple(str(part) for part in item.absolute_path),
                item.message,
            ),
        )
    ]


def normalize_policy_source_release(document: Any) -> PolicySourceRelease:
    """Validate and normalize a generic policy-source release manifest."""
    if not isinstance(document, dict):
        raise PolicySourceReleaseError("policy-source release manifest must be an object")
    schema_name = document.get("schema")
    if schema_name != POLICY_SOURCE_RELEASE_SCHEMA:
        raise PolicySourceReleaseError(
            f"unsupported policy-source release manifest schema: {schema_name!r}"
        )
    errors = _schema_errors(document)
    if errors:
        raise PolicySourceReleaseError(
            "policy-source release manifest schema validation failed: "
            + "; ".join(errors)
        )

    by_filename: dict[str, dict[str, Any]] = {}
    for representation in document.get("representations", []):
        filename = representation["filename"]
        previous = by_filename.get(filename)
        if previous is not None and previous != representation:
            raise PolicySourceReleaseError(
                "policy-source release manifest has conflicting representations "
                f"for filename {filename!r}"
            )
        by_filename[filename] = representation

    content = document["content"]
    metadata_document = document.get("sourceMetadata")
    metadata = (
        PolicySourceMetadata(
            git_tag=metadata_document.get("gitTag"),
            git_commit=metadata_document.get("gitCommit"),
        )
        if metadata_document is not None
        else None
    )
    representations = tuple(
        PolicySourceArchiveRepresentation(
            kind=item["kind"],
            format=item["format"],
            content_root=item["contentRoot"],
            filename=item["filename"],
            sha256=item["sha256"],
        )
        for item in document.get("representations", [])
    )
    return PolicySourceRelease(
        manifest_schema=schema_name,
        distribution=document["distribution"],
        version=document["version"],
        content=PolicySourceContentIdentity(
            digest=content["digest"],
            digest_algorithm=content["digestAlgorithm"],
        ),
        source_metadata=metadata,
        representations=representations,
    )


def load_policy_source_release(source: Path) -> PolicySourceRelease:
    """Load one JSON manifest without consulting Git, a provider, or the network."""
    source = source.resolve()
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicySourceReleaseError(
            f"cannot read policy-source release manifest {source}: {error}"
        ) from error
    return normalize_policy_source_release(document)


def _file_sha256(source: Path) -> str:
    digest = hashlib.sha256()
    try:
        with source.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise PolicySourceReleaseError(
            f"cannot read policy-source archive {source}: {error}"
        ) from error
    return f"sha256:{digest.hexdigest()}"


def _member_parts(member: tarfile.TarInfo) -> tuple[str, ...]:
    name = member.name
    if member.isdir() and name.endswith("/"):
        name = name[:-1]
    if not name or "\\" in name or _WINDOWS_DRIVE.match(name):
        raise PolicySourceReleaseError(f"unsafe policy-source archive path: {member.name!r}")
    path = PurePosixPath(name)
    parts = tuple(name.split("/"))
    if path.is_absolute() or any(part in {"", ".", ".."} for part in parts):
        raise PolicySourceReleaseError(f"unsafe policy-source archive path: {member.name!r}")
    if parts[0] != "policy":
        raise PolicySourceReleaseError(
            f"policy-source archive entry is outside policy/: {member.name!r}"
        )
    generated = _GENERATED_COMPONENTS.intersection(parts)
    if generated:
        component = sorted(generated)[0]
        raise PolicySourceReleaseError(
            f"policy-source archive contains excluded {component!r} path component: "
            f"{member.name!r}"
        )
    return parts


def _validate_gzip_metadata(archive_path: Path) -> None:
    try:
        with archive_path.open("rb") as stream:
            header = stream.read(_GZIP_HEADER_SIZE)
    except OSError as error:
        raise PolicySourceReleaseError(
            f"cannot read policy-source archive {archive_path}: {error}"
        ) from error
    # XFL records the compression strategy and is intentionally representation-specific.
    if (
        len(header) != _GZIP_HEADER_SIZE
        or header[:2] != b"\x1f\x8b"
        or header[2] != _GZIP_DEFLATE_METHOD
        or header[3] != _GZIP_NORMALIZED_FLAGS
        or header[4:8] != b"\0\0\0\0"
        or header[9] != _GZIP_NORMALIZED_OS
    ):
        raise PolicySourceReleaseError(
            "policy-source archive gzip metadata is not normalized"
        )


def _validate_member_metadata(member: tarfile.TarInfo) -> None:
    expected_mode = (
        _ARCHIVE_DIRECTORY_MODE if member.isdir() else _ARCHIVE_FILE_MODE
    )
    # PAX path extension data is necessary for long names; all other PAX metadata
    # would make identical source entries encode differently.
    allowed_pax_headers = (
        {"path": member.name} if member.pax_headers.get("path") == member.name else {}
    )
    if (
        member.mtime != 0
        or member.uid != 0
        or member.gid != 0
        or member.uname != ""
        or member.gname != ""
        or member.mode != expected_mode
        or member.linkname != ""
        or member.devmajor != 0
        or member.devminor != 0
        or member.pax_headers != allowed_pax_headers
        or bool(member.sparse)
        or (member.isdir() and member.size != 0)
    ):
        raise PolicySourceReleaseError(
            "policy-source archive tar metadata is not normalized for entry "
            f"{member.name!r}"
        )


def _validated_members(
    archive: tarfile.TarFile,
) -> tuple[list[tuple[tarfile.TarInfo, tuple[str, ...]]], int]:
    validated: list[tuple[tarfile.TarInfo, tuple[str, ...]]] = []
    paths: set[tuple[str, ...]] = set()
    file_paths: set[tuple[str, ...]] = set()
    file_count = 0
    for member in archive.getmembers():
        parts = _member_parts(member)
        if parts in paths:
            raise PolicySourceReleaseError(
                f"policy-source archive contains duplicate path: {member.name!r}"
            )
        paths.add(parts)
        if member.isdir():
            pass
        elif member.isfile():
            if parts == ("policy",):
                raise PolicySourceReleaseError("policy-source archive root policy/ is not a directory")
            file_paths.add(parts)
            file_count += 1
        else:
            raise PolicySourceReleaseError(
                "policy-source archive contains unsupported filesystem entry "
                f"{member.name!r}"
            )
        _validate_member_metadata(member)
        validated.append((member, parts))
    if not validated or validated[0][1] != ("policy",) or not validated[0][0].isdir():
        raise PolicySourceReleaseError("policy-source archive lacks policy/ content root")
    actual_order = [parts for _, parts in validated]
    expected_order = [
        ("policy",),
        *sorted(actual_order[1:], key=lambda parts: "/".join(parts)),
    ]
    if actual_order != expected_order:
        raise PolicySourceReleaseError(
            "policy-source archive entries are not in normalized order"
        )
    for _, parts in validated:
        for end in range(1, len(parts)):
            if parts[:end] in file_paths:
                raise PolicySourceReleaseError(
                    "policy-source archive file is the parent of another entry: "
                    f"{'/'.join(parts[:end])!r}"
                )
    return validated, file_count


def validate_policy_source_archive(
    release: PolicySourceRelease,
    representation: PolicySourceArchiveRepresentation,
    archive_path: Path,
    *,
    materialize_to: Path | None = None,
) -> PolicySourceArchiveValidation:
    """Validate exact generic archive bytes and optionally materialize policy content."""
    if representation not in release.representations:
        raise PolicySourceReleaseError("archive representation is not declared by the release")
    archive_path = archive_path.resolve()
    actual_representation_digest = _file_sha256(archive_path)
    if actual_representation_digest != representation.sha256:
        raise PolicySourceReleaseError(
            "policy-source archive representation digest mismatch: "
            f"expected {representation.sha256}, got {actual_representation_digest}"
        )
    if representation.kind != "archive" or representation.format != POLICY_SOURCE_ARCHIVE_FORMAT:
        raise PolicySourceReleaseError(
            f"unsupported policy-source archive representation: {representation.format!r}"
        )
    if representation.content_root != "policy":
        raise PolicySourceReleaseError(
            f"unsupported policy-source archive content root: {representation.content_root!r}"
        )
    _validate_gzip_metadata(archive_path)

    with tempfile.TemporaryDirectory(prefix="compliance-policy-source-") as temporary:
        extraction_root = Path(temporary)
        try:
            with tarfile.open(archive_path, mode="r:gz") as archive:
                members, file_count = _validated_members(archive)
                for member, parts in sorted(
                    members,
                    key=lambda item: (not item[0].isdir(), len(item[1]), item[1]),
                ):
                    destination = extraction_root.joinpath(*parts)
                    if member.isdir():
                        destination.mkdir(parents=True, exist_ok=True)
                        continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise PolicySourceReleaseError(
                            f"cannot read policy-source archive file: {member.name!r}"
                        )
                    with stream, destination.open("xb") as output:
                        shutil.copyfileobj(stream, output)
        except (OSError, tarfile.TarError) as error:
            raise PolicySourceReleaseError(
                f"cannot inspect policy-source archive {archive_path}: {error}"
            ) from error

        policy_root = extraction_root / "policy"
        if not policy_root.is_dir():
            raise PolicySourceReleaseError("policy-source archive lacks policy/ content root")
        actual_content_digest = source_tree_digest(policy_root)
        if actual_content_digest != release.content.digest:
            raise PolicySourceReleaseError(
                "policy-source archive content digest mismatch: "
                f"expected {release.content.digest}, got {actual_content_digest}"
            )

        materialized_path: Path | None = None
        if materialize_to is not None:
            materialized_path = materialize_to.resolve()
            try:
                shutil.copytree(policy_root, materialized_path)
            except OSError as error:
                raise PolicySourceReleaseError(
                    f"cannot materialize policy-source archive at {materialized_path}: {error}"
                ) from error

    return PolicySourceArchiveValidation(
        representation_sha256=actual_representation_digest,
        content_digest=actual_content_digest,
        file_count=file_count,
        materialized_path=materialized_path,
    )
