"""Load and validate repository-local configuration for compliance commands."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import yaml
from jsonschema import Draft202012Validator

from .composition import (
    CompositionError, CompositionLock, UniqueKeyLoader, COMPOSITION_LOCK_FILENAME,
    load_composition_lock, require_composition, validate_composition,
)
from .policy_sources import PolicySource, normalize_policy_sources


CONFIG_FILENAME = "compliance.yaml"
CONFIG_SCHEMA = "compliance.example/project-config/v1alpha3"
PROJECT_REGISTRY_SCHEMA = "compliance.example/project-registry/v1alpha1"
_LOCKED_RUNTIME_OVERRIDE_FLAGS = ("--policy-source", "--policies", "--resource-schema")


class ProjectConfigError(ValueError):
    """A project configuration could not be loaded safely."""


def project_config_schema_path(schema: str = CONFIG_SCHEMA) -> Path:
    if schema == CONFIG_SCHEMA:
        filename = "project-config-v1alpha3.schema.json"
    else:
        raise ProjectConfigError(f"unsupported project config schema: {schema!r}")
    return Path(__file__).resolve().parent / "schemas" / filename


def project_registry_schema_path() -> Path:
    return Path(__file__).resolve().parent / "schemas/project-registry.schema.json"


@dataclass(frozen=True)
class ProjectConfig:
    """Validated configuration with paths resolved against its source file."""

    schema: str = CONFIG_SCHEMA
    source: Path | None = None
    paths: dict[str, Path] = field(default_factory=dict)
    policy_sources: tuple[PolicySource, ...] = ()
    composition_lock: CompositionLock | None = None
    expected_content: dict[str, dict] = field(default_factory=dict)
    project_registry_source: Path | None = None
    project_name: str | None = None
    default_project: str | None = None
    available_projects: dict[str, Path] = field(default_factory=dict)

    def path(self, key: str) -> Path | None:
        return self.paths.get(key)


    def resolved_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "schema": self.schema,
            "source": str(self.source) if self.source else None,
            "project_registry": (
                str(self.project_registry_source) if self.project_registry_source else None
            ),
            "project": self.project_name,
            "available_projects": {
                name: str(path) for name, path in sorted(self.available_projects.items())
            },
            "paths": {key: str(value) for key, value in sorted(self.paths.items())},
            "policy_sources": [
                {
                    "name": source.name,
                    "path": str(source.path),
                    **(
                        {"expected_digest": source.expected_digest}
                        if source.expected_digest
                        else {}
                    ),
                }
                for source in self.policy_sources
            ],
        }
        document["expectedContent"] = self.expected_content
        document["expectedComposition"] = (
            {"path": str(self.composition_lock.source), "digest": self.composition_lock.digest()}
            if self.composition_lock else None
        )
        return document


def discover_config(start: Path) -> Path | None:
    """Return the nearest project configuration at or above start."""
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def _validate_document(
    document: Any,
    source: Path,
    *,
    expected_schema: str,
    schema_path: Path,
) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ProjectConfigError(f"project config must be an object: {source}")

    if document.get("schema") != expected_schema:
        raise ProjectConfigError(
            f"unsupported project config schema in {source}: "
            f"{document.get('schema')!r}; expected {expected_schema!r}"
        )

    try:
        with schema_path.open(encoding="utf-8") as stream:
            schema = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise ProjectConfigError(f"cannot read project config schema {schema_path}: {error}") from error

    errors = sorted(
        Draft202012Validator(schema).iter_errors(document),
        key=lambda error: (
            tuple(str(part) for part in error.absolute_path),
            error.message,
        ),
    )
    if errors:
        rendered = []
        for error in errors:
            location = "/" + "/".join(str(part) for part in error.absolute_path)
            rendered.append(f"{location or '/'}: {error.message}")
        raise ProjectConfigError(
            f"project config schema validation failed for {source}: " + "; ".join(rendered)
        )
    return document


def _load_document(source: Path) -> Any:
    try:
        with source.open(encoding="utf-8") as stream:
            text = stream.read()
            documents = list(yaml.safe_load_all(text))
            if (len(documents) == 1 and isinstance(documents[0], dict)
                    and documents[0].get("schema") == CONFIG_SCHEMA):
                documents = list(yaml.load_all(text, Loader=UniqueKeyLoader))
    except (OSError, yaml.YAMLError, CompositionError) as error:
        raise ProjectConfigError(f"cannot read configuration {source}: {error}") from error

    if len(documents) != 1:
        raise ProjectConfigError(
            f"configuration must contain exactly one YAML document: {source}"
        )
    return documents[0]


def _load_project_config(
    source: Path,
    *,
    project_registry_source: Path | None = None,
    project_name: str | None = None,
    default_project: str | None = None,
    available_projects: dict[str, Path] | None = None,
) -> ProjectConfig:
    raw_document = _load_document(source)
    schema = raw_document.get("schema") if isinstance(raw_document, dict) else None
    if schema != CONFIG_SCHEMA:
        raise ProjectConfigError(
            f"unsupported project config schema in {source}: {schema!r}"
        )
    document = _validate_document(
        raw_document,
        source,
        expected_schema=schema,
        schema_path=project_config_schema_path(schema),
    )
    base = source.parent
    paths = {
        key: (base / Path(value)).resolve()
        if not Path(value).is_absolute()
        else Path(value).resolve()
        for key, value in document.get("paths", {}).items()
    }
    framework_declarations = paths.get("frameworkDeclarations")
    if framework_declarations is not None:
        for forbidden in (base / "policy", base / "generated"):
            try:
                framework_declarations.relative_to(forbidden.resolve())
            except ValueError:
                continue
            raise ProjectConfigError(
                "paths.frameworkDeclarations must be project governance outside policy/ and generated/"
            )
    source_definitions = document["policySources"]
    try:
        policy_sources = normalize_policy_sources(
            PolicySource(
                definition["name"],
                (base / definition["path"])
                if not Path(definition["path"]).is_absolute()
                else Path(definition["path"]),
            )
            for definition in source_definitions
        )
    except ValueError as error:
        raise ProjectConfigError(f"invalid policy sources in {source}: {error}") from error
    if framework_declarations is not None:
        for policy_source in policy_sources:
            try:
                framework_declarations.relative_to(policy_source.path)
            except ValueError:
                try:
                    policy_source.path.relative_to(framework_declarations)
                except ValueError:
                    continue
            raise ProjectConfigError(
                "paths.frameworkDeclarations must be project governance outside every policy-source path"
            )

    composition_lock = None
    expected_content = {}
    expected_content = {
        definition["name"]: definition["expectedContent"]
        for definition in source_definitions if "expectedContent" in definition
    }
    if "expectedComposition" in document:
        lock_source = base / COMPOSITION_LOCK_FILENAME
        if lock_source.is_symlink() or lock_source.resolve().parent != base.resolve():
            raise ProjectConfigError("composition lock must be the regular adjacent compliance.lock.yaml")
        try:
            composition_lock = load_composition_lock(lock_source)
        except CompositionError as error:
            raise ProjectConfigError(str(error)) from error

    return ProjectConfig(
        schema=schema,
        composition_lock=composition_lock,
        expected_content=expected_content,
        source=source,
        paths=paths,
        policy_sources=policy_sources,
        project_registry_source=project_registry_source,
        project_name=project_name,
        default_project=default_project,
        available_projects=available_projects or {},
    )


def load_config(path: Path, project: str | None = None) -> ProjectConfig:
    source = path.resolve()
    if not source.is_file():
        raise ProjectConfigError(f"configuration does not exist: {source}")
    document = _load_document(source)
    schema = document.get("schema") if isinstance(document, dict) else None
    if schema == CONFIG_SCHEMA:
        if project is not None:
            raise ProjectConfigError(
                f"--project requires a project registry; {source} is a project config"
            )
        return _load_project_config(source)
    if schema != PROJECT_REGISTRY_SCHEMA:
        raise ProjectConfigError(
            f"unsupported configuration schema in {source}: {schema!r}"
        )

    project_registry = _validate_document(
        document,
        source,
        expected_schema=PROJECT_REGISTRY_SCHEMA,
        schema_path=project_registry_schema_path(),
    )
    default_project = project_registry["defaultProject"]
    projects = {
        name: (source.parent / definition["config"]).resolve()
        for name, definition in project_registry["projects"].items()
    }
    if default_project not in projects:
        raise ProjectConfigError(
            f"project registry defaultProject {default_project!r} is not defined in projects"
        )
    selected_project = project or default_project
    if selected_project not in projects:
        available = ", ".join(sorted(projects))
        raise ProjectConfigError(
            f"unknown project {selected_project!r}; available projects: {available}"
        )
    return _load_project_config(
        projects[selected_project],
        project_registry_source=source,
        project_name=selected_project,
        default_project=default_project,
        available_projects=projects,
    )


def _argument_uses_flag(argument: str, flag: str) -> bool:
    option = argument.split("=", 1)[0]
    return option.startswith("--") and flag.startswith(option)


def _locked_runtime_overrides(argv: Sequence[str]) -> list[str]:
    return [
        flag
        for flag in _LOCKED_RUNTIME_OVERRIDE_FLAGS
        if any(_argument_uses_flag(argument, flag) for argument in argv)
    ]


def select_config(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    validate_runtime: bool = True,
) -> ProjectConfig:
    """Select explicit, disabled, or automatically discovered configuration."""
    selector = argparse.ArgumentParser(add_help=False)
    group = selector.add_mutually_exclusive_group()
    group.add_argument("--config", type=Path)
    group.add_argument("--no-config", action="store_true")
    selector.add_argument("--project")
    selected, _ = selector.parse_known_args(argv)

    if selected.no_config and selected.project:
        raise ProjectConfigError("--project cannot be used with --no-config")
    if selected.no_config:
        return ProjectConfig()
    working_directory = (cwd or Path.cwd()).resolve()
    source = (
        (working_directory / selected.config).resolve()
        if selected.config and not selected.config.is_absolute()
        else selected.config.resolve()
        if selected.config
        else discover_config(working_directory)
    )
    config = load_config(source, selected.project) if source else ProjectConfig()
    if config.source is not None:
        rejected = _locked_runtime_overrides(argv)
        if rejected:
            raise ProjectConfigError(
                "selected project configuration does not permit runtime contract "
                "overrides: " + ", ".join(rejected)
            )
    if validate_runtime and config.source is not None:
        composition_validation(config, require=True)
    return config


def format_config(config: ProjectConfig, output_format: str) -> str:
    document = config.resolved_document()
    if output_format == "json":
        return json.dumps(document, indent=2, sort_keys=True)
    lines = [f"Config: {config.source or 'none'}", f"Schema: {config.schema}"]
    if config.project_registry_source:
        lines.append(f"Project registry: {config.project_registry_source}")
        lines.append(
            f"Project: {config.project_name}"
            + (" (default)" if config.project_name == config.default_project else "")
        )
    if not config.paths:
        lines.append("Paths: none")
    else:
        width = max(len(key) for key in config.paths)
        lines.extend(
            f"{key:<{width}}  {value}" for key, value in sorted(config.paths.items())
        )
    if not config.policy_sources:
        lines.append("Policy sources: none")
    else:
        lines.append("Policy sources:")
        for source in config.policy_sources:
            pin = f" ({source.expected_digest})" if source.expected_digest else ""
            lines.append(f"  {source.name}  {source.path}{pin}")
    return "\n".join(lines)


def composition_validation(config: ProjectConfig, *, require: bool = False) -> dict[str, Any]:
    """Observe actual v1alpha3 composition independently on every invocation."""
    if config.schema != CONFIG_SCHEMA:
        raise ProjectConfigError("composition diagnostics require project-config/v1alpha3")
    try:
        # Re-read the selected lock so subsequent execution never uses a stale expectation.
        lock = config.composition_lock
        if lock:
            if lock.source.is_symlink():
                raise CompositionError("composition lock must be a regular adjacent file")
            lock = load_composition_lock(lock.source)
        operation = require_composition if require else validate_composition
        return operation(config.policy_sources, direct=config.expected_content, lock=lock)
    except CompositionError as error:
        raise ProjectConfigError(str(error)) from error
