"""Installed tooling release identity and compatibility metadata."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import metadata, resources
from typing import Any

from .tooling_source import TOOLING_SOURCE_DIGEST_ALGORITHM


DISTRIBUTION_NAME = "compliance-tooling"
CLI_NAME = "compliance"
RELEASE_METADATA_SCHEMA = "compliance.example/tooling-release-metadata/v2"
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class ToolingReleaseIdentity:
    """Identity of the installed tooling package without transport assumptions."""

    schema: str
    distribution: str
    cli: str
    version: str
    tested_opa_version: str
    source_digest: str | None = None
    source_digest_algorithm: str | None = None

    @property
    def build_kind(self) -> str:
        return "release" if self.source_digest else "development"

    def document(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "distribution": self.distribution,
            "cli": self.cli,
            "version": self.version,
            "source_digest": self.source_digest,
            "source_digest_algorithm": self.source_digest_algorithm,
            "tested_opa_version": self.tested_opa_version,
            "build_kind": self.build_kind,
        }


def _release_metadata() -> dict[str, Any]:
    resource = resources.files("tools").joinpath("release-metadata.json")
    document = json.loads(resource.read_text(encoding="utf-8"))
    schema = document.get("schema")
    if schema != RELEASE_METADATA_SCHEMA:
        raise RuntimeError(f"unsupported tooling release metadata schema: {schema!r}")

    source_digest = document.get("source_digest")
    if source_digest is not None and not _DIGEST.fullmatch(source_digest):
        raise RuntimeError(
            "invalid tooling source digest in installed release metadata: "
            f"{source_digest!r}"
        )
    if document.get("source_digest_algorithm") != TOOLING_SOURCE_DIGEST_ALGORITHM:
        raise RuntimeError(
            "unsupported tooling source digest algorithm in installed release metadata: "
            f"{document.get('source_digest_algorithm')!r}"
        )

    tested_opa_version = document.get("tested_opa_version")
    if not isinstance(tested_opa_version, str) or not tested_opa_version:
        raise RuntimeError("installed tooling release metadata lacks tested OPA version")
    return document


def tooling_release_identity() -> ToolingReleaseIdentity:
    """Return installed package identity plus embedded canonical source metadata."""
    try:
        version = metadata.version(DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError:
        version = "uninstalled"
    release = _release_metadata()
    schema = release["schema"]
    return ToolingReleaseIdentity(
        schema=schema,
        distribution=DISTRIBUTION_NAME,
        cli=CLI_NAME,
        version=version,
        tested_opa_version=release["tested_opa_version"],
        source_digest=release.get("source_digest"),
        source_digest_algorithm=release.get("source_digest_algorithm"),
    )


def format_release_identity(identity: ToolingReleaseIdentity | None = None) -> str:
    """Format a compact human-facing installed tooling identity."""
    resolved = identity or tooling_release_identity()
    if resolved.source_digest:
        source = resolved.source_digest
    else:
        source = "development/unrecorded"
    return (
        f"{resolved.cli} {resolved.version} "
        f"({resolved.distribution}; source {source}; OPA tested {resolved.tested_opa_version})"
    )
