import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import yaml

from contract_fixtures import fixture_root

from tools.compliance import build_parser, main, subject_artifact_path
from tools.project_config import ProjectConfig, load_config
from tools.cli import main as console_main
from tools.assessment_provenance import artifact_digest
from assessment_fixture import planning_fields


class ComplianceCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = fixture_root(cls)
        cls.config_path = cls.root / "compliance.yaml"

    @staticmethod
    def plan_document(subject_id):
        sources = [{"name": "unit-test", "digest": "sha256:" + "2" * 64}]
        document = {
            "subject": {
                "schema": "compliance.example/inventory-subject/v1",
                "id": subject_id,
                "type": "linux-host",
                "status": "active",
                "labels": {},
                "inventory": {
                    "source": "unit-test",
                    "external_id": subject_id,
                    "observed_at": "2026-08-28T12:00:00Z",
                },
            },
            "resolved_groups": [],
            "assignments": [],
            "resolved_baselines": [],
            "resolved_requirement_baselines": [],
            "requirements": [],
            "controls": [],
            "excluded_controls": [],
            "resolution": {"status": "valid", "errors": []},
        }
        document.update(planning_fields(sources))
        from assessment_fixture import refresh_operation
        refresh_operation(document)
        document["id"] = artifact_digest(document)
        return document

    def test_command_line_path_overrides_config_default(self):
        config = ProjectConfig(paths={"inventory": Path("from-config")})
        parser = build_parser(config)

        args = parser.parse_args([
            "inventory",
            "validate",
            "--inventory",
            "from-cli",
            "--assignments",
            "assignments",
        ])

        self.assertEqual(args.inventory, Path("from-cli"))

    def test_assessment_run_accepts_fixed_evaluation_instant(self):
        config = ProjectConfig(
            policy_sources=(),
            paths={
                "inventory": Path("inventory"),
                "assignments": Path("assignments"),
                "evidence": Path("evidence"),
                "plan": Path("plans"),
                "results": Path("results"),
                "waivers": Path("waivers"),
                "resourceSchema": Path("resource-schema.json"),
            },
        )
        parser = build_parser(config)

        args = parser.parse_args([
            "assessment",
            "run",
            "host/example",
            "--at",
            "2026-09-01T00:00:00Z",
        ])

        self.assertEqual(args.at, "2026-09-01T00:00:00Z")

    def test_config_show_exposes_resolved_machine_readable_paths(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main([
                "--config", str(self.config_path),
                "--project", "cloud",
                "config", "show", "--format", "json",
            ])

        document = json.loads(output.getvalue())
        self.assertEqual(document["project_registry"], str(self.config_path))
        self.assertNotIn("workspace", document)
        self.assertEqual(document["project"], "cloud")
        project_registry = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        expected_source = (
            self.config_path.parent
            / project_registry["projects"]["cloud"]["config"]
        ).resolve()
        self.assertEqual(
            document["source"],
            str(expected_source),
        )
        self.assertEqual(
            document["paths"]["inventory"],
            str(expected_source.parent / "inventory"),
        )

    def test_config_list_exposes_project_registry_projects(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main([
                "--config", str(self.config_path),
                "--project", "cloud",
                "config", "list", "--format", "json",
            ])

        document = json.loads(output.getvalue())
        self.assertEqual(document["schema"], "compliance.example/project-registry-list/v1")
        self.assertEqual(document["project_registry"], str(self.config_path))
        self.assertNotIn("workspace", document)
        self.assertEqual(document["default_project"], "cloud")
        self.assertEqual(document["selected_project"], "cloud")
        self.assertEqual(
            [project["name"] for project in document["projects"]],
            [
                "cloud",
                "iam",
                "linux",
            ],
        )

    def test_console_config_text_uses_registry_terminology(self):
        for command, expected in (("show", "Project registry:"),
                                  ("list", "Project registry:"),
                                  ("validate", "valid project registry:")):
            with self.subTest(command=command):
                output = io.StringIO()
                with redirect_stdout(output):
                    console_main(["--config", str(self.config_path), "config", command])
                self.assertIn(expected, output.getvalue())
                self.assertNotIn("workspace", output.getvalue().lower())

    def test_registry_and_direct_selection_render_identical_plans_and_keep_paths_isolated(self):
        registry = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        selected = load_config(self.config_path, "cloud")
        with tempfile.TemporaryDirectory() as temporary:
            relocated = Path(temporary) / "registry.yaml"
            relocated.write_text(yaml.safe_dump({
                "schema": registry["schema"],
                "defaultProject": "same-project",
                "projects": {"same-project": {"config": str(selected.source)}},
            }), encoding="utf-8")
            plans = []
            for index, flags in enumerate((
                ["--config", str(self.config_path)],
                ["--config", str(self.config_path), "--project", "cloud"],
                ["--config", str(selected.source)],
                ["--config", str(relocated)],
            )):
                output_path = Path(temporary) / f"plan-{index}.json"
                with redirect_stdout(io.StringIO()):
                    console_main(flags + ["plan", "render", "cloud-account/aws-111122223333",
                                          "--output", str(output_path)])
                plans.append(json.loads(output_path.read_text(encoding="utf-8")))
            for plan in plans[1:]:
                self.assertEqual(plan, plans[0])
        configs = [load_config(self.config_path, name) for name in registry["projects"]]
        for key in ("inventory", "assignments", "waivers", "evidence", "plan", "results"):
            with self.subTest(path=key):
                paths = [config.path(key) for config in configs]
                self.assertEqual(len(set(paths)), len(configs))

    def test_inventory_validate_uses_only_project_config(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main([
                "--config", str(self.config_path),
                "--project", "cloud",
                "inventory", "validate",
            ])

        self.assertIn("valid inventory: 2 asset(s), 2 group(s), 2 assignment(s)", output.getvalue())

    def test_named_project_registry_project_uses_mock_fleet_inventory(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main([
                "--config",
                str(self.config_path),
                "--project",
                "cloud",
                "inventory",
                "validate",
            ])

        self.assertIn("valid inventory: 2 asset(s), 2 group(s), 2 assignment(s)", output.getvalue())

    def test_policy_validate_uses_project_config(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main([
                "--config", str(self.config_path),
                "--project", "cloud",
                "policy", "validate",
            ])

        self.assertIn(
            "valid policy catalog: 10 baseline document(s), 7 control manifest(s)",
            output.getvalue(),
        )


    def test_waiver_views_use_project_config(self):
        validation = io.StringIO()
        with redirect_stdout(validation):
            main([
                "--config",
                str(self.config_path),
                "--project",
                "linux",
                "waiver",
                "validate",
            ])
        self.assertIn("valid waiver catalog: 1 waiver(s)", validation.getvalue())

        listing = io.StringIO()
        with redirect_stdout(listing):
            main([
                "--config",
                str(self.config_path),
                "--project",
                "linux",
                "waiver",
                "list",
                "--at",
                "2026-08-28T12:00:00Z",
                "--format",
                "json",
            ])
        document = json.loads(listing.getvalue())
        self.assertEqual(document["summary"]["active"], 1)
        self.assertEqual(
            document["waivers"][0]["instance_id"],
            "test.packages.extra",
        )

    def test_repeatable_policy_source_overrides_assemble_locally(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main([
                "--no-config",
                "policy",
                "validate",
                "--policy-source",
                f"control-library={self.root / 'shared'}",
                "--policy-source",
                "verification-policy="
                f"{self.root / 'selection'}",
                "--policy-source",
                "environment-private="
                f"{self.root / 'iam/policy'}",
            ])

        self.assertIn("2 realization(s)", output.getvalue())

    def test_assessment_command_cutover_has_no_predecessor_aliases(self):
        parser = build_parser(ProjectConfig())
        common = [
            "--plan", "plan.json", "--at", "2026-09-01T00:00:00Z",
            "--as-of", "2026-09-02T00:00:00Z",
        ]
        args = parser.parse_args(["assessment", "mappings", *common])
        self.assertEqual(args.assessment_command, "mappings")
        grouped = parser.parse_args(["assessment", "status", "--by", "group", *common])
        self.assertEqual(grouped.by, "group")
        for removed in ("frameworks", "groups"):
            with self.subTest(removed=removed), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    parser.parse_args(["assessment", removed])
        import tools.assessment as assessment
        for removed_symbol in (
            "latest_report", "reports_for_plan", "build_status_report",
            "build_group_report", "build_framework_report",
        ):
            self.assertFalse(hasattr(assessment, removed_symbol))
        import tools.operation as operation
        for removed_symbol in ("plan_coverage", "summarize_qualifications"):
            self.assertFalse(hasattr(operation, removed_symbol))

    def test_extensionless_artifact_path_uses_subject_filename(self):
        self.assertEqual(
            subject_artifact_path(Path("generated/plans"), "saas/example/test"),
            Path("generated/plans/saas__example__test.json"),
        )

    def test_file_artifact_path_is_unchanged(self):
        path = Path("generated/plan.json")
        self.assertEqual(subject_artifact_path(path, "saas/example/test"), path)

    def test_plan_show_uses_configured_plan_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            plan = Path(temporary) / "plan.json"
            document = self.plan_document("host/test")
            plan.write_text(json.dumps(document), encoding="utf-8")
            config = ProjectConfig(paths={"plan": plan})
            parser = build_parser(config)
            args = parser.parse_args(["plan", "show"])
            output = io.StringIO()

            with redirect_stdout(output):
                args.handler(args)

        self.assertIn(f'Assessment plan: {document["id"]}', output.getvalue())
        self.assertIn("Asset:           host/test", output.getvalue())
        self.assertIn("Disposition:     unassigned", output.getvalue())
        self.assertNotIn("Coverage:", output.getvalue())

    def test_plan_show_lists_configured_plan_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            plans = Path(temporary) / "plans"
            plans.mkdir()
            for subject_id in ("host/one", "host/two"):
                path = subject_artifact_path(plans, subject_id)
                path.write_text(
                    json.dumps(self.plan_document(subject_id)),
                    encoding="utf-8",
                )
            parser = build_parser(ProjectConfig(paths={"plan": plans}))
            args = parser.parse_args(["plan", "show"])
            output = io.StringIO()

            with redirect_stdout(output):
                args.handler(args)

        self.assertIn("Assessment plans (2)", output.getvalue())
        self.assertIn("host/one", output.getvalue())
        self.assertIn("host/two", output.getvalue())
        self.assertIn("ASSET", output.getvalue())
        self.assertIn("DISPOSITION", output.getvalue())
        self.assertNotIn("COVERAGE", output.getvalue())

    def test_plan_show_json_index_uses_plan_disposition(self):
        with tempfile.TemporaryDirectory() as temporary:
            plans = Path(temporary) / "plans"
            plans.mkdir()
            for subject_id in ("host/one", "host/two"):
                subject_artifact_path(plans, subject_id).write_text(
                    json.dumps(self.plan_document(subject_id)),
                    encoding="utf-8",
                )
            parser = build_parser(ProjectConfig(paths={"plan": plans}))
            args = parser.parse_args(["plan", "show", "--format", "json"])
            output = io.StringIO()

            with redirect_stdout(output):
                args.handler(args)

        document = json.loads(output.getvalue())
        self.assertEqual(
            {entry["disposition"] for entry in document["plans"]},
            {"unassigned"},
        )
        self.assertTrue(all("coverage" not in entry for entry in document["plans"]))
        self.assertTrue(all("assessable" not in entry for entry in document["plans"]))

    def test_plan_render_help_uses_asset_vocabulary(self):
        parser = build_parser(ProjectConfig())
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit):
            parser.parse_args(["plan", "render", "--help"])

        rendered = output.getvalue()
        self.assertIn("ASSET", rendered)
        self.assertIn("assets", rendered)
        self.assertNotIn("subject", rendered.lower())

    def test_plan_show_selects_subject_from_configured_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            plans = Path(temporary) / "plans"
            plans.mkdir()
            plan = subject_artifact_path(plans, "host/one")
            document = self.plan_document("host/one")
            plan.write_text(json.dumps(document), encoding="utf-8")
            parser = build_parser(ProjectConfig(paths={"plan": plans}))
            args = parser.parse_args(["plan", "show", "host/one"])
            output = io.StringIO()

            with redirect_stdout(output):
                args.handler(args)

        self.assertIn(f'Assessment plan: {document["id"]}', output.getvalue())


if __name__ == "__main__":
    unittest.main()
