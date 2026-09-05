"""Release-aware console entry point for the compliance CLI."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .locked_artifacts import locked_artifact_runtime
from .project_config import ProjectConfigError, release_validation, select_config
from .release import format_release_identity, tooling_release_identity
from .release_lock import format_release_validation


def _remaining_after_global_options(arguments: list[str]) -> list[str]:
    selector = argparse.ArgumentParser(add_help=False)
    group = selector.add_mutually_exclusive_group()
    group.add_argument("--config")
    group.add_argument("--no-config", action="store_true")
    selector.add_argument("--project")
    _, remaining = selector.parse_known_args(arguments)
    return remaining


def _run_version(arguments: list[str]) -> bool:
    if arguments == ["--version"]:
        print(format_release_identity())
        return True
    if not arguments or arguments[0] != "version":
        return False

    parser = argparse.ArgumentParser(
        prog="compliance version",
        description="Show installed compliance tooling release identity.",
    )
    parser.add_argument("--format", choices=("table", "json"), default="table")
    args = parser.parse_args(arguments[1:])
    identity = tooling_release_identity()
    if args.format == "json":
        print(json.dumps(identity.document(), indent=2, sort_keys=True))
    else:
        print(format_release_identity(identity))
    return True


def _run_release(arguments: list[str]) -> bool:
    remaining = _remaining_after_global_options(arguments)
    if not remaining or remaining[0] != "release":
        return False

    parser = argparse.ArgumentParser(
        prog="compliance release",
        description="Inspect or validate a locked downstream release composition.",
    )
    commands = parser.add_subparsers(dest="release_command", required=True)
    for name, help_text in (
        ("show", "show the locked composition and current materialization state"),
        ("validate", "require the locked composition to match installed/local inputs"),
    ):
        child = commands.add_parser(name, help=help_text)
        child.add_argument("--format", choices=("table", "json"), default="table")

    args = parser.parse_args(remaining[1:])
    try:
        config = select_config(arguments, validate_release=False)
        report = release_validation(config)
    except ProjectConfigError as error:
        parser.error(str(error))

    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_release_validation(report))
    if args.release_command == "validate" and not report["valid"]:
        parser.exit(2, "compliance release: locked composition is invalid\n")
    return True


def _run_locked_config_validate(arguments: list[str]) -> bool:
    if _remaining_after_global_options(arguments) != ["config", "validate"]:
        return False
    try:
        config = select_config(arguments)
    except ProjectConfigError as error:
        raise SystemExit(f"compliance: configuration error: {error}") from error
    if not config.is_locked:
        return False
    if config.project_registry_source:
        print(
            f"valid project registry: {config.project_registry_source}; "
            f"project {config.project_name}: {config.source} "
            f"({len(config.paths)} configured path(s), "
            f"{len(config.policy_sources)} policy source(s), {config.schema})"
        )
    else:
        print(
            f"valid project config: {config.source} "
            f"({len(config.paths)} configured path(s), "
            f"{len(config.policy_sources)} policy source(s), {config.schema})"
        )
    return True


def main(argv: Sequence[str] | None = None) -> None:
    """Handle release contracts, then run normal commands under the selected artifact version."""
    arguments = list(argv if argv is not None else sys.argv[1:])
    if (
        _run_version(arguments)
        or _run_release(arguments)
        or _run_locked_config_validate(arguments)
    ):
        return

    try:
        config = select_config(arguments)
    except ProjectConfigError as error:
        raise SystemExit(f"compliance: configuration error: {error}") from error

    from .compliance import main as compliance_main

    with locked_artifact_runtime(config):
        compliance_main(arguments)


if __name__ == "__main__":
    main()
