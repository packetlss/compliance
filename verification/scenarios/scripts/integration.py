#!/usr/bin/env python3
"""Assemble and verify the destination-local canonical scenario inputs."""

from __future__ import annotations

import argparse
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

SCENARIOS_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SCENARIOS_ROOT.parents[1]
FIXTURE_PATH = Path("verification/fixtures/iam-private-boundary")
PRIVATE_POLICY_PATH = FIXTURE_PATH / "policy"
MATERIALIZED_PRIVATE_PATH = Path("external-sources/environment-private")
ASSEMBLY_ROOTS = (
    Path("tooling"),
    Path("policy-sources/control-library"),
    Path("policy-sources/verification-policy"),
    Path("projects"),
    FIXTURE_PATH,
    Path("verification/scenarios"),
)
TOP_LEVEL_ENTRIES = {
    "compliance.yaml",
    "external-sources",
    "policy-sources",
    "projects",
    "tooling",
    "verification",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(REPOSITORY_ROOT), *arguments], text=True
    ).strip()


def require_non_git_root(root: Path) -> None:
    require(not (root / ".git").exists(), f"integration root has .git metadata: {root}")
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        capture_output=True,
    )
    require(result.returncode != 0, f"integration root is inside a Git repository: {root}")


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
    require(
        archive_status == 0 and extracted.returncode == 0,
        "unable to export committed scenario inputs",
    )


def file_map(root: Path) -> dict[Path, tuple[bytes, bool]]:
    files: dict[Path, tuple[bytes, bool]] = {}
    for path in sorted(root.rglob("*")):
        require(
            not path.is_symlink(),
            f"assembly inputs must be materialized, not symlinked: {path}",
        )
        if path.is_file():
            relative = path.relative_to(root)
            executable = bool(path.stat().st_mode & stat.S_IXUSR)
            files[relative] = (path.read_bytes(), executable)
    return files


def materialize_private_source(root: Path) -> None:
    fixture_policy = root / PRIVATE_POLICY_PATH
    private_root = root / MATERIALIZED_PRIVATE_PATH
    require(fixture_policy.is_dir(), f"IAM fixture policy is missing: {fixture_policy}")
    require(not private_root.exists(), f"private source root already exists: {private_root}")
    private_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(fixture_policy, private_root)
    for source in sorted(fixture_policy.rglob("*")):
        if source.is_file():
            destination = private_root / source.relative_to(fixture_policy)
            require(
                source.stat().st_ino != destination.stat().st_ino
                or source.stat().st_dev != destination.stat().st_dev,
                f"private policy was linked instead of physically copied: {destination}",
            )
    require(
        file_map(private_root) == file_map(fixture_policy),
        "independently materialized environment-private content changed",
    )
    shutil.rmtree(fixture_policy)
    require(
        not fixture_policy.exists(),
        "fixture policy remained in the execution assembly after materialization",
    )


def transform_export(root: Path) -> None:
    materialize_private_source(root)
    shutil.copyfile(
        root / "verification/scenarios/integration/compliance.yaml",
        root / "compliance.yaml",
    )


def expected_file_map(revision: str) -> dict[Path, tuple[bytes, bool]]:
    with tempfile.TemporaryDirectory(prefix="scenario-integration-expected-") as temporary:
        root = Path(temporary)
        export_roots(root, revision)
        transform_export(root)
        return file_map(root)


def verify(root: Path) -> None:
    require(root.is_dir(), f"integration root is unavailable: {root}")
    require_non_git_root(root)
    require(
        {path.name for path in root.iterdir()} == TOP_LEVEL_ENTRIES,
        "integration root must contain only the registry and declared destination inputs",
    )
    require(
        {path.name for path in (root / "policy-sources").iterdir()}
        == {"control-library", "verification-policy"},
        "integration must keep exactly the shared-library and verification-policy producers",
    )
    require(
        {path.name for path in (root / "verification").iterdir()}
        == {"fixtures", "scenarios"},
        "integration must contain exactly the scenario and fixture ownership roots",
    )
    require(
        {path.name for path in (root / "verification/fixtures").iterdir()}
        == {"iam-private-boundary"},
        "integration must contain only the approved IAM boundary fixture",
    )
    require(
        {path.name for path in (root / "external-sources").iterdir()}
        == {"environment-private"},
        "integration must contain exactly one independently materialized private source",
    )
    require(
        not (root / PRIVATE_POLICY_PATH).exists(),
        "scenario execution can still traverse the IAM fixture policy path",
    )
    private_root = (root / MATERIALIZED_PRIVATE_PATH).resolve()
    fixture_root = (root / FIXTURE_PATH).resolve()
    shared_root = (root / "policy-sources/control-library/policies").resolve()
    verification_root = (root / "policy-sources/verification-policy/policies").resolve()
    require(
        not private_root.is_relative_to(fixture_root)
        and not private_root.is_relative_to(shared_root)
        and not private_root.is_relative_to(verification_root),
        "environment-private is nested beneath another semantic source root",
    )
    require(
        not any(path.name == ".git" for path in root.rglob(".git")),
        "integration root must not contain Git metadata",
    )
    require(
        (root / "compliance.yaml").read_bytes()
        == (root / "verification/scenarios/integration/compliance.yaml").read_bytes(),
        "integration registry differs from the scenario-owned registry",
    )
    revision = git("rev-parse", "HEAD")
    require(
        file_map(root) == expected_file_map(revision),
        "integration assembly differs from the transformed committed destination revision",
    )
    print(f"Verified destination revision: {revision}", flush=True)
    print(f"Verified temporary non-Git scenario assembly: {root}", flush=True)
    print(f"Independent environment-private root: {private_root}", flush=True)


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
    transform_export(root)
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
        parser.exit(1, f"integration error: {error}\n")


if __name__ == "__main__":
    main()
