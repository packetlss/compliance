"""Canonical content identity for compliance-tooling runtime/build source."""

from __future__ import annotations

import hashlib
import stat
from pathlib import Path


TOOLING_SOURCE_DIGEST_ALGORITHM = (
    "compliance.example/tooling-source-tree-digest/v1alpha1"
)
_INCLUDED_FILES = (
    Path("pyproject.toml"),
    Path("scripts/build-wheel.py"),
    Path("schemas/inventory/resource.schema.json"),
    Path("schemas/waivers/resource.schema.json"),
)
_INCLUDED_DIRECTORIES = (Path("tools"), Path("package-data"))
_EXCLUDED_RELATIVE = frozenset({Path("tools/release-metadata.json")})
_EXCLUDED_COMPONENTS = frozenset({"__pycache__", "build", "dist"})


class ToolingSourceError(ValueError):
    """The tooling source tree cannot be represented by the canonical digest."""


def _included_paths(root: Path) -> tuple[Path, ...]:
    root = root.resolve()
    paths: set[Path] = set()
    for relative in _INCLUDED_FILES:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise ToolingSourceError(f"required tooling source file is unavailable: {relative}")
        paths.add(relative)
    for directory_relative in _INCLUDED_DIRECTORIES:
        directory = root / directory_relative
        if not directory.is_dir() or directory.is_symlink():
            raise ToolingSourceError(
                f"required tooling source directory is unavailable: {directory_relative}"
            )
        for path in directory.rglob("*"):
            relative = path.relative_to(root)
            if relative in _EXCLUDED_RELATIVE:
                continue
            if any(component in _EXCLUDED_COMPONENTS for component in relative.parts):
                continue
            if path.is_symlink():
                raise ToolingSourceError(
                    f"tooling source digest does not support symbolic links: {relative}"
                )
            mode = path.stat(follow_symlinks=False).st_mode
            if stat.S_ISDIR(mode):
                continue
            if not stat.S_ISREG(mode):
                raise ToolingSourceError(
                    f"tooling source digest supports only regular files: {relative}"
                )
            if path.suffix == ".pyc":
                continue
            paths.add(relative)
    return tuple(sorted(paths, key=lambda item: item.as_posix()))


def tooling_source_digest(root: Path) -> str:
    """Hash canonical tooling source content independent of Git and location."""
    root = root.resolve()
    if not root.is_dir():
        raise ToolingSourceError(f"tooling source root is not a directory: {root}")
    digest = hashlib.sha256()
    for relative in _included_paths(root):
        path = root / relative
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"
