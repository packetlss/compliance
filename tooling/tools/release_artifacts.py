"""Provider-neutral preparation and verification for tooling release payloads."""

from __future__ import annotations

import configparser
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from email.parser import Parser
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from tools.release import (
    CLI_NAME,
    DISTRIBUTION_NAME,
    RELEASE_METADATA_SCHEMA,
)
from tools.tooling_source import TOOLING_SOURCE_DIGEST_ALGORITHM, tooling_source_digest


RELEASE_MANIFEST_SCHEMA = "compliance.example/tooling-release-manifest/v2"
MANIFEST_FILENAME = "tooling-release-manifest.json"
CHECKSUMS_FILENAME = "SHA256SUMS"

_SEMVER_TEXT = (
    r"(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)
_SEMVER = re.compile(rf"^{_SEMVER_TEXT}$")
_TAG = re.compile(rf"^v(?P<version>{_SEMVER_TEXT})$")
_SOURCE_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_CHECKSUM_LINE = re.compile(
    r"^(?P<digest>[0-9a-f]{64})  (?P<filename>[A-Za-z0-9._+-]+)$"
)


class ToolingReleaseError(ValueError):
    """Raised when a tooling release payload violates its release contract."""


def release_tag_version(tag: str) -> str:
    """Return the semantic version named by a strict `v<SemVer>` release tag."""
    match = _TAG.fullmatch(tag)
    if match is None:
        raise ToolingReleaseError(f"release tag must be v<SemVer>: {tag!r}")
    return match.group("version")


def _validate_semver(version: str, *, field: str) -> None:
    if _SEMVER.fullmatch(version) is None:
        raise ToolingReleaseError(f"{field} must be strict SemVer: {version!r}")


def _validate_source_sha(git_commit: str) -> None:
    if _SOURCE_SHA.fullmatch(git_commit) is None:
        raise ToolingReleaseError(
            "source Git SHA must be exactly 40 lower-case hexadecimal characters"
        )


def _validate_digest(value: str, *, field: str) -> None:
    if _DIGEST.fullmatch(value) is None:
        raise ToolingReleaseError(f"{field} must be sha256:<64 lower-case hex>")


def _project_identity(root: Path) -> tuple[str, str, str]:
    document = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = document.get("project")
    if not isinstance(project, dict):
        raise ToolingReleaseError("pyproject.toml lacks [project] metadata")
    distribution = project.get("name")
    version = project.get("version")
    scripts = project.get("scripts")
    if distribution != DISTRIBUTION_NAME:
        raise ToolingReleaseError(
            f"project distribution must be {DISTRIBUTION_NAME!r}, found {distribution!r}"
        )
    if not isinstance(version, str):
        raise ToolingReleaseError("project version must be a string")
    _validate_semver(version, field="project version")
    if not isinstance(scripts, dict) or scripts.get(CLI_NAME) != "tools.cli:main":
        raise ToolingReleaseError(
            f"project must expose {CLI_NAME!r} as tools.cli:main"
        )
    return distribution, CLI_NAME, version


def _manifest_validator() -> Draft202012Validator:
    schema_path = resources.files("tools").joinpath(
        "schemas/tooling-release-manifest-v2.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def validate_release_manifest(document: dict[str, Any]) -> None:
    """Validate one provider-neutral release manifest document."""
    schema_name = document.get("schema")
    if schema_name != RELEASE_MANIFEST_SCHEMA:
        raise ToolingReleaseError(
            f"unsupported tooling release manifest schema: {schema_name!r}"
        )
    errors = sorted(
        _manifest_validator().iter_errors(document),
        key=lambda error: list(error.path),
    )
    if errors:
        rendered = "; ".join(
            f"{'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ToolingReleaseError(f"release manifest schema validation failed: {rendered}")

    version = document["version"]
    source = document["source"]
    if source["digestAlgorithm"] != TOOLING_SOURCE_DIGEST_ALGORITHM:
        raise ToolingReleaseError("unsupported canonical tooling source digest algorithm")
    _validate_digest(source["digest"], field="source.digest")
    metadata = document.get("sourceMetadata")
    if metadata is not None:
        tag_version = release_tag_version(metadata["gitTag"])
        if tag_version != version:
            raise ToolingReleaseError(
                f"Git tag version {tag_version!r} does not match manifest version {version!r}"
            )
        _validate_source_sha(metadata["gitCommit"])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _wheel_identity(wheel: Path) -> dict[str, Any]:
    try:
        archive = zipfile.ZipFile(wheel)
    except (OSError, zipfile.BadZipFile) as error:
        raise ToolingReleaseError(f"invalid wheel archive {wheel}: {error}") from error

    with archive:
        names = archive.namelist()
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ToolingReleaseError(
                f"wheel must contain exactly one dist-info METADATA file: {wheel.name}"
            )
        metadata_name = metadata_names[0]
        dist_info = metadata_name.rsplit("/", 1)[0]
        metadata = Parser().parsestr(archive.read(metadata_name).decode("utf-8"))
        distribution = metadata.get("Name")
        version = metadata.get("Version")

        entry_points_name = f"{dist_info}/entry_points.txt"
        if entry_points_name not in names:
            raise ToolingReleaseError("wheel lacks console entry-point metadata")
        entry_points = configparser.ConfigParser(interpolation=None)
        entry_points.read_string(archive.read(entry_points_name).decode("utf-8"))
        try:
            cli_target = entry_points["console_scripts"][CLI_NAME].strip()
        except KeyError as error:
            raise ToolingReleaseError(
                f"wheel lacks {CLI_NAME!r} console entry point"
            ) from error

        release_metadata_name = "tools/release-metadata.json"
        if release_metadata_name not in names:
            raise ToolingReleaseError("wheel lacks tools/release-metadata.json")
        release_metadata = json.loads(archive.read(release_metadata_name).decode("utf-8"))

    if distribution != DISTRIBUTION_NAME:
        raise ToolingReleaseError(
            f"wheel distribution mismatch: expected {DISTRIBUTION_NAME!r}, found {distribution!r}"
        )
    if not isinstance(version, str):
        raise ToolingReleaseError("wheel version metadata is missing")
    _validate_semver(version, field="wheel version")
    if cli_target != "tools.cli:main":
        raise ToolingReleaseError(
            f"wheel console entry point mismatch: expected 'tools.cli:main', found {cli_target!r}"
        )

    release_schema = release_metadata.get("schema")
    tested_opa_version = release_metadata.get("tested_opa_version")
    if not isinstance(tested_opa_version, str):
        raise ToolingReleaseError("wheel release metadata lacks tested OPA version")
    _validate_semver(tested_opa_version, field="tested OPA version")

    identity: dict[str, Any] = {
        "distribution": distribution,
        "cli": CLI_NAME,
        "version": version,
        "release_metadata_schema": release_schema,
        "tested_opa_version": tested_opa_version,
    }
    if release_schema != RELEASE_METADATA_SCHEMA:
        raise ToolingReleaseError("wheel release metadata schema mismatch")
    source_digest = release_metadata.get("source_digest")
    if not isinstance(source_digest, str):
        raise ToolingReleaseError("v2 release wheel must embed a canonical source digest")
    _validate_digest(source_digest, field="wheel source digest")
    if release_metadata.get("source_digest_algorithm") != TOOLING_SOURCE_DIGEST_ALGORITHM:
        raise ToolingReleaseError("wheel source digest algorithm mismatch")
    identity["source_digest"] = source_digest
    identity["source_digest_algorithm"] = TOOLING_SOURCE_DIGEST_ALGORITHM
    return identity


def _checksum_entries(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ToolingReleaseError(f"cannot read checksum file {path}: {error}") from error
    for line in lines:
        match = _CHECKSUM_LINE.fullmatch(line)
        if match is None:
            raise ToolingReleaseError(f"invalid SHA256SUMS line: {line!r}")
        filename = match.group("filename")
        if filename in entries:
            raise ToolingReleaseError(f"duplicate SHA256SUMS entry: {filename}")
        entries[filename] = match.group("digest")
    return entries


def verify_release_payload(release_dir: Path) -> dict[str, Any]:
    """Verify a complete provider-neutral release payload directory."""
    release_dir = release_dir.resolve()
    manifest_path = release_dir / MANIFEST_FILENAME
    checksums_path = release_dir / CHECKSUMS_FILENAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ToolingReleaseError(f"cannot read release manifest: {error}") from error
    if not isinstance(manifest, dict):
        raise ToolingReleaseError("release manifest must be a JSON object")
    validate_release_manifest(manifest)

    artifact = manifest["artifact"]
    wheel_filename = artifact["filename"]
    wheel_path = release_dir / wheel_filename
    expected_files = {wheel_filename, MANIFEST_FILENAME, CHECKSUMS_FILENAME}
    try:
        actual_files = {path.name for path in release_dir.iterdir() if path.is_file()}
    except OSError as error:
        raise ToolingReleaseError(f"cannot inspect release directory: {error}") from error
    if actual_files != expected_files:
        raise ToolingReleaseError(
            "release payload must contain exactly wheel, manifest, and SHA256SUMS; "
            f"expected {sorted(expected_files)}, found {sorted(actual_files)}"
        )

    version = manifest["version"]
    expected_wheel = f"compliance_tooling-{version}-py3-none-any.whl"
    if wheel_filename != expected_wheel:
        raise ToolingReleaseError(
            f"unexpected wheel filename: expected {expected_wheel!r}, found {wheel_filename!r}"
        )

    wheel_identity = _wheel_identity(wheel_path)
    for field, expected, actual in (
        ("distribution", manifest["distribution"], wheel_identity["distribution"]),
        ("cli", manifest["cli"], wheel_identity["cli"]),
        ("version", manifest["version"], wheel_identity["version"]),
        (
            "testedOpaVersion",
            manifest["testedOpaVersion"],
            wheel_identity["tested_opa_version"],
        ),
    ):
        if actual != expected:
            raise ToolingReleaseError(
                f"wheel identity mismatch for {field}: expected {expected!r}, found {actual!r}"
            )

    source = manifest["source"]
    if wheel_identity.get("source_digest") != source["digest"]:
        raise ToolingReleaseError("wheel canonical source digest does not match manifest")
    if wheel_identity.get("source_digest_algorithm") != source["digestAlgorithm"]:
        raise ToolingReleaseError("wheel source digest algorithm does not match manifest")
    if artifact.get("kind") != "python-wheel":
        raise ToolingReleaseError("v2 release artifact kind must be python-wheel")

    actual_wheel_digest = _sha256(wheel_path)
    if artifact["sha256"] != actual_wheel_digest:
        raise ToolingReleaseError(
            f"manifest wheel digest mismatch: expected {artifact['sha256']}, actual {actual_wheel_digest}"
        )

    checksum_entries = _checksum_entries(checksums_path)
    expected_checksum_names = {wheel_filename, MANIFEST_FILENAME}
    if set(checksum_entries) != expected_checksum_names:
        raise ToolingReleaseError(
            "SHA256SUMS must contain exactly wheel and manifest entries; "
            f"expected {sorted(expected_checksum_names)}, found {sorted(checksum_entries)}"
        )
    for filename in sorted(expected_checksum_names):
        actual = _sha256(release_dir / filename).removeprefix("sha256:")
        if checksum_entries[filename] != actual:
            raise ToolingReleaseError(
                f"SHA256SUMS mismatch for {filename}: expected {checksum_entries[filename]}, actual {actual}"
            )
    if checksum_entries[wheel_filename] != artifact["sha256"].removeprefix("sha256:"):
        raise ToolingReleaseError("manifest and SHA256SUMS wheel digests differ")
    return manifest


def prepare_release_payload(
    root: Path,
    *,
    output_dir: Path,
    git_tag: str | None = None,
    git_commit: str | None = None,
) -> dict[str, Any]:
    """Build, describe, and verify one content-addressed tooling release payload."""
    root = root.resolve()
    output_dir = output_dir.resolve()
    distribution, cli, project_version = _project_identity(root)
    if (git_tag is None) != (git_commit is None):
        raise ToolingReleaseError("git_tag and git_commit must be supplied together")
    source_metadata: dict[str, str] | None = None
    if git_tag is not None and git_commit is not None:
        if release_tag_version(git_tag) != project_version:
            raise ToolingReleaseError(
                f"Git tag {git_tag!r} does not match project version {project_version!r}"
            )
        _validate_source_sha(git_commit)
        source_metadata = {"gitTag": git_tag, "gitCommit": git_commit}

    source_digest = tooling_source_digest(root)
    output_dir.mkdir(parents=True, exist_ok=True)
    if list(output_dir.iterdir()):
        raise ToolingReleaseError(f"release output directory must be empty: {output_dir}")

    with tempfile.TemporaryDirectory(prefix="compliance-tooling-release-build-") as temporary:
        build_dir = Path(temporary) / "dist"
        subprocess.run(
            [
                sys.executable,
                str(root / "scripts/build-wheel.py"),
                "--source-digest",
                source_digest,
                "--output-dir",
                str(build_dir),
            ],
            cwd=root,
            check=True,
        )
        built_wheels = sorted(build_dir.glob("*.whl"))
        if len(built_wheels) != 1:
            raise ToolingReleaseError(
                f"release preparation must build exactly one wheel, found {len(built_wheels)}"
            )
        built_wheel = built_wheels[0]
        expected_wheel = f"compliance_tooling-{project_version}-py3-none-any.whl"
        if built_wheel.name != expected_wheel:
            raise ToolingReleaseError(
                f"release wheel filename mismatch: expected {expected_wheel!r}, found {built_wheel.name!r}"
            )
        wheel = output_dir / built_wheel.name
        shutil.copy2(built_wheel, wheel)

    wheel_identity = _wheel_identity(wheel)
    if wheel_identity["version"] != project_version:
        raise ToolingReleaseError("built wheel version does not match project version")
    if wheel_identity.get("source_digest") != source_digest:
        raise ToolingReleaseError("built wheel source digest does not match canonical source")

    manifest: dict[str, Any] = {
        "schema": RELEASE_MANIFEST_SCHEMA,
        "distribution": distribution,
        "cli": cli,
        "version": project_version,
        "source": {
            "digest": source_digest,
            "digestAlgorithm": TOOLING_SOURCE_DIGEST_ALGORITHM,
        },
        "artifact": {
            "kind": "python-wheel",
            "filename": wheel.name,
            "sha256": _sha256(wheel),
        },
        "testedOpaVersion": wheel_identity["tested_opa_version"],
    }
    if source_metadata is not None:
        manifest["sourceMetadata"] = source_metadata
    validate_release_manifest(manifest)

    manifest_path = output_dir / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checksums = {
        wheel.name: _sha256(wheel).removeprefix("sha256:"),
        MANIFEST_FILENAME: _sha256(manifest_path).removeprefix("sha256:"),
    }
    (output_dir / CHECKSUMS_FILENAME).write_text(
        "".join(
            f"{digest}  {filename}\n"
            for filename, digest in sorted(checksums.items())
        ),
        encoding="utf-8",
    )
    return verify_release_payload(output_dir)
