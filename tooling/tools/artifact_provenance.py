"""Generator and release-composition provenance for locked generated artifacts."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from typing import Any

from .project_config import ProjectConfig, ProjectConfigError, release_validation
from .release import ToolingReleaseIdentity, tooling_release_identity
from .release_lock import RELEASE_LOCK_SCHEMA
from .tooling_source import TOOLING_SOURCE_DIGEST_ALGORITHM


DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class ArtifactProvenanceError(ValueError):
    """Locked artifact provenance is missing, malformed, or inconsistent."""


@dataclass(frozen=True)
class ContentArtifactProvenance:
    """Content-addressed generator identity used by locked v3 artifacts."""

    distribution: str
    version: str
    source_digest: str
    source_digest_algorithm: str
    artifact_sha256: str
    release_lock_digest: str

    @property
    def artifact_version(self) -> int:
        return 3

    def fields(self) -> dict[str, Any]:
        return {
            "generator": {
                "distribution": self.distribution,
                "version": self.version,
                "source_digest": self.source_digest,
                "source_digest_algorithm": self.source_digest_algorithm,
                "artifact_sha256": self.artifact_sha256,
            },
            "release_lock_digest": self.release_lock_digest,
        }


def locked_artifact_provenance(
    config: ProjectConfig,
    *,
    installed_identity: ToolingReleaseIdentity | None = None,
) -> ContentArtifactProvenance:
    """Derive provenance only from a validated locked project and installed release."""
    if not config.is_locked or config.release_lock is None:
        raise ArtifactProvenanceError(
            "locked artifact provenance requires project-config/v1alpha2"
        )
    identity = installed_identity or tooling_release_identity()
    try:
        report = release_validation(config, installed_identity=identity)
    except ProjectConfigError as error:
        raise ArtifactProvenanceError(str(error)) from error
    if not report["valid"]:
        raise ArtifactProvenanceError(
            "locked artifact provenance requires a valid release composition: "
            + "; ".join(json.dumps(error, sort_keys=True) for error in report["errors"])
        )
    digest = config.release_lock.digest()
    if not DIGEST_RE.fullmatch(digest):
        raise ArtifactProvenanceError(f"invalid release lock digest: {digest!r}")

    if config.release_lock.schema != RELEASE_LOCK_SCHEMA:
        raise ArtifactProvenanceError(
            f"unsupported locked provenance schema: {config.release_lock.schema!r}"
        )
    if identity.source_digest is None or not DIGEST_RE.fullmatch(identity.source_digest):
        raise ArtifactProvenanceError(
            "v1alpha2 lock requires installed tooling with canonical source digest"
        )
    if identity.source_digest_algorithm != TOOLING_SOURCE_DIGEST_ALGORITHM:
        raise ArtifactProvenanceError(
            "installed tooling source digest algorithm does not match the current contract"
        )
    artifact_sha256 = config.release_lock.tooling.artifact_sha256
    if not DIGEST_RE.fullmatch(artifact_sha256):
        raise ArtifactProvenanceError(
            f"invalid locked tooling wheel digest: {artifact_sha256!r}"
        )
    return ContentArtifactProvenance(
        distribution=identity.distribution,
        version=identity.version,
        source_digest=identity.source_digest,
        source_digest_algorithm=identity.source_digest_algorithm,
        artifact_sha256=artifact_sha256,
        release_lock_digest=digest,
    )


def optional_artifact_provenance(config: ProjectConfig) -> ContentArtifactProvenance | None:
    """Return locked provenance for v1alpha2, otherwise preserve v1 development behavior."""
    return locked_artifact_provenance(config) if config.is_locked else None


def stored_artifact_provenance(document: dict[str, Any]) -> ContentArtifactProvenance | None:
    """Read compact provenance fields from one generated artifact."""
    generator = document.get("generator")
    lock_digest = document.get("release_lock_digest")
    if generator is None and lock_digest is None:
        return None
    if not isinstance(generator, dict) or not isinstance(lock_digest, str):
        raise ArtifactProvenanceError(
            "artifact provenance requires generator and release_lock_digest together"
        )
    distribution = generator.get("distribution")
    version = generator.get("version")
    if not isinstance(distribution, str) or not distribution:
        raise ArtifactProvenanceError("artifact generator distribution is invalid")
    if not isinstance(version, str) or not version:
        raise ArtifactProvenanceError("artifact generator version is invalid")
    if not DIGEST_RE.fullmatch(lock_digest):
        raise ArtifactProvenanceError("artifact release_lock_digest is invalid")

    expected_fields = {
        "distribution",
        "version",
        "source_digest",
        "source_digest_algorithm",
        "artifact_sha256",
    }
    if set(generator) != expected_fields:
        raise ArtifactProvenanceError("artifact v3 generator fields are invalid")
    source_digest = generator.get("source_digest")
    artifact_sha256 = generator.get("artifact_sha256")
    source_algorithm = generator.get("source_digest_algorithm")
    if not isinstance(source_digest, str) or not DIGEST_RE.fullmatch(source_digest):
        raise ArtifactProvenanceError("artifact generator source_digest is invalid")
    if source_algorithm != TOOLING_SOURCE_DIGEST_ALGORITHM:
        raise ArtifactProvenanceError("artifact generator source_digest_algorithm is invalid")
    if not isinstance(artifact_sha256, str) or not DIGEST_RE.fullmatch(artifact_sha256):
        raise ArtifactProvenanceError("artifact generator artifact_sha256 is invalid")
    return ContentArtifactProvenance(
        distribution=distribution,
        version=version,
        source_digest=source_digest,
        source_digest_algorithm=source_algorithm,
        artifact_sha256=artifact_sha256,
        release_lock_digest=lock_digest,
    )


def require_artifact_provenance(
    document: dict[str, Any],
    expected: ContentArtifactProvenance | None,
    *,
    label: str,
) -> ContentArtifactProvenance:
    """Require stored locked provenance and, when supplied, exact current-lock equality."""
    stored = stored_artifact_provenance(document)
    if stored is None:
        raise ArtifactProvenanceError(f"{label} lacks locked artifact provenance")
    if expected is not None and stored != expected:
        raise ArtifactProvenanceError(
            f"{label} release composition does not match the current validated lock: "
            f"stored={json.dumps(stored.fields(), sort_keys=True)}, "
            f"current={json.dumps(expected.fields(), sort_keys=True)}"
        )
    return stored


def copy_artifact_provenance(document: dict[str, Any]) -> dict[str, Any]:
    """Copy validated stored provenance for a downstream generated artifact."""
    return copy.deepcopy(require_artifact_provenance(document, None, label="source artifact").fields())
