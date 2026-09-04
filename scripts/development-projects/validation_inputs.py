#!/usr/bin/env python3
"""Assemble and verify co-located development-project validation inputs."""

from __future__ import annotations

import argparse
import stat
import subprocess
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = Path("validation/development-projects/compliance.yaml")
ASSEMBLY_ROOTS = (
    Path("tooling"),
    Path("policy-sources/control-library"),
    Path("policy-sources/verification-policy"),
    Path("projects"),
)
TOP_LEVEL_ENTRIES = {"compliance.yaml", "tooling", "policy-sources", "projects"}
POLICY_SOURCE_ENTRIES = {"control-library", "verification-policy"}
PROJECT_ENTRIES = {"mock-fleet", "server-personas"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(REPOSITORY_ROOT), *arguments], text=True
    ).strip()


def require_non_git_root(root: Path) -> None:
    require(not (root / ".git").exists(), f"assembly root has .git metadata: {root}")
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        capture_output=True,
    )
    require(result.returncode != 0, f"assembly root is inside a Git repository: {root}")


def export_roots(root: Path, revision: str) -> None:
    archive = subprocess.Popen(
        [
            "git",
            "-C",
            str(REPOSITORY_ROOT),
            "archive",
            revision,
            "--",
            *(str(path) for path in ASSEMBLY_ROOTS),
        ],
        stdout=subprocess.PIPE,
    )
    require(archive.stdout is not None, "git archive did not provide output")
    extracted = subprocess.run(["tar", "-x", "-C", str(root)], stdin=archive.stdout)
    archive.stdout.close()
    archive_status = archive.wait()
    require(archive_status == 0 and extracted.returncode == 0, "unable to export committed roots")


def file_map(root: Path) -> dict[Path, tuple[bytes, bool]]:
    files: dict[Path, tuple[bytes, bool]] = {}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), f"assembly inputs must be materialized, not symlinked: {path}")
        if path.is_file():
            relative = path.relative_to(root)
            executable = bool(path.stat().st_mode & stat.S_IXUSR)
            files[relative] = (path.read_bytes(), executable)
    return files


def expected_file_map(revision: str) -> dict[Path, tuple[bytes, bool]]:
    with tempfile.TemporaryDirectory(prefix="development-projects-expected-") as temporary:
        root = Path(temporary)
        export_roots(root, revision)
        return file_map(root)


def verify(root: Path) -> None:
    require(root.is_dir(), f"assembly root is unavailable: {root}")
    require_non_git_root(root)
    require(
        {path.name for path in root.iterdir()} == TOP_LEVEL_ENTRIES,
        "assembly root must contain only the registry and four explicit co-located roots",
    )
    require(
        {path.name for path in (root / "policy-sources").iterdir()} == POLICY_SOURCE_ENTRIES,
        "assembly must keep exactly the two independently named policy-source producers",
    )
    require(
        {path.name for path in (root / "projects").iterdir() if path.is_dir()} == PROJECT_ENTRIES,
        "assembly must keep mock-fleet and server-personas as separate project roots",
    )
    require(
        not any(path.name == ".git" for path in root.rglob(".git")),
        "assembly must not contain component Git metadata",
    )
    require(
        not any(path.is_file() for path in (root / "projects").glob("*/generated/**/*")),
        "assembly contains generated project output",
    )
    revision = git("rev-parse", "HEAD")
    expected_registry = subprocess.check_output(
        ["git", "-C", str(REPOSITORY_ROOT), "show", f"{revision}:{REGISTRY_PATH}"]
    )
    require(
        (root / "compliance.yaml").read_bytes() == expected_registry,
        "assembly registry differs from the committed project validation registry",
    )
    require(
        file_map(root) == {
            **expected_file_map(revision),
            Path("compliance.yaml"): (expected_registry, False),
        },
        "assembly roots differ from the committed destination revision",
    )
    print(
        "Verified temporary non-Git assembly with explicit tooling, policy-source, and project roots",
        flush=True,
    )


def assemble(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    require_non_git_root(root)
    require(not any(root.iterdir()), f"assembly requires an empty directory: {root}")
    require(
        not git("status", "--porcelain", "--untracked-files=all"),
        "commit destination changes before assembling the exact head under test",
    )
    revision = git("rev-parse", "HEAD")
    export_roots(root, revision)
    registry = subprocess.check_output(
        ["git", "-C", str(REPOSITORY_ROOT), "show", f"{revision}:{REGISTRY_PATH}"]
    )
    (root / "compliance.yaml").write_bytes(registry)
    verify(root)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("assemble", "verify"):
        subparser = commands.add_parser(command)
        subparser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        if args.command == "assemble":
            assemble(root)
        else:
            verify(root)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"assembly error: {error}\n")


if __name__ == "__main__":
    main()
