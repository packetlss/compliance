import copy
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from contract_fixtures import fixture_root
from examples.prepare_policy_diff_set import main
from tools.policy_diff import build_policy_diff_set
from tools.project_config import load_config
from tools.render_plan import content_digest, load_inventory_inputs, render_plan


class PolicyDiffExampleTests(unittest.TestCase):
    def test_generator_prepares_all_three_comparison_states(self):
        root = fixture_root(self)
        config = load_config(root / "compliance.yaml", "cloud")
        subject, groups, assignments = load_inventory_inputs(
            config.path("inventory"),
            config.path("assignments"),
            "cloud-account/aws-111122223333",
            config.path("resourceSchema"),
        )
        base = render_plan(subject, groups, assignments, config.policy_sources)
        base["controls"][0]["instance_id"] = (
            "company.aws.s3-account-public-access-block"
        )

        def sample(_project, subject_id):
            plan = copy.deepcopy(base)
            plan["subject"]["id"] = subject_id
            if subject_id == "host/persona-conflict-01":
                plan["resolution"] = {
                    "status": "invalid",
                    "errors": [{"type": "test-conflict"}],
                }
                plan["coverage"].update(
                    status="invalid", assessable=False, reason="resolution-errors"
                )
            plan.pop("id")
            plan["id"] = content_digest(plan)
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
        self.assertFalse(unchanged["summary"]["changed"])
        self.assertEqual(unchanged["summary"]["unchanged"], 2)
        self.assertEqual(changed["summary"]["modified"], 1)
        self.assertEqual(changed["summary"]["removed"], 1)
        self.assertEqual(changed["summary"]["added"], 1)
        self.assertEqual(incomplete["comparison"]["status"], "incomplete")
