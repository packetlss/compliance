from tools.assessment_provenance import artifact_digest
from tools.compliance import default_schema_path
import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from contract_fixtures import fixture_root
from examples.prepare_policy_diff_set import main, _render, _resign
from tools.artifact_validation import validate_assessment_plan
from tools.policy_diff import load_policy_plan_set
from tools.policy_diff import build_policy_diff_set
from tools.project_config import load_config
from tools.render_plan import load_inventory_inputs, render_plan, control_definition_fingerprint


class PolicyDiffExampleTests(unittest.TestCase):
    def test_generator_prepares_all_three_comparison_states(self):
        root = fixture_root(self)
        config = load_config(root / "compliance.yaml", "cloud")
        subject, groups, assignments = load_inventory_inputs(
            config.path("inventory"),
            config.path("assignments"),
            "cloud-account/aws-111122223333",
            default_schema_path(),
        )
        base = render_plan(subject, groups, assignments, config.policy_sources)
        base["controls"][0]["instance_id"] = (
            "company.aws.s3-account-public-access-block"
        )

        base["controls"][0]["policy_inputs"]["instance"]["instance_id"] = base["controls"][0]["instance_id"]
        base["controls"][0]["definition_fingerprint"] = control_definition_fingerprint(base["controls"][0]["policy_inputs"]["instance"])
        base["controls"][0]["policy_inputs"]["instance"][
            "definition_fingerprint"
        ] = base["controls"][0]["definition_fingerprint"]

        def sample(_project, subject_id):
            plan = copy.deepcopy(base)
            plan["subject"]["id"] = subject_id
            if subject_id == "host/persona-conflict-01":
                plan["resolution"] = {
                    "status": "invalid",
                    "errors": [{"type": "test-conflict"}],
                }
            from assessment_fixture import refresh_operation
            refresh_operation(plan)
            plan.pop("id")
            plan["id"] = artifact_digest(plan)
            return plan

        output = root / "samples"
        stdout = io.StringIO()
        with (
            patch("examples.prepare_policy_diff_set._render", side_effect=sample),
            redirect_stdout(stdout),
        ):
            main(["--output", str(output)])
        unchanged = build_policy_diff_set(
            output / "unchanged/before", output / "unchanged/after"
        )
        changed = build_policy_diff_set(
            output / "changed/before", output / "changed/after"
        )
        incomplete = build_policy_diff_set(
            output / "incomplete/before", output / "incomplete/after"
        )
        self.assertIn("expected exit 0", stdout.getvalue())
        self.assertIn("scripts/dev cli --no-config policy diff-set", stdout.getvalue())
        self.assertNotIn("uv run compliance", stdout.getvalue())
        self.assertFalse(unchanged["summary"]["changed"])
        self.assertEqual(unchanged["summary"]["unchanged"], 2)
        self.assertEqual(changed["summary"]["modified"], 1)
        self.assertEqual(changed["summary"]["removed"], 1)
        self.assertEqual(changed["summary"]["added"], 1)
        self.assertEqual(incomplete["comparison"]["status"], "incomplete")

    def test_v4_project_uses_tooling_schema_and_resigns_diff_fixture(self):
        root = fixture_root(self)
        config = load_config(root / "compliance.yaml", "cloud")
        document = json.loads(config.source.read_text())
        document["schema"] = "compliance.example/project-config/v1alpha3"
        config.source.write_text(json.dumps(document))
        with patch("examples.prepare_policy_diff_set.PROJECT_REGISTRY", root / "compliance.yaml"):
            plan = _render("cloud", "cloud-account/aws-111122223333")
        self.assertEqual(plan["schema"], "compliance.example/assessment-plan/v4")
        self.assertEqual(plan["provenance"]["planningComposition"]["actual"]["tooling"]["execution"],
                         {"kind": "source"})
        snapshots = root / "v4-snapshots"
        snapshots.mkdir()
        snapshot = snapshots / "plan.json"
        snapshot.write_text(json.dumps(plan))
        unchanged = build_policy_diff_set(snapshots, snapshots)
        self.assertFalse(unchanged["summary"]["changed"])
        self.assertEqual(unchanged["summary"]["unchanged"], 1)
        before = plan["id"]
        plan["controls"][0]["remediation"] = "Synthetic changed runbook"
        _resign(plan)
        self.assertNotEqual(plan["id"], before)
        validate_assessment_plan(plan)
        changed_snapshots = root / "changed-v4-snapshots"
        changed_snapshots.mkdir()
        (changed_snapshots / "plan.json").write_text(json.dumps(plan))
        changed = build_policy_diff_set(snapshots, changed_snapshots)
        self.assertEqual(changed["summary"]["modified"], 1)
        self.assertEqual(changed["comparison"]["status"], "complete")
        # V4 admission must retain identity/provenance validation.
        plan["provenance"]["planningComposition"]["actual"]["tooling"]["source"]["digest"] = "sha256:" + "0" * 64
        snapshot.write_text(json.dumps(plan))
        with self.assertRaises(ValueError):
            load_policy_plan_set(snapshots)
