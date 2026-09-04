"""Release lock loading, canonical identity, and materialized-source validation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from ._canonical_json import canonical_json_bytes
from .policy_sources import PolicySource, source_tree_digest
from .release import ToolingReleaseIdentity, tooling_release_identity
from .tooling_source import TOOLING_SOURCE_DIGEST_ALGORITHM


RELEASE_LOCK_FILENAME = "compliance.lock.yaml"
RELEASE_LOCK_SCHEMA = "compliance.example/release-lock/v1alpha2"
RELEASE_LOCK_DIGEST_ALGORITHM = "compliance.example/release-lock-digest/v1alpha1"
POLICY_SOURCE_DIGEST_ALGORITHM = (
    "compliance.example/policy-source-tree-digest/v1alpha1"
)
RELEASE_VALIDATION_SCHEMA = "compliance.example/release-validation/v1alpha2"


class ReleaseLockError(ValueError):
    """A release lock could not be loaded or validated safely."""


@dataclass(frozen=True)
class LockedTooling:
    distribution: str
    version: str
    artifact_sha256: str
    source_digest: str
    source_digest_algorithm: str
    artifact_kind: str

    def document(self) -> dict[str, Any]:
        return {
            "distribution": self.distribution,
            "version": self.version,
            "source": {
                "digest": self.source_digest,
                "digestAlgorithm": self.source_digest_algorithm,
            },
            "artifact": {
                "kind": self.artifact_kind,
                "sha256": self.artifact_sha256,
            },
        }


@dataclass(frozen=True)
class LockedPolicySource:
    name: str
    distribution: str
    version: str
    source_digest: str
    source_digest_algorithm: str = POLICY_SOURCE_DIGEST_ALGORITHM

    def document(self) -> dict[str, Any]:
        return {
            "distribution": self.distribution,
            "version": self.version,
            "content": {
                "digest": self.source_digest,
                "digestAlgorithm": self.source_digest_algorithm,
            },
        }


@dataclass(frozen=True)
class ReleaseLock:
    source: Path
    schema: str
    tooling: LockedTooling
    policy_sources: tuple[LockedPolicySource, ...]

    def semantic_document(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "tooling": self.tooling.document(),
            "policySources": {
                source.name: source.document()
                for source in sorted(self.policy_sources, key=lambda item: item.name)
            },
        }

    def digest(self) -> str:
        return release_lock_digest(self)


def release_lock_schema_path(schema: str = RELEASE_LOCK_SCHEMA) -> Path:
    if schema != RELEASE_LOCK_SCHEMA:
        raise ReleaseLockError(f"unsupported release lock schema: {schema!r}")
    return Path(__file__).resolve().parent / "schemas/release-lock-v1alpha2.schema.json"


def _load_yaml_document(source: Path) -> Any:
    try:
        with source.open(encoding="utf-8") as stream:
            documents = list(yaml.safe_load_all(stream))
    except (OSError, yaml.YAMLError) as error:
        raise ReleaseLockError(f"cannot read release lock {source}: {error}") from error
    if len(documents) != 1:
        raise ReleaseLockError(
            f"release lock must contain exactly one YAML document: {source}"
        )
    return documents[0]


def _schema_errors(document: Any, schema_name: str) -> list[str]:
    schema_path = release_lock_schema_path(schema_name)
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseLockError(f"cannot read release lock schema {schema_path}: {error}") from error
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


def load_release_lock(source: Path) -> ReleaseLock:
    """Load one validated lock without resolving transport or Git state."""
    source = source.resolve()
    if not source.is_file():
        raise ReleaseLockError(f"release lock does not exist: {source}")
    document = _load_yaml_document(source)
    if not isinstance(document, dict):
        raise ReleaseLockError(f"release lock must be an object: {source}")
    schema_name = document.get("schema")
    if schema_name != RELEASE_LOCK_SCHEMA:
        raise ReleaseLockError(f"unsupported release lock schema: {schema_name!r}")
    errors = _schema_errors(document, schema_name)
    if errors:
        raise ReleaseLockError(
            f"release lock schema validation failed for {source}: " + "; ".join(errors)
        )

    tooling = document["tooling"]
    locked_tooling = LockedTooling(
        distribution=tooling["distribution"],
        version=tooling["version"],
        source_digest=tooling["source"]["digest"],
        source_digest_algorithm=tooling["source"]["digestAlgorithm"],
        artifact_kind=tooling["artifact"]["kind"],
        artifact_sha256=tooling["artifact"]["sha256"],
    )
    policy_sources = tuple(
        LockedPolicySource(
            name=name,
            distribution=definition["distribution"],
            version=definition["version"],
            source_digest=definition["content"]["digest"],
            source_digest_algorithm=definition["content"]["digestAlgorithm"],
        )
        for name, definition in sorted(document["policySources"].items())
    )
    return ReleaseLock(
        source=source,
        schema=schema_name,
        tooling=locked_tooling,
        policy_sources=policy_sources,
    )


def release_lock_digest(lock: ReleaseLock) -> str:
    """Hash canonical semantic lock content, independent of YAML/layout/paths."""
    encoded = canonical_json_bytes(lock.semantic_document())
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def validate_release_composition(
    lock: ReleaseLock,
    configured_sources: tuple[PolicySource, ...],
    *,
    installed_identity: ToolingReleaseIdentity | None = None,
) -> dict[str, Any]:
    """Validate installed tooling and local materialized sources against a lock."""
    installed = installed_identity or tooling_release_identity()
    errors: list[dict[str, Any]] = []
    expected_tooling = lock.tooling

    if installed.source_digest is None:
        errors.append({
            "type": "tooling-release-unrecorded",
            "message": "v1alpha2 locks require tooling with an embedded canonical source digest",
        })
    if installed.source_digest_algorithm != TOOLING_SOURCE_DIGEST_ALGORITHM:
        errors.append({
            "type": "tooling-source-digest-algorithm-mismatch",
            "expected": TOOLING_SOURCE_DIGEST_ALGORITHM,
            "actual": installed.source_digest_algorithm,
        })
    comparisons = (
        ("distribution", expected_tooling.distribution, installed.distribution),
        ("version", expected_tooling.version, installed.version),
        ("source.digest", expected_tooling.source_digest, installed.source_digest),
    )
    for field, expected, actual in comparisons:
        if actual != expected:
            errors.append({
                "type": "tooling-release-mismatch",
                "field": field,
                "expected": expected,
                "actual": actual,
            })

    locked_by_name = {source.name: source for source in lock.policy_sources}
    configured_by_name = {source.name: source for source in configured_sources}
    for name in sorted(set(locked_by_name) - set(configured_by_name)):
        errors.append({"type": "locked-policy-source-missing", "policy_source": name})
    for name in sorted(set(configured_by_name) - set(locked_by_name)):
        errors.append({"type": "unlocked-policy-source", "policy_source": name})

    source_reports: list[dict[str, Any]] = []
    for name in sorted(set(locked_by_name) | set(configured_by_name)):
        locked = locked_by_name.get(name)
        configured = configured_by_name.get(name)
        actual_digest: str | None = None
        source_errors: list[dict[str, Any]] = []
        if locked is not None and configured is not None:
            if configured.expected_digest != locked.source_digest:
                source_errors.append({
                    "type": "configured-policy-digest-mismatch",
                    "policy_source": name,
                    "locked": locked.source_digest,
                    "configured": configured.expected_digest,
                })
            try:
                actual_digest = source_tree_digest(configured.path)
            except (OSError, ValueError) as error:
                source_errors.append({
                    "type": "materialized-policy-source-unavailable",
                    "policy_source": name,
                    "message": str(error),
                })
            else:
                if actual_digest != locked.source_digest:
                    source_errors.append({
                        "type": "materialized-policy-digest-mismatch",
                        "policy_source": name,
                        "expected": locked.source_digest,
                        "actual": actual_digest,
                    })
        errors.extend(source_errors)
        source_reports.append({
            "name": name,
            "locked": locked.document() if locked is not None else None,
            "materialized_path": str(configured.path) if configured is not None else None,
            "configured_digest": configured.expected_digest if configured is not None else None,
            "actual_digest": actual_digest,
            "valid": not source_errors and locked is not None and configured is not None,
        })

    return {
        "schema": RELEASE_VALIDATION_SCHEMA,
        "lock_schema": lock.schema,
        "release_lock_digest_algorithm": RELEASE_LOCK_DIGEST_ALGORITHM,
        "release_lock_digest": release_lock_digest(lock),
        "lock_source": str(lock.source),
        "locked_tooling": expected_tooling.document(),
        "installed_tooling": installed.document(),
        "policy_sources": source_reports,
        "valid": not errors,
        "errors": errors,
    }


def format_release_validation(report: dict[str, Any]) -> str:
    """Render a compact human-readable release composition report."""
    locked = report["locked_tooling"]
    installed = report["installed_tooling"]
    locked_source = locked["source"]["digest"]
    installed_source = installed.get("source_digest") or "unrecorded"
    lines = [
        f"Release lock: {report['lock_source']}",
        f"Lock digest:  {report['release_lock_digest']}",
        f"Status:       {'valid' if report['valid'] else 'invalid'}",
        "Tooling:",
        f"  locked:    {locked['distribution']} {locked['version']} {locked_source}",
        f"  installed: {installed['distribution']} {installed['version']} {installed_source}",
        "Policy sources:",
    ]
    for source in report["policy_sources"]:
        locked_source_document = source["locked"] or {}
        expected = locked_source_document.get("content", {}).get("digest", "unlocked")
        lines.append(
            f"  {source['name']}: {'valid' if source['valid'] else 'invalid'} "
            f"expected={expected} actual={source['actual_digest'] or 'unavailable'} "
            f"path={source['materialized_path'] or 'unconfigured'}"
        )
    if report["errors"]:
        lines.append("Errors:")
        lines.extend("  " + json.dumps(error, sort_keys=True) for error in report["errors"])
    return "\n".join(lines)
