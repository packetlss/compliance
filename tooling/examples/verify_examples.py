#!/usr/bin/env python3
"""Run the synthetic examples using project-registry project locations."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from tools.project_config import ProjectConfigError, load_config

try:
    from . import _verify_examples_core as _core
except ImportError:  # Direct execution by path.
    import _verify_examples_core as _core


_project_registry_override = os.environ.get("COMPLIANCE_EXAMPLE_PROJECT_REGISTRY")
if _project_registry_override:
    _core.PROJECT_REGISTRY = Path(_project_registry_override).resolve()


def project_fixture_root(
    project: str,
    *,
    project_registry: Path | None = None,
) -> Path:
    """Resolve a project's fixture directory from the project registry."""
    source = (project_registry or _core.PROJECT_REGISTRY).resolve()
    try:
        config = load_config(source, project)
    except ProjectConfigError as error:
        raise _core.ExampleFailure(
            f"cannot resolve project {project!r} from {source}: {error}"
        ) from error
    if config.source is None:
        raise _core.ExampleFailure(
            f"project {project!r} has no resolved configuration source"
        )
    return config.source.parent / "fixtures"


def _collect(self, project: str, *, fixtures: Path | None = None) -> Path:
    evidence = self.root / project / "evidence"
    fixture_root = fixtures or project_fixture_root(project)
    command = [
        sys.executable,
        str(_core.MOCK_COLLECTOR),
        str(fixture_root),
        str(evidence),
        "--collected-at",
        _core.EXAMPLE_INSTANT,
    ]
    completed = subprocess.run(
        command,
        cwd=_core.WORKSPACE_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise _core.ExampleFailure(completed.stdout + completed.stderr)
    self.domain_covered.add("collector.mock-api")
    self._display(
        "collector.mock-api",
        command,
        completed.stdout + completed.stderr,
    )
    return evidence


# Preserve the existing executable coverage engine while replacing its only
# repository-name-derived fixture resolver with project-registry resolution.
_core.ExampleRunner.collect = _collect

# Re-export the established public names so imports of examples.verify_examples
# continue to behave as before.
for _name, _value in vars(_core).items():
    if not _name.startswith("_") and _name not in globals():
        globals()[_name] = _value

PROJECT_REGISTRY = _core.PROJECT_REGISTRY
ExampleRunner = _core.ExampleRunner
main = _core.main


if __name__ == "__main__":
    main()
