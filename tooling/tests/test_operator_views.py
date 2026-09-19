import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools.compliance import build_parser, main
from tools.coverage import (
    COVERAGE_CLASSES,
    build_coverage_explanation,
    build_coverage_list,
    format_coverage_explanation,
    resolve_coverage_plans,
)
from tools.inventory import (
    build_inventory_explanation,
    build_inventory_list,
    format_inventory_explanation,
    format_inventory_list,
)
from tools.project_config import select_config


ROOT = Path(__file__).resolve().parents[2]
TECHNICAL_CONFIG = (
    ROOT
    / "verification/scenarios/projects/technical-only-packages/compliance.yaml"
)
ROLLOUT_CONFIG = (
    ROOT / "verification/scenarios/projects/linux-hardening-rollout/compliance.yaml"
)


def subject(asset_id, *, status="active", labels=None):
    return {
        "schema": "compliance.example/inventory-subject/v1",
        "id": asset_id,
        "type": "linux-host",
        "status": status,
        "labels": labels or {},
        "inventory": {
            "source": "unit-inventory",
            "external_id": asset_id,
            "observed_at": "2026-09-01T00:00:00Z",
        },
    }


def plan(
    asset_id,
    *,
    status="active",
    resolution="valid",
    groups=None,
    assignments=None,
    controls=None,
    excluded=None,
    requirements=None,
):
    return {
        "subject": subject(asset_id, status=status),
        "resolved_groups": groups or [],
        "assignments": assignments or [],
        "resolved_baselines": [],
        "resolved_requirement_baselines": [],
        "requirements": requirements or [],
        "controls": controls or [],
        "excluded_controls": excluded or [],
        "resolution": {
            "status": resolution,
            "errors": [] if resolution == "valid" else [{"type": "test-conflict"}],
        },
    }


class InventoryOperatorViewTests(unittest.TestCase):
    def setUp(self):
        self.subjects = {
            "host/B": {
                **subject("host/B", labels={"zone": "b", "managed": "true"}),
                "annotations": {"description": "second"},
                "attributes": {"cores": 4},
            },
            "host/A": subject("host/A", labels={"managed": "true", "zone": "a"}),
        }
        self.groups = [
            {"id": "parent", "parents": []},
            {
                "id": "managed",
                "parents": ["parent"],
                "selector": {"match_labels": {"managed": "true"}},
                "members": ["host/B"],
            },
        ]
        self.assignments = [
            {
                "id": "managed-policy",
                "target": {"group": "managed"},
                "baselines": ["example.policy@2", "example.base@1"],
            }
        ]

    def test_inventory_lists_are_bounded_useful_and_deterministic(self):
        assets = build_inventory_list(
            "assets", self.subjects, list(reversed(self.groups)), self.assignments
        )
        groups = build_inventory_list(
            "groups", self.subjects, list(reversed(self.groups)), self.assignments
        )
        assignments = build_inventory_list(
            "assignments", self.subjects, self.groups, self.assignments
        )

        self.assertEqual(
            [item["asset_id"] for item in assets["assets"]], ["host/A", "host/B"]
        )
        self.assertEqual(
            set(assets["assets"][0]),
            {"asset_id", "asset_type", "lifecycle", "labels", "source"},
        )
        self.assertEqual(
            [item["group_id"] for item in groups["groups"]], ["managed", "parent"]
        )
        self.assertEqual(
            assignments["assignments"][0]["policy_references"],
            ["example.base@1", "example.policy@2"],
        )
        self.assertIn("Supplied inventory assets", format_inventory_list(assets))
        self.assertIn("POLICY REFERENCES", format_inventory_list(assignments))

    def test_inventory_explain_contains_only_facts_and_membership(self):
        document = build_inventory_explanation(self.subjects["host/B"], self.groups)
        rendered = format_inventory_explanation(document)

        self.assertEqual(document["asset"]["asset_id"], "host/B")
        self.assertEqual(
            [group["id"] for group in document["resolved_groups"]],
            ["managed", "parent"],
        )
        self.assertIn("explicit member; selector managed=true", rendered)
        self.assertIn("inherited via managed", rendered)
        self.assertNotIn("assignment", json.dumps(document).lower())
        self.assertNotIn("Policy", rendered)

    def test_inventory_cli_uses_asset_vocabulary_without_subject_alias(self):
        parser = build_parser(select_config(["--no-config"]))
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "inventory",
                    "list",
                    "subjects",
                    "--inventory",
                    "inventory",
                    "--assignments",
                    "assignments",
                ]
            )
        args = parser.parse_args(
            [
                "inventory",
                "explain",
                "host/A",
                "--inventory",
                "inventory",
                "--assignments",
                "assignments",
                "--format",
                "json",
            ]
        )
        self.assertEqual(args.asset_id, "host/A")

        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "coverage",
                    "list",
                    "subjects",
                    "--inventory",
                    "inventory",
                    "--assignments",
                    "assignments",
                    "--policy-source",
                    "source=policy",
                ]
            )
        args = parser.parse_args(
            [
                "coverage",
                "explain",
                "host/A",
                "--inventory",
                "inventory",
                "--assignments",
                "assignments",
                "--policy-source",
                "source=policy",
            ]
        )
        self.assertEqual(args.asset_id, "host/A")


class CoverageOperatorViewTests(unittest.TestCase):
    def test_asset_list_preserves_all_five_existing_distinctions(self):
        assigned = [{"id": "a", "group": "g", "baselines": ["p@1"]}]
        check = {"instance_id": "check", "disposition": "evaluate"}
        plans = [
            plan("asset/result", assignments=assigned, controls=[check]),
            plan("asset/inactive", status="retired", assignments=assigned, controls=[check]),
            plan("asset/unassigned"),
            plan("asset/no-policy", assignments=assigned),
            plan("asset/invalid", assignments=assigned, resolution="invalid"),
        ]
        subjects = {item["subject"]["id"]: item["subject"] for item in plans}
        document = build_coverage_list("assets", subjects, [], [], list(reversed(plans)))

        rows = {item["asset_id"]: item for item in document["assets"]}
        self.assertEqual(
            {item["coverage_class"] for item in rows.values()}, set(COVERAGE_CLASSES)
        )
        self.assertEqual(
            document["summary"]["coverage_classes"],
            {name: 1 for name in COVERAGE_CLASSES},
        )
        self.assertEqual(rows["asset/no-policy"]["assignment_count"], 1)
        self.assertEqual(rows["asset/no-policy"]["assessable_check_count"], 0)
        self.assertEqual(rows["asset/invalid"]["coverage_class"], "invalid_resolution")
        self.assertEqual(rows["asset/invalid"]["assessable_check_count"], 0)

    def test_group_and_assignment_views_keep_zero_effect_rows(self):
        groups = [
            {"id": "empty", "parents": []},
            {"id": "members", "parents": []},
        ]
        assignments = [
            {"id": "empty-policy", "target": {"group": "empty"}, "baselines": ["p@1"]},
            {"id": "excluded-policy", "target": {"group": "members"}, "baselines": ["x@1"]},
        ]
        assigned = [{"id": "excluded-policy", "group": "members", "baselines": ["x@1"]}]
        excluded = [{
            "instance_id": "x",
            "disposition": "excluded",
            "provenance": [{"assignment": "excluded-policy", "baseline": "x@1"}],
        }]
        plans = [
            plan(
                "host/A",
                groups=[{"id": "members", "sources": [{"membership": "explicit", "source": "group.members"}]}],
                assignments=assigned,
                excluded=excluded,
            )
        ]
        subjects = {"host/A": plans[0]["subject"]}

        group_view = build_coverage_list(
            "groups", subjects, groups, assignments, plans
        )
        assignment_view = build_coverage_list(
            "assignments", subjects, groups, assignments, plans
        )
        empty_group = next(item for item in group_view["groups"] if item["group_id"] == "empty")
        empty_assignment = next(
            item
            for item in assignment_view["assignments"]
            if item["assignment_id"] == "empty-policy"
        )
        excluded_assignment = next(
            item
            for item in assignment_view["assignments"]
            if item["assignment_id"] == "excluded-policy"
        )

        self.assertEqual(empty_group["current_asset_count"], 0)
        self.assertEqual(empty_group["direct_assignment_count"], 1)
        self.assertEqual(empty_assignment["current_asset_count"], 0)
        self.assertEqual(excluded_assignment["current_asset_count"], 1)
        self.assertEqual(excluded_assignment["assessable_asset_count"], 0)
        self.assertEqual(excluded_assignment["excluded_check_count"], 1)
        self.assertEqual(
            excluded_assignment["coverage_classes"]["no_assessable_policy"], 1
        )

        self.assertEqual(
            group_view,
            build_coverage_list(
                "groups",
                subjects,
                list(reversed(groups)),
                list(reversed(assignments)),
                list(reversed(plans)),
            ),
        )
        self.assertEqual(
            assignment_view,
            build_coverage_list(
                "assignments",
                subjects,
                list(reversed(groups)),
                list(reversed(assignments)),
                list(reversed(plans)),
            ),
        )

    def test_coverage_resolution_calls_existing_planner_in_asset_order(self):
        subjects = {"host/B": subject("host/B"), "host/A": subject("host/A")}
        resolved = [plan("host/A"), plan("host/B")]
        with patch("tools.coverage.render_plan", side_effect=resolved) as planner:
            actual = resolve_coverage_plans(
                subjects, [], [], ("policy-source",), config="project"
            )

        self.assertEqual(actual, resolved)
        self.assertEqual(
            [call.args[0]["id"] for call in planner.call_args_list],
            ["host/A", "host/B"],
        )
        self.assertTrue(all(call.kwargs["config"] == "project" for call in planner.call_args_list))

    def test_technical_only_explanation_has_checks_and_no_objective(self):
        generated = TECHNICAL_CONFIG.parent / "generated"
        before = generated.exists()
        output = io.StringIO()
        with redirect_stdout(output):
            main(
                [
                    "--config",
                    str(TECHNICAL_CONFIG),
                    "coverage",
                    "explain",
                    "host/technical-A",
                    "--format",
                    "json",
                ]
            )
        document = json.loads(output.getvalue())
        policy = document["assignments"][0]["policies"][0]

        self.assertEqual(document["coverage_class"], "result_required")
        self.assertEqual(policy["title"], "Linux package baseline")
        self.assertEqual(policy["objectives"], [])
        self.assertEqual(
            policy["checks"][0]["title"], "Required system packages are installed"
        )
        self.assertEqual(
            policy["checks"][0]["required_evidence"][0]["evidence_type"],
            "linux.packages/v1",
        )
        self.assertEqual(generated.exists(), before)

    def test_invalid_resolution_is_explicit_and_not_an_empty_success(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main(
                [
                    "--config",
                    str(ROLLOUT_CONFIG),
                    "coverage",
                    "explain",
                    "host/persona-conflict-01",
                ]
            )
        rendered = output.getvalue()

        self.assertIn("Coverage: invalid_resolution", rendered)
        self.assertIn("Policy resolution: INVALID", rendered)
        self.assertIn("control-instance-conflict", rendered)
        self.assertIn("Applicable policy: unresolved policy", rendered)
        self.assertNotIn("Check:", rendered)
        self.assertNotIn("Coverage: unassigned", rendered)

    def test_assessment_refusal_is_bounded_and_publishes_no_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(SystemExit) as raised:
                main(
                    [
                        "--config",
                        str(ROLLOUT_CONFIG),
                        "assessment",
                        "run",
                        "host/persona-conflict-01",
                        "--evidence",
                        str(root / "evidence"),
                        "--plan-output",
                        str(root / "plans"),
                        "--output",
                        str(root / "results"),
                        "--at",
                        "2026-09-01T00:00:00Z",
                    ]
                )

            rendered = str(raised.exception)
            self.assertIn("Assessment refused", rendered)
            self.assertIn("Asset: host/persona-conflict-01", rendered)
            self.assertIn("Code: control-instance-conflict", rendered)
            self.assertIn(
                "Check: benchmark.example.linux-server.ip-forwarding-disabled",
                rendered,
            )
            self.assertIn("Policy: company.linux-server-hardening@1", rendered)
            self.assertIn(
                "coverage explain host/persona-conflict-01", rendered
            )
            self.assertNotIn("incoming_provenance", rendered)
            self.assertNotIn("definition_fingerprint", rendered)
            self.assertNotIn("net.ipv4.ip_forward", rendered)
            self.assertFalse((root / "results").exists())

    def test_ordinary_explanations_exclude_plan_internal_provenance(self):
        valid_output = io.StringIO()
        with redirect_stdout(valid_output):
            main(
                [
                    "--config",
                    str(ROLLOUT_CONFIG),
                    "coverage",
                    "explain",
                    "host/container-app-01",
                    "--format",
                    "json",
                ]
            )
        valid = json.loads(valid_output.getvalue())

        policies = [
            policy
            for assignment in valid["assignments"]
            for policy in assignment["policies"]
        ]
        objective = next(
            policy["objectives"][0]
            for policy in policies
            if policy["policy_type"] == "objective"
        )
        tailored = next(
            check
            for policy in policies
            for check in policy["checks"]
            if check["alignment"] == "tailored"
        )
        self.assertEqual(set(objective["realization"]), {"reference"})
        self.assertEqual(
            set(tailored["deviations"][0]),
            {
                "id",
                "classification",
                "rationale",
                "approval_ref",
                "review_after",
            },
        )
        self.assertNotIn("derivations", tailored)

        invalid_output = io.StringIO()
        with redirect_stdout(invalid_output):
            main(
                [
                    "--config",
                    str(ROLLOUT_CONFIG),
                    "coverage",
                    "explain",
                    "host/persona-conflict-01",
                    "--format",
                    "json",
                ]
            )
        invalid = json.loads(invalid_output.getvalue())
        failure = next(
            item
            for item in invalid["resolution"]["failures"]
            if item["reason"] == "control-instance-conflict"
        )
        self.assertEqual(set(failure), {"reason", "check_id"})

        projected = json.dumps([valid, invalid], sort_keys=True)
        for forbidden in (
            "parent_fingerprint",
            "definition_fingerprint",
            "digest",
            "policy_sources",
            "inherited_lineage",
            "lineage",
            "provenance",
            "before",
            "after",
            "existing",
            "incoming",
            "incoming_provenance",
        ):
            self.assertNotIn(f'"{forbidden}"', projected)

        human_output = io.StringIO()
        with redirect_stdout(human_output):
            main(
                [
                    "--config",
                    str(ROLLOUT_CONFIG),
                    "coverage",
                    "explain",
                    "host/container-app-01",
                ]
            )
            main(
                [
                    "--config",
                    str(ROLLOUT_CONFIG),
                    "coverage",
                    "explain",
                    "host/persona-conflict-01",
                ]
            )
        rendered = human_output.getvalue()
        self.assertIn("Approved deviation:", rendered)
        self.assertIn("Code: control-instance-conflict", rendered)
        self.assertNotIn("sha256:", rendered)
        self.assertNotIn("parent_fingerprint", rendered)
        self.assertNotIn("incoming_provenance", rendered)

    def test_objective_checks_require_one_matching_provenance_path(self):
        objective = {
            "reference": "objective/one",
            "title": "Readable objective",
            "statement": "The objective meaning.",
            "required": True,
            "adoption": {"status": "adopted"},
            "provenance": [
                {
                    "assignment": "assignment/a",
                    "baseline": "objective-policy@1",
                }
            ],
        }
        mixed_path_check = {
            "instance_id": "check/mixed",
            "title": "Check from other paths",
            "purpose": "Must not be attributed across provenance records.",
            "disposition": "evaluate",
            "alignment": "unaltered",
            "parameters": {},
            "evidence": [],
            "provenance": [
                {
                    "assignment": "assignment/a",
                    "baseline": "objective-policy@1",
                    "requirement": "objective/other",
                },
                {
                    "assignment": "assignment/b",
                    "baseline": "other-policy@1",
                    "requirement": "objective/one",
                },
            ],
        }
        source = plan(
            "host/A",
            assignments=[
                {
                    "id": "assignment/a",
                    "group": "group/a",
                    "baselines": ["objective-policy@1"],
                }
            ],
            controls=[mixed_path_check],
            requirements=[objective],
        )
        source["resolved_requirement_baselines"] = [
            {
                "assignment": "assignment/a",
                "group": "group/a",
                "reference": "objective-policy@1",
                "title": "Objective policy",
            }
        ]

        explanation = build_coverage_explanation(source)

        self.assertEqual(
            explanation["assignments"][0]["policies"][0]["objectives"][0][
                "checks"
            ],
            [],
        )

    def test_coverage_projects_current_additive_value_and_applicability(self):
        base_path = {
            "group": "group/base",
            "assignment": "assignment/base",
            "baseline": "policy.base@1",
        }
        contribution_path = {
            "group": "group/feature",
            "assignment": "assignment/feature",
            "baseline": "policy.feature@1",
        }
        contribution_identity = {
            "baseline": "policy.feature@1",
            "id": "packages",
            "requirement": "objective",
            "slot": "allowed",
        }
        objective = {
            "reference": "objective@1",
            "title": "Authorized software",
            "statement": "Only authorized software is installed.",
            "required": True,
            "adoption": {"status": "implemented"},
            "provenance": [base_path],
            "parameter_facts": {
                "states": {
                    "allowed": {
                        "bound": True,
                        "value": ["base", "postgresql"],
                        "declaration": {"binding_mode": "open"},
                        "composition": {
                            "kind": "additive-set",
                            "base_value": ["base"],
                            "base_origins": [{
                                "baseline": "policy.base@1",
                                "digest": "sha256:" + "1" * 64,
                                "applicability": base_path,
                            }],
                            "contributions": [{
                                "identity": contribution_identity,
                                "owner": {
                                    "reference": "policy.feature@1",
                                    "digest": "sha256:" + "2" * 64,
                                    "document": {"private": "frozen plan detail"},
                                    "policy_sources": [{"policy_source": "test", "path": "feature.json"}],
                                },
                                "members": ["postgresql"],
                                "applicability": [contribution_path],
                            }],
                            "member_origins": [
                                {
                                    "member": "base",
                                    "origins": [{
                                        "kind": "base",
                                        "baseline": "policy.base@1",
                                        "digest": "sha256:" + "1" * 64,
                                        "applicability": base_path,
                                    }],
                                },
                                {
                                    "member": "postgresql",
                                    "origins": [{
                                        "kind": "contribution",
                                        "identity": contribution_identity,
                                    }],
                                },
                            ],
                        },
                    }
                }
            },
        }
        source = plan(
            "host/A",
            assignments=[{
                "id": "assignment/base",
                "group": "group/base",
                "baselines": ["policy.base@1"],
            }],
            requirements=[objective],
        )
        source["resolved_requirement_baselines"] = [{
            "assignment": "assignment/base",
            "group": "group/base",
            "reference": "policy.base@1",
            "title": "Base policy",
        }]

        explanation = build_coverage_explanation(source)
        parameter = explanation["assignments"][0]["policies"][0]["objectives"][0]["parameters"][0]
        self.assertEqual(parameter["effective_value"], ["base", "postgresql"])
        self.assertEqual(
            parameter["composition"]["contributions"][0]["applicability"],
            [contribution_path],
        )
        projected = json.dumps(parameter)
        self.assertNotIn("sha256:", projected)
        self.assertNotIn("policy_sources", projected)
        self.assertNotIn("frozen plan detail", projected)
        rendered = format_coverage_explanation(explanation)
        self.assertIn('Effective parameter allowed: ["base","postgresql"]', rendered)
        self.assertIn("Contribution: policy.feature@1 #packages via 1 path(s)", rendered)

    def test_explanation_orders_domain_meaning_before_stable_ids(self):
        check = {
            "instance_id": "check.id",
            "title": "Readable check",
            "purpose": "Verify the configured value.",
            "disposition": "evaluate",
            "alignment": "unaltered",
            "parameters": {"expected": True},
            "evidence": [{"id": "observation", "type": "setting/v1", "max_age": "1h"}],
            "provenance": [{"group": "g", "assignment": "a", "baseline": "p@1"}],
        }
        source = plan(
            "host/A",
            groups=[{"id": "g", "sources": [{"membership": "explicit", "source": "group.members"}]}],
            assignments=[{"id": "a", "group": "g", "baselines": ["p@1"]}],
            controls=[check],
        )
        source["resolved_baselines"] = [
            {"assignment": "a", "group": "g", "reference": "p@1", "title": "Readable policy"}
        ]
        rendered = format_coverage_explanation(build_coverage_explanation(source))

        self.assertLess(rendered.index("Applicable policy: Readable policy"), rendered.index("Reference: p@1"))
        self.assertLess(rendered.index("Check: Readable check"), rendered.index("ID: check.id"))


if __name__ == "__main__":
    unittest.main()
