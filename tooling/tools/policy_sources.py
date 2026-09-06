"""Named, content-addressed policy sources used for local catalog assembly."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, TypeAlias

SOURCE_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$")


@dataclass(frozen=True, order=True)
class PolicySource:
    """One independently revisioned policy tree."""

    name: str
    path: Path
    expected_digest: str | None = None

    def __post_init__(self) -> None:
        if not SOURCE_NAME.fullmatch(self.name):
            raise ValueError(
                f"invalid policy source name {self.name!r}; use lower-case letters, "
                "digits, '.', '_' or '-'"
            )
        object.__setattr__(self, "path", self.path.resolve())


PolicySources: TypeAlias = Path | PolicySource | Iterable[PolicySource]


def normalize_policy_sources(sources: PolicySources) -> tuple[PolicySource, ...]:
    """Return a name-sorted, unique source set; a Path remains legacy-compatible."""
    if isinstance(sources, Path):
        values = [PolicySource("default", sources)]
    elif isinstance(sources, PolicySource):
        values = [sources]
    else:
        values = list(sources)
    if not values:
        raise ValueError("at least one policy source is required")
    names = [source.name for source in values]
    duplicates = sorted(name for name in set(names) if names.count(name) > 1)
    if duplicates:
        raise ValueError("duplicate policy source name(s): " + ", ".join(duplicates))
    return tuple(sorted(values, key=lambda source: source.name))


def source_tree_digest(root: Path) -> str:
    """Digest the stable relative paths and bytes in one source tree."""
    if not root.is_dir():
        raise ValueError(f"policy source is not a directory: {root}")
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if (
            not path.is_file()
            or "build" in relative.parts
            or "__pycache__" in relative.parts
        ):
            continue
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def policy_source_revisions(sources: PolicySources) -> list[dict[str, str]]:
    """Calculate the actual revision of every source in canonical name order."""
    return [
        {"name": source.name, "digest": source_tree_digest(source.path)}
        for source in normalize_policy_sources(sources)
    ]


def source_pin_errors(sources: PolicySources) -> list[dict[str, Any]]:
    """Report missing source trees and expected-digest mismatches."""
    errors: list[dict[str, Any]] = []
    for source in normalize_policy_sources(sources):
        try:
            actual = source_tree_digest(source.path)
        except ValueError as error:
            errors.append({
                "type": "policy-source-unavailable",
                "policy_source": source.name,
                "path": str(source.path),
                "message": str(error),
            })
            continue
        if source.expected_digest and source.expected_digest != actual:
            errors.append({
                "type": "policy-source-digest-mismatch",
                "policy_source": source.name,
                "path": str(source.path),
                "expected": source.expected_digest,
                "actual": actual,
            })
    return errors


def rego_module_paths(
    sources: PolicySources,
    *,
    include_tests: bool,
) -> tuple[Path, ...]:
    """Return every unique Rego module without materializing an assembled tree."""
    selected: list[Path] = []
    seen_content: set[str] = set()
    for source in normalize_policy_sources(sources):
        controls_root = source.path / "controls"
        if not controls_root.is_dir():
            continue
        for path in sorted(controls_root.rglob("*.rego")):
            if not include_tests and path.name.endswith("_test.rego"):
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in seen_content:
                continue
            seen_content.add(digest)
            selected.append(path)
    return tuple(selected)


def parse_policy_source(value: str, *, base: Path | None = None) -> PolicySource:
    """Parse the CLI form NAME=PATH."""
    name, separator, raw_path = value.partition("=")
    if not separator or not raw_path:
        raise ValueError(f"invalid policy source {value!r}; expected NAME=PATH")
    path = Path(raw_path)
    if not path.is_absolute():
        path = (base or Path.cwd()) / path
    return PolicySource(name, path)
