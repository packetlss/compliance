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
    def test_read_browser_is_static_external_and_accepts_only_derived_responses(self):
        browser = Path(__file__).resolve().parents[1] / "examples/read-browser"
        javascript = (browser / "app.js").read_text(encoding="utf-8")
        html = (browser / "index.html").read_text(encoding="utf-8")

        for name in ("README.md", "index.html", "styles.css", "app.js"):
            self.assertTrue((browser / name).is_file())
        for schema in (
            "inventory-assets-view/v1alpha1",
            "coverage-assets-view/v1alpha1",
            "coverage-asset-explanation/v1alpha1",
            "assessment-status-view/v1alpha1",
            "assessment-explanation-view/v1alpha1",
            "assessment-mappings-view/v1alpha1",
            "framework-satisfaction-status/v1alpha1",
            "framework-satisfaction-explanation/v1alpha1",
            "policy-diff/v1alpha1",
        ):
            self.assertIn(schema, javascript)
        for forbidden in (
            "fetch(",
            "XMLHttpRequest",
            "assessment-plan/v4",
            "assessment-results/v4",
            "localStorage",
            "indexedDB",
        ):
            self.assertNotIn(forbidden, javascript)
        self.assertIn('type="file"', html)

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
        expected = {
            ("assessment", "explain"),
            ("assessment", "mappings"),
            ("assessment", "run"),
            ("assessment", "status"),
            ("framework", "validate"),
            ("framework", "status"),
            ("framework", "explain"),
            ("config", "list"),
            ("config", "show"),
            ("config", "validate"),
            ("coverage", "explain"),
            ("coverage", "list"),
            ("inventory", "explain"),
            ("inventory", "graph"),
            ("inventory", "list"),
            ("inventory", "validate"),
            ("plan", "render"),
            ("plan", "show"),
            ("policy", "diff"),
            ("policy", "diff-set"),
            ("policy", "validate"),
            ("producer", "list"),
            ("producer", "schema"),
            ("producer", "validate"),
            ("waiver", "explain"),
            ("waiver", "list"),
            ("waiver", "validate"),
        }

        self.assertEqual(commands, expected)
        self.assertEqual(set(CLI_EXAMPLES), expected)

    def test_domain_examples_cover_retained_special_states(self):
        self.assertEqual(set(DOMAIN_EXAMPLES), {
            "assessment.filters",
            "assessment.mapping-traceability",
            "collector.mock-api",
            "coverage.current-views",
            "evidence.contracts",
            "evidence.schema-enforcement",
            "inventory.multi-parent-dag",
            "output.json-contracts",
            "policy.control-implementations",
            "policy.invalid-resolution",
            "policy.multi-source-realization",
            "policy.overlay-provenance",
            "policy.overlay-substitute",
            "policy.governed-tailoring",
            "requirements.all-of",
            "requirements.missing-evidence",
            "requirements.realization-roll-up",
            "waiver.application",
            "waiver.filters",
        })

    def test_mock_fleet_inventory_oracle_uses_named_dag_not_group_count(self):
        validation = "valid inventory: 3 asset(s), 7 group(s), 2 assignment(s)"
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
            "assets": [{
                "asset_id": MOCK_FLEET_PRIMARY_AWS_SUBJECT,
                "historical_outcome": "fail",
            }],
        }
        filtered_mappings = {
            "filters": {
                "external_refs": ["CSA-CCM-v4.1:LOG-domain"],
                "groups": ["aws-production-accounts"],
                "levels": ["technical"],
                "outcomes": [],
                "plan_alignment": [],
            },
            "mappings": [
                {
                    "asset_id": subject_id,
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
                filtered_mappings,
                secondary_result,
            )
        )

        extra_failure = copy.deepcopy(filtered_status)
        extra_failure["assets"].append(
            {"asset_id": MOCK_FLEET_SECONDARY_AWS_SUBJECT}
        )
        self.assertFalse(
            mock_fleet_filter_contract_holds(
                extra_failure,
                filtered_mappings,
                secondary_result,
            )
        )

        missing_secondary_mapping = copy.deepcopy(filtered_mappings)
        missing_secondary_mapping["mappings"] = [
            missing_secondary_mapping["mappings"][0]
        ]
        self.assertFalse(
            mock_fleet_filter_contract_holds(
                filtered_status,
                missing_secondary_mapping,
                secondary_result,
            )
        )

        failing_secondary = copy.deepcopy(secondary_result)
        failing_secondary["outcome"] = "fail"
        failing_secondary["results"][-1]["status"] = "fail"
        self.assertFalse(
            mock_fleet_filter_contract_holds(
                filtered_status,
                filtered_mappings,
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
            "coverage": "build_coverage_list",
            "render_plan": "render_plan",
            "evaluate_plan": "evaluate_plan_document",
            "assessment": "build_status_view",
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
