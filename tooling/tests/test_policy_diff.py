from tools.assessment_provenance import artifact_digest
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from contract_fixtures import fixture_root

from tools.artifact_validation import validate_assessment_plan
from tools.compliance import default_schema_path, main
from tools.policy_diff import (
    build_policy_diff,
    build_policy_diff_set,
    format_policy_diff,
    format_policy_diff_set,
    validate_policy_diff,
    validate_policy_diff_set,
)
from tools.project_config import load_config
from tools.render_plan import (
    control_definition_fingerprint,
    load_inventory_inputs,
    render_plan,
)


class PolicyDiffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = fixture_root(cls)
        project_registry = cls.root / "compliance.yaml"

        def render_project_plan(project: str, subject_id: str):
            config = load_config(project_registry, project)
            subject, groups, assignments = load_inventory_inputs(
                config.path("inventory"),
                config.path("assignments"),
                subject_id,
                config.path("resourceSchema") or default_schema_path(),
            )
            return render_plan(
                subject,
                groups,
                assignments,
                config.policy_sources,
            )

        macos_fixture = Path(__file__).resolve().parent / "fixtures/macos-project"
        mock_config = load_config(project_registry, "cloud")
        subject, groups, assignments = load_inventory_inputs(
            macos_fixture / "inventory",
            macos_fixture / "assignments",
            "workstation/tooling-macos-fixture",
            mock_config.path("resourceSchema") or default_schema_path(),
        )
        cls.macos_plan = render_plan(
            subject,
            groups,
            assignments,
            mock_config.policy_sources,
        )
        cls.iam_plan = render_project_plan(
            "iam",
            "host/restricted-linux-01",
        )
        cls.invalid_plan = copy.deepcopy(cls.macos_plan)
        cls.invalid_plan["resolution"] = {"status": "invalid", "errors": [{"type": "test-conflict"}]}
        cls.invalid_plan["coverage"].update(status="invalid", assessable=False, reason="resolution-errors")
        from assessment_fixture import refresh_operation
        refresh_operation(cls.invalid_plan)
        cls.invalid_plan.pop("id")
        cls.invalid_plan["id"] = artifact_digest(cls.invalid_plan)
        cls.standard_plan = render_project_plan(
            "linux",
            "host/configuration-linux-01",
        )

    @staticmethod
    def resign(plan):
        from assessment_fixture import refresh_operation
        refresh_operation(plan)
        plan.pop("id", None)
        plan["id"] = artifact_digest(plan)
        validate_assessment_plan(plan)
        return plan

    @staticmethod
    def write_plan(root, name, plan):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(plan), encoding="utf-8")
        return path

    def test_identical_plans_have_no_effective_or_context_changes(self):
        document = build_policy_diff(self.macos_plan, copy.deepcopy(self.macos_plan))

        self.assertFalse(document["summary"]["changed"])
        self.assertFalse(document["context"]["changed"])
        self.assertEqual(document["summary"]["total_changes"], 0)
        self.assertEqual(document["comparison"]["status"], "complete")
        validate_policy_diff(document)

    def test_revision_only_churn_is_context_not_effective_policy(self):
        after = copy.deepcopy(self.macos_plan)
        after["inventory_revision"] = "sha256:" + "0" * 64
        self.resign(after)

        document = build_policy_diff(self.macos_plan, after)

        self.assertFalse(document["summary"]["changed"])
        self.assertTrue(document["context"]["changed"])
        self.assertEqual(
            document["context"]["changed_fields"],
            ["plan_id", "inventory_revision", "operation_digest"],
        )

    def test_control_criteria_change_is_exact_and_attributable(self):
        after = copy.deepcopy(self.macos_plan)
        control = next(
            item
            for item in after["controls"]
            if item["instance_id"] == "developer.macos.shellcheck-required"
        )
        control["parameters"] = {"required": ["shellcheck", "shfmt"]}
        control["policy_inputs"]["instance"]["parameters"] = copy.deepcopy(control["parameters"])
        control["definition_fingerprint"] = control_definition_fingerprint(control["policy_inputs"]["instance"])
        self.resign(after)

        document = build_policy_diff(self.macos_plan, after)
        change = document["control_changes"][0]

        self.assertTrue(document["summary"]["changed"])
        self.assertEqual(document["summary"]["controls"]["modified"], 1)
        self.assertEqual(change["identity"], "developer.macos.shellcheck-required")
        self.assertEqual(change["change"], "modified")
        self.assertIn("parameters", change["changed_fields"])
        self.assertEqual(
            change["before"]["parameters"],
            {"required": ["shellcheck"]},
        )
        self.assertEqual(
            change["after"]["parameters"],
            {"required": ["shellcheck", "shfmt"]},
        )

    def test_exclusion_shows_frozen_derivation_and_approval(self):
        before = copy.deepcopy(self.macos_plan)
        excluded = before["excluded_controls"].pop()
        template = next(
            item
            for item in before["controls"]
            if item["implementation"] == excluded["implementation"]
        )
        active = copy.deepcopy(excluded)
        active.update({
            "disposition": "evaluate",
            "alignment": "unaltered",
            "derivations": [],
            "deviations": [],
            "lineage": [excluded["lineage"][0]],
            "entrypoint": template["entrypoint"],
            "severity": template["severity"],
            "remediation": template["remediation"],
            "evidence": template["evidence"],
            "implementation_sources": template["implementation_sources"],
        })
        active["policy_inputs"]["definition"] = copy.deepcopy(template["policy_inputs"]["definition"])
        active["policy_inputs"]["parameters_schema"] = copy.deepcopy(template["policy_inputs"]["parameters_schema"])
        before["controls"].append(active)
        before["controls"].sort(key=lambda item: item["instance_id"])
        before["coverage"]["active_control_count"] += 1
        before["coverage"]["excluded_control_count"] -= 1
        self.resign(before)

        document = build_policy_diff(before, self.macos_plan)
        change = next(
            item
            for item in document["control_changes"]
            if item["identity"] == "benchmark.example.macos.audit-formula-required"
        )
        rendered = format_policy_diff(document)

        self.assertEqual(change["change"], "excluded")
        self.assertEqual(change["after"]["deviations"][0]["id"], "DEV-MAC-002")
        self.assertEqual(
            change["after"]["derivations"][0]["before"]["parameters"],
            {"required": ["example-audit-tool"]},
        )
        self.assertIn("test/approval", rendered)
        self.assertIn('"disposition":"excluded"', rendered)

    def test_requirement_revision_is_a_modified_stable_requirement(self):
        after = copy.deepcopy(self.iam_plan)
        requirement = after["requirements"][0]
        requirement["reference"] = "company.iam.role-based-access@2"
        requirement["title"] = "Centrally governed interactive access"
        for baseline in after['resolved_requirement_baselines']:
            for pin in baseline['requirements']:
                pin['requirement'] = requirement['reference']
        from assessment_fixture import freeze_policy_inputs
        freeze_policy_inputs(after)
        self.resign(after)

        document = build_policy_diff(self.iam_plan, after)
        change = document["requirement_changes"][0]

        self.assertEqual(change["identity"], "company.iam.role-based-access")
        self.assertEqual(change["change"], "modified")
        self.assertIn("reference", change["changed_fields"])
        self.assertIn("title", change["changed_fields"])

    def test_collection_order_does_not_create_an_effective_change(self):
        after = copy.deepcopy(self.macos_plan)
        after["controls"].reverse()
        after["resolved_groups"].reverse()
        self.resign(after)

        document = build_policy_diff(self.macos_plan, after)

        self.assertFalse(document["summary"]["changed"])
        self.assertTrue(document["context"]["changed"])

    def test_cli_exit_codes_distinguish_same_changed_and_incomplete(self):
        changed = copy.deepcopy(self.macos_plan)
        changed["controls"][0]["remediation"] = "Use the newly approved procedure."
        self.resign(changed)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before_path = root / "before.json"
            after_path = root / "after.json"
            invalid_path = root / "invalid.json"
            before_path.write_text(json.dumps(self.macos_plan), encoding="utf-8")
            after_path.write_text(json.dumps(changed), encoding="utf-8")
            invalid_path.write_text(json.dumps(self.invalid_plan), encoding="utf-8")

            same_output = io.StringIO()
            with redirect_stdout(same_output):
                main([
                    "--no-config", "policy", "diff",
                    str(before_path), str(before_path),
                ])
            self.assertIn("NO EFFECTIVE POLICY CHANGES", same_output.getvalue())

            changed_output = io.StringIO()
            with redirect_stdout(changed_output):
                with self.assertRaises(SystemExit) as raised:
                    main([
                        "--no-config", "policy", "diff",
                        str(before_path), str(after_path), "--format", "json",
                    ])
            self.assertEqual(raised.exception.code, 1)
            self.assertTrue(json.loads(changed_output.getvalue())["summary"]["changed"])

            incomplete_output = io.StringIO()
            with redirect_stdout(incomplete_output):
                with self.assertRaises(SystemExit) as raised:
                    main([
                        "--no-config", "policy", "diff",
                        str(invalid_path), str(invalid_path),
                    ])
            self.assertEqual(raised.exception.code, 2)
            self.assertIn("Comparison: INCOMPLETE", incomplete_output.getvalue())

    def test_cli_rejects_different_subjects_as_usage_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before_path = root / "before.json"
            after_path = root / "after.json"
            before_path.write_text(json.dumps(self.macos_plan), encoding="utf-8")
            after_path.write_text(json.dumps(self.iam_plan), encoding="utf-8")

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main([
                        "--no-config", "policy", "diff",
                        str(before_path), str(after_path),
                    ])
        self.assertEqual(raised.exception.code, 2)

    def test_plan_set_identical_nested_sets_are_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before"
            after = root / "after"
            self.write_plan(before, "macos.json", self.macos_plan)
            self.write_plan(before, "nested/iam.json", self.iam_plan)
            self.write_plan(after, "macos.json", self.macos_plan)
            self.write_plan(after, "nested/iam.json", self.iam_plan)

            document = build_policy_diff_set(before, after)

        self.assertEqual(document["comparison"]["status"], "complete")
        self.assertFalse(document["summary"]["changed"])
        self.assertEqual(document["summary"]["unchanged"], 2)
        self.assertEqual(
            [item["subject_id"] for item in document["subjects"]],
            ["host/restricted-linux-01", "workstation/tooling-macos-fixture"],
        )
        validate_policy_diff_set(document)
        tampered = copy.deepcopy(document)
        tampered["summary"]["unchanged"] = 1
        with self.assertRaisesRegex(ValueError, "/summary/unchanged"):
            validate_policy_diff_set(tampered)

    def test_plan_set_reports_added_removed_and_modified_subjects(self):
        changed = copy.deepcopy(self.macos_plan)
        changed["controls"][0]["remediation"] = "Follow the approved runbook."
        self.resign(changed)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before"
            after = root / "after"
            self.write_plan(before, "macos.json", self.macos_plan)
            self.write_plan(before, "iam.json", self.iam_plan)
            self.write_plan(after, "macos.json", changed)
            self.write_plan(after, "standard.json", self.standard_plan)

            document = build_policy_diff_set(before, after)
            rendered = format_policy_diff_set(document)

        self.assertTrue(document["summary"]["changed"])
        self.assertEqual(document["summary"]["added"], 1)
        self.assertEqual(document["summary"]["removed"], 1)
        self.assertEqual(document["summary"]["modified"], 1)
        changes = {
            item["subject_id"]: item["change"]
            for item in document["subjects"]
        }
        self.assertEqual(changes["host/configuration-linux-01"], "added")
        self.assertEqual(changes["host/restricted-linux-01"], "removed")
        self.assertEqual(changes["workstation/tooling-macos-fixture"], "modified")
        self.assertIn("Subject detail: workstation/tooling-macos-fixture", rendered)
        self.assertIn("EFFECTIVE POLICY CHANGED", rendered)

    def test_plan_set_context_only_change_is_unchanged(self):
        after_plan = copy.deepcopy(self.macos_plan)
        after_plan["inventory_revision"] = "sha256:" + "0" * 64
        self.resign(after_plan)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before"
            after = root / "after"
            self.write_plan(before, "macos.json", self.macos_plan)
            self.write_plan(after, "macos.json", after_plan)

            document = build_policy_diff_set(before, after)

        item = document["subjects"][0]
        self.assertEqual(item["change"], "unchanged")
        self.assertTrue(item["diff"]["context"]["changed"])
        self.assertFalse(document["summary"]["changed"])

    def test_plan_set_invalid_resolution_is_incomplete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before"
            after = root / "after"
            self.write_plan(before, "invalid.json", self.invalid_plan)
            self.write_plan(after, "invalid.json", self.invalid_plan)

            document = build_policy_diff_set(before, after)
            rendered = format_policy_diff_set(document)

        self.assertEqual(document["comparison"]["status"], "incomplete")
        self.assertEqual(document["summary"]["incomplete"], 1)
        self.assertFalse(document["summary"]["changed"])
        self.assertIn("Result: INCOMPLETE", rendered)

    def test_plan_set_rejects_empty_mixed_and_duplicate_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            empty = root / "empty"
            valid = root / "valid"
            mixed = root / "mixed"
            malformed = root / "malformed"
            duplicate = root / "duplicate"
            empty.mkdir()
            self.write_plan(valid, "macos.json", self.macos_plan)
            self.write_plan(mixed, "macos.json", self.macos_plan)
            (mixed / "other.json").write_text('{"kind": "other"}', encoding="utf-8")
            self.write_plan(malformed, "macos.json", self.macos_plan)
            (malformed / "broken.json").write_text("{", encoding="utf-8")
            self.write_plan(duplicate, "one.json", self.macos_plan)
            self.write_plan(duplicate, "two.json", self.macos_plan)

            with self.assertRaisesRegex(ValueError, "contains no JSON plans"):
                build_policy_diff_set(empty, valid)
            with self.assertRaisesRegex(ValueError, "not an assessment plan"):
                build_policy_diff_set(mixed, valid)
            with self.assertRaisesRegex(ValueError, "invalid JSON assessment plan"):
                build_policy_diff_set(malformed, valid)
            with self.assertRaisesRegex(ValueError, "duplicate subject plan"):
                build_policy_diff_set(duplicate, valid)

    def test_plan_set_cli_exit_codes(self):
        changed = copy.deepcopy(self.macos_plan)
        changed["controls"][0]["remediation"] = "Use a reviewed procedure."
        self.resign(changed)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before"
            same = root / "same"
            after = root / "after"
            invalid = root / "invalid"
            self.write_plan(before, "macos.json", self.macos_plan)
            self.write_plan(same, "macos.json", self.macos_plan)
            self.write_plan(after, "macos.json", changed)
            self.write_plan(invalid, "invalid.json", self.invalid_plan)

            output = io.StringIO()
            with redirect_stdout(output):
                main([
                    "--no-config", "policy", "diff-set",
                    str(before), str(same),
                ])
            self.assertIn("NO EFFECTIVE POLICY CHANGES", output.getvalue())

            output = io.StringIO()
            with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
                main([
                    "--no-config", "policy", "diff-set",
                    str(before), str(after), "--format", "json",
                ])
            self.assertEqual(raised.exception.code, 1)
            self.assertTrue(json.loads(output.getvalue())["summary"]["changed"])

            output = io.StringIO()
            with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
                main([
                    "--no-config", "policy", "diff-set",
                    str(invalid), str(invalid),
                ])
            self.assertEqual(raised.exception.code, 2)
            self.assertIn("Comparison: INCOMPLETE", output.getvalue())


if __name__ == "__main__":
    unittest.main()
