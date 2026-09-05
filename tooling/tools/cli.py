"""Release-aware console entry point for the compliance CLI."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .project_config import ProjectConfigError, select_config, composition_validation
from .release import format_release_identity, tooling_release_identity


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


def _run_composition(arguments: list[str]) -> bool:
    remaining = _remaining_after_global_options(arguments)
    if not remaining or remaining[0] != "composition":
        return False
    parser = argparse.ArgumentParser(prog="compliance composition", description="Inspect actual composition and optional expected enforcement.")
    commands = parser.add_subparsers(dest="operation", required=True)
    for name in ("show", "validate"):
        child = commands.add_parser(name)
        child.add_argument("--format", choices=("table", "json"), default="table")
    args = parser.parse_args(remaining[1:])
    try:
        config = select_config(arguments, validate_runtime=False)
        report = composition_validation(config)
    except ProjectConfigError as error:
        parser.error(str(error))
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Actual composition: {report['compositionDigest']}")
        print(f"Tooling execution: {report['actual']['tooling']['execution']['kind']}")
        for source in report['actual']['policySources']:
            print(f"  {source['name']}: {source['content']['digest']}")
        print("Enforcement: " + ("valid" if report['valid'] else "invalid"))
        for error in report['errors']:
            print("  " + error)
    if args.operation == "validate" and not report['valid']:
        parser.exit(2, "compliance composition: expected composition mismatch\n")
    return True


def main(argv: Sequence[str] | None = None) -> None:
    """Handle identity and composition diagnostics, then dispatch domain commands."""
    arguments = list(argv if argv is not None else sys.argv[1:])
    if (
        _run_version(arguments)
        or _run_composition(arguments)
    ):
        return

    from .compliance import main as compliance_main

    compliance_main(arguments)


if __name__ == "__main__":
    main()
