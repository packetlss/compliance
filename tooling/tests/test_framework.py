from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from tests.assessment_fixture import evidence_document, evidence_plan
from tools.assessment_provenance import member_plan_digest
from tools.composition import composition_digest
from tools.evaluate_plan import control_error_result, evaluate_plan_document
from tools.framework import (
    build_status, declaration_digest, declaration_projection, load_declarations,
    validate_project_declarations,
)
from tools.render_plan import source_tree_digest


def declaration(determination: str = "affirmative") -> dict:
    governance = {"subject": "subject", "owner": "owner", "determination": determination}
    if determination != "not_established":
        governance["review"] = {"reference": "review", "approvedBy": "approver", "approvedAt": "2026-09-01T00:00:00Z"}
    return {
        "apiVersion": "compliance.example/v1alpha1",
        "kind": "FrameworkObligationDeclaration",
        "metadata": {"name": "example", "revision": "1", "owner": "owner", "review": {"reference": "review", "approvedBy": "approver", "approvedAt": "2026-09-01T00:00:00Z"}},
        "spec": {
            "framework": {"id": "example", "profile": "profile", "version": "1"},
            "scope": {"id": "scope", "description": "Supplied scope.", "groupRefs": [{"name": "scope-group"}]},
            "obligations": [{"id": "one", "disposition": "applicable", "interpretation": "Reviewed governance basis.", "basis": {"category": "governance-declared", "governance": governance}}],
        },
    }


def account() -> dict:
    return {"operation": {"operation_id": "sha256:" + "0" * 64, "members": [{"subject_id": "host/a", "resolved_groups": [{"id": "scope-group"}]}], "selection_witness": {"mode": "groups", "groups": [{"id": "scope-group", "members": ["host/a"]}]}}, "evaluated_at": "2026-09-01T00:00:00Z", "query_instant": "2026-09-01T00:00:00Z", "members": []}


class FrameworkDeclarationTests(unittest.TestCase):
    def test_owned_set_order_does_not_change_digest_but_text_does(self):
        first = declaration()
        second = copy.deepcopy(first)
        second["spec"]["scope"]["groupRefs"].append({"name": "another-group"})
        second["spec"]["scope"]["groupRefs"].reverse()
        reordered = copy.deepcopy(second)
        reordered["spec"]["scope"]["groupRefs"].reverse()
        self.assertEqual(declaration_projection(second), declaration_projection(reordered))
        self.assertEqual(declaration_digest(second), declaration_digest(reordered))
        changed = copy.deepcopy(first)
        changed["spec"]["obligations"][0]["interpretation"] = "Different reviewed interpretation."
        self.assertNotEqual(declaration_digest(first), declaration_digest(changed))

    def test_declaration_only_mutation_does_not_change_ordinary_identity_vectors(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, plan = evidence_plan(root)
            evidence = root / "evidence"
            evidence.mkdir()
            (evidence / "observation.json").write_text(
                json.dumps(evidence_document()), encoding="utf-8",
            )

            def passing_control(data, _reason):
                result = control_error_result(data, "Synthetic passing decision.")
                result["status"] = "pass"
                return result

            with patch("tools.evaluate_plan.evaluate_control", side_effect=passing_control):
                report = evaluate_plan_document(
                    plan, evidence, (source,), evaluated_at=datetime(2026, 9, 1, tzinfo=UTC),
                )
            identities = {
                "policy_source": source_tree_digest(source.path),
                "planning_composition": composition_digest(
                    plan["provenance"]["planningComposition"]["actual"],
                ),
                "member_plan": member_plan_digest(plan),
                "operation": plan["operation"]["operation_id"],
                "bound_plan": plan["id"],
                "result": report["id"],
            }
            changed = declaration()
            changed["spec"]["obligations"][0]["interpretation"] = "A declaration-only mutation."
            self.assertNotEqual(declaration_digest(declaration()), declaration_digest(changed))
            self.assertEqual(identities, {
                "policy_source": source_tree_digest(source.path),
                "planning_composition": composition_digest(
                    plan["provenance"]["planningComposition"]["actual"],
                ),
                "member_plan": member_plan_digest(plan),
                "operation": plan["operation"]["operation_id"],
                "bound_plan": plan["id"],
                "result": report["id"],
            })

    def test_governance_states_use_fail_first_framework_words(self):
        for determination, expected in (("affirmative", "satisfied"), ("negative", "not_satisfied"), ("not_established", "not_established")):
            with self.subTest(determination=determination):
                item = declaration(determination)
                item["digestAlgorithm"] = "compliance.example/framework-obligation-declaration-digest/v1alpha1"
                item["digest"] = declaration_digest(item)
                self.assertEqual(build_status(item, account(), [], [])["state"], expected)

    def test_retired_framework_basis_and_field_are_rejected(self):
        governance = declaration()["spec"]["obligations"][0]["basis"]["governance"]
        for basis in (
            {"category": "external-judgment"},
            {"category": "governance-declared", "governance": governance, "externalReference": "external/authority"},
        ):
            with self.subTest(basis=basis):
                item = declaration()
                item["spec"]["obligations"][0]["basis"] = basis
                with tempfile.TemporaryDirectory() as temporary:
                    path = Path(temporary) / "declaration.json"
                    path.write_text(json.dumps(item), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "invalid FrameworkObligationDeclaration"):
                        load_declarations(path)

    def test_each_current_framework_basis_validates_and_projects(self):
        pin = {
            "reference": "example.objective@1", "digest": "sha256:" + "a" * 64,
            "groupRefs": [{"name": "scope-group"}],
        }
        bases = {
            "governance-declared": declaration()["spec"]["obligations"][0]["basis"],
            "evidence-assessed-objective": {"category": "evidence-assessed-objective", "objectivePins": [pin]},
            "direct-technical-policy": {"category": "direct-technical-policy", "directPolicyPins": [pin]},
            "mixed-governance-assessed": {
                "category": "mixed-governance-assessed",
                "governance": declaration()["spec"]["obligations"][0]["basis"]["governance"],
                "objectivePins": [pin],
            },
        }
        for category, basis in bases.items():
            with self.subTest(category=category), tempfile.TemporaryDirectory() as temporary:
                item = declaration()
                item["spec"]["obligations"][0]["basis"] = basis
                path = Path(temporary) / "declaration.json"
                path.write_text(json.dumps(item), encoding="utf-8")
                loaded = load_declarations(path)[0]
                status = build_status(loaded, account(), [], [])
                self.assertEqual(status["obligations"][0]["basis"], category)

    def test_excluded_assessed_row_remains_visible_without_history(self):
        item = declaration()
        row = item["spec"]["obligations"][0]
        row["disposition"] = "excluded"
        row["rationale"] = "Governance excluded this ledger entry."
        row["basis"] = {"category": "evidence-assessed-objective", "objectivePins": [{"reference": "example.objective@1", "digest": "sha256:" + "a" * 64, "groupRefs": [{"name": "scope-group"}]}]}
        item["digestAlgorithm"] = "compliance.example/framework-obligation-declaration-digest/v1alpha1"
        item["digest"] = declaration_digest(item)
        status = build_status(item, account(), [], [])
        self.assertEqual(status["state"], "not_established")
        self.assertEqual(status["obligations"][0]["state"], "excluded")
        self.assertEqual(status["obligations"][0]["rationale"], "Governance excluded this ledger entry.")

    def test_not_established_governance_may_be_reviewed_or_unreviewed(self):
        for reviewed in (False, True):
            with self.subTest(reviewed=reviewed):
                item = declaration("not_established")
                if reviewed:
                    item["spec"]["obligations"][0]["basis"]["governance"]["review"] = {
                        "reference": "review", "approvedBy": "approver", "approvedAt": "2026-09-01T00:00:00Z",
                    }
                with tempfile.TemporaryDirectory() as temporary:
                    path = Path(temporary) / "declaration.json"
                    path.write_text(json.dumps(item), encoding="utf-8")
                    loaded = load_declarations(path)[0]
                status = build_status(loaded, account(), [], [])
                self.assertEqual(status["state"], "not_established")
                self.assertEqual(status["obligations"][0]["support"][0]["determination"], "not_established")
                self.assertEqual(status["obligations"][0]["support"][0]["state"], "unknown")

    def test_assessed_support_retains_each_subject_outcome_and_qualification(self):
        item = declaration()
        item["spec"]["obligations"][0]["basis"] = {"category": "evidence-assessed-objective", "objectivePins": [{"reference": "example.objective@1", "digest": "sha256:" + "a" * 64, "groupRefs": [{"name": "scope-group"}]}]}
        item["digestAlgorithm"] = "compliance.example/framework-obligation-declaration-digest/v1alpha1"
        item["digest"] = declaration_digest(item)
        historical = account()
        historical["operation"]["members"].append({"subject_id": "host/b", "resolved_groups": [{"id": "scope-group"}]})
        historical["operation"]["selection_witness"]["groups"][0]["members"].append("host/b")
        historical["members"] = [
            {"subject_id": "host/a", "accounting_disposition": "result_required", "historical_interpretation": "validated", "result_id": "result-a", "plan_id": "plan-a", "plan_alignment": "plan_aligned", "evidence_timeliness": {"qualification": "available"}, "recorded_waiver_qualification": {"waivers": [], "counts": {}}},
            {"subject_id": "host/b", "accounting_disposition": "result_required", "historical_interpretation": "validated", "result_id": "result-b", "plan_id": "plan-b", "plan_alignment": "different_plan", "evidence_timeliness": {"qualification": "unavailable"}, "recorded_waiver_qualification": {"waivers": [{"qualification": "expired"}], "counts": {"expired": 1}}},
        ]
        plans = [{"id": f"plan-{suffix}", "requirements": [{"reference": "example.objective@1", "digest": "sha256:" + "a" * 64, "provenance": [{"group": "scope-group"}]}]} for suffix in ("a", "b")]
        reports = [{"id": f"result-{suffix}", "requirement_assessments": [{"requirement": "example.objective@1", "status": "pass", "reason": f"Exact retained support {suffix}."}]} for suffix in ("a", "b")]
        status = build_status(item, historical, plans, reports)
        support = status["obligations"][0]["support"][0]["subject_support"]
        self.assertEqual(status["state"], "satisfied")
        self.assertEqual([row["outcomes"][0]["reason"] for row in support], ["Exact retained support a.", "Exact retained support b."])
        self.assertEqual(support[1]["qualifications"]["recorded_waiver_qualification"]["counts"], {"expired": 1})
        self.assertNotIn("reason", support[1])

    def test_missing_assessed_history_is_attributable_and_not_established(self):
        item = declaration()
        item["spec"]["obligations"][0]["basis"] = {
            "category": "evidence-assessed-objective",
            "objectivePins": [{
                "reference": "example.objective@1", "digest": "sha256:" + "a" * 64,
                "groupRefs": [{"name": "scope-group"}],
            }],
        }
        item["digestAlgorithm"] = "compliance.example/framework-obligation-declaration-digest/v1alpha1"
        item["digest"] = declaration_digest(item)
        incomplete = account()
        incomplete["members"] = [{
            "subject_id": "host/a", "accounting_disposition": "result_required",
            "historical_interpretation": "unavailable", "result_id": None, "plan_id": "plan-a",
        }]
        status = build_status(item, incomplete, [], [])
        support = status["obligations"][0]["support"][0]
        self.assertEqual(status["state"], "not_established")
        self.assertEqual(support["state"], "unknown")
        self.assertEqual(support["subject_support"][0]["reason"], "exact_retained_result_support_unavailable")

        retained = account()
        retained["members"] = [{
            "subject_id": "host/a", "accounting_disposition": "result_required",
            "historical_interpretation": "validated", "result_id": "result-a", "plan_id": "plan-a",
        }]
        absent_pin = build_status(item, retained, [{"id": "plan-a", "requirements": []}], [{
            "id": "result-a", "requirement_assessments": [],
        }])
        self.assertEqual(absent_pin["state"], "not_established")
        self.assertEqual(absent_pin["obligations"][0]["support"][0]["subject_support"][0]["reason"], "pin_absent_from_exact_retained_plan_provenance")

        absent_outcome = build_status(item, retained, [{
            "id": "plan-a", "requirements": [{
                "reference": "example.objective@1", "digest": "sha256:" + "a" * 64,
                "provenance": [{"group": "scope-group"}],
            }],
        }], [{"id": "result-a", "requirement_assessments": []}])
        self.assertEqual(absent_outcome["state"], "not_established")
        self.assertEqual(absent_outcome["obligations"][0]["support"][0]["subject_support"][0]["reason"], "pin_has_no_exact_retained_assessment_outcome")

        missing_scope = copy.deepcopy(item)
        missing_scope["spec"]["scope"]["groupRefs"] = [{"name": "unwitnessed-group"}]
        missing_scope["spec"]["obligations"][0]["basis"]["objectivePins"][0]["groupRefs"] = [{"name": "unwitnessed-group"}]
        missing_scope["digest"] = declaration_digest(missing_scope)
        with self.assertRaisesRegex(ValueError, "operation anchor lacks required frozen group scope witness"):
            build_status(missing_scope, account(), [], [])

        explicit_scope = account()
        explicit_scope["operation"]["selection_witness"] = {"mode": "explicit"}
        with self.assertRaisesRegex(ValueError, "operation anchor lacks required frozen group scope witness"):
            build_status(item, explicit_scope, [], [])

    def test_admission_rejects_objective_pin_unbound_from_its_group(self):
        item = declaration()
        item["spec"]["obligations"][0]["basis"] = {"category": "evidence-assessed-objective", "objectivePins": [{"reference": "example.objective@1", "digest": "sha256:" + "a" * 64, "groupRefs": [{"name": "scope-group"}]}]}
        with (
            patch("tools.framework.load_inventory_catalog", return_value=(
                {}, [{"id": "scope-group"}],
                [{"target": {"group": "other-group"}, "baselines": []}],
            )),
            patch("tools.framework.load_policy_catalogs", return_value=({}, {}, [])),
            patch("tools.framework.load_requirement_catalogs", return_value=(
                {"example.objective@1": {"_digest": "sha256:" + "a" * 64}}, {}, {}, [],
            )),
        ):
            with self.assertRaisesRegex(ValueError, "incoherent"):
                validate_project_declarations([item], inventory=Path("inventory"), assignments=Path("assignments"), resource_schema=Path("schema"), policy_sources=())

    def test_direct_policy_pin_accepts_assigned_overlay_ancestry_and_exact_history(self):
        base_digest = "sha256:" + "b" * 64
        overlay_digest = "sha256:" + "c" * 64
        item = declaration()
        item["spec"]["obligations"][0]["basis"] = {
            "category": "direct-technical-policy",
            "directPolicyPins": [{
                "reference": "example.base@1", "digest": base_digest,
                "groupRefs": [{"name": "scope-group"}],
            }],
        }
        baselines = {
            "example.base@1": {"_digest": base_digest, "kind": "Baseline", "spec": {}},
            "example.overlay@1": {
                "_digest": overlay_digest,
                "kind": "BaselineOverlay",
                "spec": {"extends": [{"baseline": "example.base@1", "digest": base_digest}]},
            },
        }
        with (
            patch("tools.framework.load_inventory_catalog", return_value=(
                {}, [{"id": "scope-group"}],
                [{"target": {"group": "scope-group"}, "baselines": ["example.overlay@1"]}],
            )),
            patch("tools.framework.load_policy_catalogs", return_value=({}, baselines, [])),
            patch("tools.framework.load_requirement_catalogs", return_value=({}, {}, {}, [])),
        ):
            validate_project_declarations([item], inventory=Path("inventory"), assignments=Path("assignments"), resource_schema=Path("schema"), policy_sources=())

        item["digestAlgorithm"] = "compliance.example/framework-obligation-declaration-digest/v1alpha1"
        item["digest"] = declaration_digest(item)
        historical = account()
        historical["members"] = [{
            "subject_id": "host/a", "accounting_disposition": "result_required",
            "historical_interpretation": "validated", "result_id": "result-a", "plan_id": "plan-a",
        }]
        plans = [{
            "id": "plan-a",
            "resolved_baselines": [{
                "reference": "example.overlay@1", "digest": overlay_digest,
                "group": "scope-group",
                "lineage": [
                    {"reference": "example.base@1", "digest": base_digest},
                    {"reference": "example.overlay@1", "digest": overlay_digest},
                ],
            }],
            "controls": [{
                "instance_id": "example.check",
                "provenance": [{"baseline": "example.overlay@1", "group": "scope-group"}],
                "lineage": [
                    {"baseline": "example.base@1", "operation": "defined"},
                    {"baseline": "example.overlay@1", "operation": "annotate"},
                ],
            }],
        }]
        reports = [{"id": "result-a", "results": [{"instance_id": "example.check", "status": "pass"}]}]
        self.assertEqual(build_status(item, historical, plans, reports)["state"], "satisfied")


if __name__ == "__main__":
    unittest.main()
