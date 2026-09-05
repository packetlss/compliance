from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from examples.verify_examples import project_fixture_root


class ExampleProjectPathTests(unittest.TestCase):
    def test_fixture_root_follows_project_registry_project_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "compliance-development-projects/projects/mock-fleet"
            project.mkdir(parents=True)
            (project / "compliance.yaml").write_text(
                """schema: compliance.example/project-config/v1alpha3
policySources:
  - name: control-library
    path: ../../../compliance-control-library/policies
paths:
  inventory: inventory
  assignments: assignments
  evidence: generated/evidence
  plan: generated/plans
  results: generated/results
  waivers: waivers
""",
                encoding="utf-8",
            )
            project_registry = root / "compliance.yaml"
            project_registry.write_text(
                """schema: compliance.example/project-registry/v1alpha1
defaultProject: mock-fleet
projects:
  mock-fleet:
    config: compliance-development-projects/projects/mock-fleet/compliance.yaml
""",
                encoding="utf-8",
            )

            self.assertEqual(
                project_fixture_root("mock-fleet", project_registry=project_registry),
                project.resolve() / "fixtures",
            )


if __name__ == "__main__":
    unittest.main()
