import argparse
import copy
import importlib
import io
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from examples.verify_examples import (
    CLI_EXAMPLES,
    DOMAIN_EXAMPLES,
    EXAMPLE_COLLECTORS,
    MOCK_FLEET_PRIMARY_AWS_SUBJECT,
    MOCK_FLEET_SECONDARY_AWS_SUBJECT,
    main as example_main,
    mock_fleet_filter_contract_holds,
    mock_fleet_inventory_contract_holds,
    validate_feature_coverage,
)
from tools.compliance import build_parser
from tools.project_config import select_config


def leaf_commands(
    parser: argparse.ArgumentParser,
    prefix: tuple[str, ...] = (),
) -> set[tuple[str, ...]]:
    leaves: set[tuple[str, ...]] = set()
    subparsers = next(
        (
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        ),
        None,
    )
    if subparsers is None:
        return {prefix}
    for name, child in subparsers.choices.items():
        leaves.update(leaf_commands(child, (*prefix, name)))
    return leaves


class ExampleCoverageTests(unittest.TestCase):
    def test_every_feature_has_one_primary_scenario(self):
        document = validate_feature_coverage()

        self.assertEqual(
            document["scenarios"]["linux-hardening-rollout"]["role"],
            "verification",
        )
        self.assertEqual(
            document["scenarios"]["linux-hardening-rollout"]["project"],
            "linux-hardening-rollout",
        )

    def test_every_public_cli_command_has_a_registered_example(self):
        config = select_config(["--no-config"])
        commands = leaf_commands(build_parser(config))

        self.assertEqual(commands, set(CLI_EXAMPLES))
        self.assertEqual(len(commands), 20)

    def test_domain_examples_cover_retained_special_states(self):
        self.assertIn("policy.invalid-resolution", DOMAIN_EXAMPLES)
        self.assertIn("waiver.application", DOMAIN_EXAMPLES)
        self.assertIn("requirements.all-of", DOMAIN_EXAMPLES)
        self.assertIn("requirements.missing-evidence", DOMAIN_EXAMPLES)
        self.assertEqual(len(DOMAIN_EXAMPLES), 18)

    def test_mock_fleet_inventory_oracle_uses_named_dag_not_group_count(self):
        validation = "valid inventory: 3 subject(s), 7 group(s), 2 assignment(s)"
        graph = "cloud-services -> production-services -> aws-production-accounts"
        explanation = "Resolved groups: aws-production-accounts"

        self.assertTrue(
            mock_fleet_inventory_contract_holds(validation, graph, explanation)
        )
        self.assertFalse(
            mock_fleet_inventory_contract_holds(
                validation,
                "cloud-services -> production-services",
                explanation,
            )
        )

    def test_mock_fleet_filter_oracle_preserves_passing_secondary_aws(self):
        filtered_status = {
            "filters": {
                "groups": ["aws-production-accounts"],
                "outcomes": ["fail"],
                "plan_alignment": [],
            },
            "subjects": [{
                "subject_id": MOCK_FLEET_PRIMARY_AWS_SUBJECT,
                "historical_outcome": "fail",
            }],
        }
        filtered_frameworks = {
            "filters": {
                "external_refs": ["CSA-CCM-v4.1:LOG-domain"],
                "groups": ["aws-production-accounts"],
                "levels": ["technical"],
                "outcomes": [],
                "plan_alignment": [],
            },
            "mappings": [
                {
                    "subject_id": subject_id,
                    "external_ref": "CSA-CCM-v4.1:LOG-domain",
                    "mapping_level": "technical",
                }
                for subject_id in (
                    MOCK_FLEET_PRIMARY_AWS_SUBJECT,
                    MOCK_FLEET_SECONDARY_AWS_SUBJECT,
                )
            ],
        }
        secondary_result = {
            "subject_id": MOCK_FLEET_SECONDARY_AWS_SUBJECT,
            "outcome": "pass",
            "results": [{"status": "pass"} for _ in range(5)],
        }

        self.assertTrue(
            mock_fleet_filter_contract_holds(
                filtered_status,
                filtered_frameworks,
                secondary_result,
            )
        )

        extra_failure = copy.deepcopy(filtered_status)
        extra_failure["subjects"].append(
            {"subject_id": MOCK_FLEET_SECONDARY_AWS_SUBJECT}
        )
        self.assertFalse(
            mock_fleet_filter_contract_holds(
                extra_failure,
                filtered_frameworks,
                secondary_result,
            )
        )

        missing_secondary_framework = copy.deepcopy(filtered_frameworks)
        missing_secondary_framework["mappings"] = [
            missing_secondary_framework["mappings"][0]
        ]
        self.assertFalse(
            mock_fleet_filter_contract_holds(
                filtered_status,
                missing_secondary_framework,
                secondary_result,
            )
        )

        failing_secondary = copy.deepcopy(secondary_result)
        failing_secondary["outcome"] = "fail"
        failing_secondary["results"][-1]["status"] = "fail"
        self.assertFalse(
            mock_fleet_filter_contract_holds(
                filtered_status,
                filtered_frameworks,
                failing_secondary,
            )
        )

    def test_registered_examples_cover_tooling_implementation_sets(self):
        tooling = Path(__file__).resolve().parents[1]
        self.assertEqual(EXAMPLE_COLLECTORS, {"mock-api": "automated"})
        self.assertEqual(set(EXAMPLE_COLLECTORS), {
            path.name for path in (tooling / "collectors").iterdir() if path.is_dir()
        })
        self.assertFalse((tooling / "collectors/macos").exists())

    def test_removed_configuration_surface_is_not_discoverable(self):
        tooling = Path(__file__).resolve().parents[1]
        parser = build_parser(select_config(["--no-config"]))
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["configuration", "render"])
        self.assertFalse((tooling / "tools/configuration.py").exists())
        self.assertEqual(
            list((tooling / "tools/schemas").glob("configuration-*.schema.json")),
            [],
        )

    def test_legacy_operator_modules_are_internal_only(self):
        tooling = Path(__file__).resolve().parents[1]
        retained_symbols = {
            "inventory": "format_group_graph",
            "render_plan": "render_plan",
            "evaluate_plan": "evaluate_plan_document",
            "assessment": "build_status_report",
            "control_realization": "roll_up_plan_requirements",
        }
        for module_name, symbol in retained_symbols.items():
            with self.subTest(module=module_name):
                module = importlib.import_module(f"tools.{module_name}")
                self.assertTrue(callable(getattr(module, symbol)))
                self.assertFalse(hasattr(module, "parse_args"))
                self.assertFalse(hasattr(module, "main"))

                direct = subprocess.run(
                    [
                        sys.executable,
                        str(tooling / "tools" / f"{module_name}.py"),
                        "--help",
                    ],
                    cwd=tooling,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(direct.returncode, 0)
                self.assertNotIn("usage:", direct.stdout + direct.stderr)

                module_execution = subprocess.run(
                    [sys.executable, "-m", f"tools.{module_name}", "--help"],
                    cwd=tooling,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(module_execution.returncode, 0)
                self.assertEqual(module_execution.stdout + module_execution.stderr, "")

    def test_show_selections_are_discoverable(self):
        output = io.StringIO()
        with redirect_stdout(output):
            example_main(["--list"])

        self.assertIn("waiver", output.getvalue())
        self.assertIn("waiver.explain", output.getvalue())
        self.assertNotIn("configuration.", output.getvalue())



if __name__ == "__main__":
    unittest.main()
