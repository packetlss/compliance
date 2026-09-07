import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from tools.evaluate_plan import (
    evaluate_control,
    evaluate_plan_document,
)
from tools.policy_sources import PolicySource, policy_source_revisions
from tools.assessment_provenance import artifact_digest
from assessment_fixture import planning_fields, freeze_policy_inputs


def assessment_plan(policy_sources, *, with_requirement=False):
    requirement_digest = "sha256:" + "5" * 64
    baseline_digest = "sha256:" + "6" * 64
    plan = {
        "subject": {
            "schema": "compliance.example/inventory-subject/v1",
            "id": "host/test",
            "type": "linux-host",
            "status": "active",
            "labels": {},
            "inventory": {
                "source": "unit-test",
                "external_id": "host/test",
                "observed_at": "2026-08-28T12:00:00Z",
            },
        },
        "resolved_groups": [{
            "id": "test-hosts",
            "sources": [{"membership": "explicit", "source": "group.members"}],
        }],
        "assignments": [{
            "id": "test-policy",
            "group": "test-hosts",
            "baselines": ["test.baseline@1"],
        }],
        "resolved_baselines": [],
        "resolved_requirement_baselines": [],
        "requirements": [],
        "controls": [{
            "instance_id": "test.check",
            "implementation": "test.control",
            "entrypoint": "data.test.evaluate",
            "parameters": {},
            "severity": "medium",
            "remediation": "",
            "evidence": [],
            "disposition": "evaluate",
            "alignment": "unaltered",
            "definition_fingerprint": "sha256:" + "4" * 64,
            "derivations": [],
            "deviations": [],
            "lineage": [{"baseline": "test.baseline@1", "operation": "defined"}],
            "provenance": [{
                "group": "test-hosts",
                "assignment": "test-policy",
                "baseline": "test.baseline@1",
            }],
            "implementation_sources": [{
                "policy_source": policy_sources[0]["name"],
                "path": "controls/test/control.json",
            }],
        }],
        "excluded_controls": [],
        "resolution": {"status": "valid", "errors": []},
    }
    if with_requirement:
        locator = [{
            "policy_source": policy_sources[0]["name"],
            "path": "requirements/test.json",
        }]
        plan["requirements"] = [{
            "reference": "test.requirement@1",
            "digest": requirement_digest,
            "title": "Test requirement",
            "statement": "The test condition is satisfied.",
            "external_refs": [],
            "policy_sources": locator,
            "required": True,
            "adoption": {
                "status": "implemented",
                "method": "automated",
                "owner": "test",
                "implementation_ref": "test/implementation",
            },
            "satisfaction": {"allOf": ["test.check"]},
            "technical_instance_ids": ["test.check"],
            "realization": {
                "reference": "test.realization@1",
                "digest": "sha256:" + "8" * 64,
                "classification": "internal",
                "policy_sources": [{
                    "policy_source": policy_sources[0]["name"],
                    "path": "realizations/test.json",
                }],
            },
            "provenance": [{
                "group": "test-hosts",
                "assignment": "test-policy",
                "baseline": "test.baseline@1",
            }],
        }]
        plan["resolved_requirement_baselines"] = [{
            "assignment": "test-policy",
            "group": "test-hosts",
            "baseline": "test.baseline@1",
            "reference": "test.baseline@1",
            "digest": baseline_digest,
            "policy_sources": [{
                "policy_source": policy_sources[0]["name"],
                "path": "requirement-baselines/test.json",
            }],
            "requirements": [{
                "requirement": "test.requirement@1",
                "digest": requirement_digest,
                "required": True,
            }],
        }]
    plan.update(planning_fields(policy_sources))
    freeze_policy_inputs(plan)
    plan["id"] = artifact_digest(plan)
    return plan


class EvidenceFreshnessTests(unittest.TestCase):
    def setUp(self):
        from tools.evaluator import EvaluatorIdentity
        identity = patch('tools.evaluator.resolve_opa_evaluator', return_value=(EvaluatorIdentity('opa', '1.18.2', 'sha256:'+'e'*64), 'opa'))
        identity.start()
        self.addCleanup(identity.stop)

    @staticmethod
    def evidence_schema() -> dict:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": [
                "schema", "id", "subject", "type", "collected_at",
                "collector", "payload",
            ],
            "additionalProperties": True,
            "properties": {
                "schema": {"const": "compliance.example/evidence/v1"},
                "id": {"type": "string", "minLength": 1},
                "subject": {
                    "type": "object",
                    "required": ["id", "type"],
                    "additionalProperties": True,
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "type": {"const": "linux-host"},
                    },
                },
                "type": {"const": "test.evidence/v1"},
                "collected_at": {"type": "string", "format": "date-time"},
                "collector": {
                    "type": "object",
                    "required": ["id", "version"],
                    "additionalProperties": True,
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "version": {"type": "string", "minLength": 1},
                    },
                },
                "payload": {
                    "type": "object",
                    "required": ["value"],
                    "additionalProperties": True,
                    "properties": {"value": {"type": "string"}},
                },
            },
        }

    @staticmethod
    def evidence_document(*, subject_id="host/test", value="observed") -> dict:
        return {
            "schema": "compliance.example/evidence/v1",
            "id": "evidence:test",
            "subject": {"id": subject_id, "type": "linux-host"},
            "type": "test.evidence/v1",
            "collected_at": "2026-08-23T11:00:00Z",
            "collector": {"id": "test-collector", "version": "1"},
            "payload": {"value": value},
        }

    def evidence_plan(self, root: Path):
        source = PolicySource("shared", root / "policy")
        schemas = source.path / "schemas/evidence"
        schemas.mkdir(parents=True)
        (schemas / "test-evidence-v1.schema.json").write_text(
            json.dumps(self.evidence_schema()),
            encoding="utf-8",
        )
        plan = assessment_plan(policy_source_revisions((source,)))
        plan["controls"][0]["evidence"] = [{
            "type": "test.evidence/v1",
            "max_age": "24h",
        }]
        plan.pop("id")
        freeze_policy_inputs(plan)
        plan["id"] = artifact_digest(plan)
        return source, plan

    @staticmethod
    def waiver_resource() -> str:
        return """\
apiVersion: compliance.example/v1alpha1
kind: Waiver
metadata:
  name: test-control-rollout
spec:
  subjectRef:
    id: host/test
  controlRef:
    instanceId: test.check
  validFrom: "2026-08-01T00:00:00Z"
  expiresAt: "2026-09-01T00:00:00Z"
  rationale: Temporary rollout constraint.
  owner: test-owner
  approval:
    reference: risk/TEST-1
    approvedBy: risk-owner
    approvedAt: "2026-07-31T00:00:00Z"
"""

    @staticmethod
    def control_result(plan, status):
        return {
            "control_id": "test.control",
            "instance_id": "test.check",
            "subject_id": "host/test",
            "plan_id": plan["id"],
            "status": status,
            "severity": "medium",
            "reason": "Synthetic control result.",
            "expected": {},
            "observed": {},
            "remediation": "",
            "external_refs": [],
            "alignment": "unaltered",
        }

    @patch("tools.evaluate_plan.subprocess.run")
    def test_evaluation_refuses_old_new_source_names_with_identical_bytes(self, run):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = root / "policy"
            policy.mkdir()
            (policy / "marker.json").write_text("{}", encoding="utf-8")
            for expected, actual in (
                ("shared-library", "control-library"),
                ("control-library", "shared-library"),
            ):
                with self.subTest(expected=expected, actual=actual):
                    plan = assessment_plan(policy_source_revisions(PolicySource(expected, policy)))
                    with self.assertRaisesRegex(ValueError, "evaluation policy composition differs"):
                        evaluate_plan_document(plan, root, (PolicySource(actual, policy),))
            run.assert_not_called()

    def test_evaluation_rejects_policy_sources_changed_since_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = PolicySource("shared", root / "policy")
            source.path.mkdir()
            marker = source.path / "release.json"
            marker.write_text("{}", encoding="utf-8")
            plan = assessment_plan(policy_source_revisions((source,)))
            marker.write_text('{"changed":true}', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "evaluation policy composition differs"):
                evaluate_plan_document(plan, root, (source,))

    @patch("tools.evaluate_plan.subprocess.run")
    def test_opa_receives_control_modules_from_every_policy_source(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = '{"status":"pass"}'
        run.return_value.stderr = ""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "shared/controls").mkdir(parents=True)
            (root / "private/controls").mkdir(parents=True)
            (root / "shared/controls/shared.rego").write_text(
                "package shared\n\nresult := true\n",
                encoding="utf-8",
            )
            (root / "private/controls/private.rego").write_text(
                "package private\n\nresult := true\n",
                encoding="utf-8",
            )
            evaluate_control(
                "opa",
                (
                    PolicySource("shared", root / "shared"),
                    PolicySource("private", root / "private"),
                ),
                {
                    "control": {"implementation": "test", "instance_id": "test.one"},
                    "subject": {"id": "host/test"},
                    "assessment": {"plan_id": "sha256:plan"},
                    "evidence": [],
                },
                "data.test.evaluate",
            )

        command = run.call_args.args[0]
        self.assertEqual(command.count("--data"), 2)
        self.assertIn(str((root / "shared/controls/shared.rego").resolve()), command)
        self.assertIn(str((root / "private/controls/private.rego").resolve()), command)


    def test_valid_typed_evidence_reaches_opa_with_extensions_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, plan = self.evidence_plan(root)
            evidence_path = root / "evidence"
            evidence_path.mkdir()
            document = self.evidence_document()
            document["payload"]["extension"] = {"richer": True}
            document["collector"]["build"] = "test-build"
            (evidence_path / "test.json").write_text(
                json.dumps(document),
                encoding="utf-8",
            )

            with patch(
                "tools.evaluate_plan.evaluate_control",
                return_value=self.control_result(plan, "pass"),
            ) as evaluate:
                evaluate_plan_document(
                    plan,
                    evidence_path,
                    (source,),
                    evaluated_at=datetime(2026, 8, 23, 12, tzinfo=UTC),
                )

        supplied = evaluate.call_args.args[2]["evidence"]
        self.assertEqual(len(supplied), 1)
        self.assertEqual(supplied[0]["payload"]["extension"], {"richer": True})
        self.assertEqual(supplied[0]["collector"]["build"], "test-build")

    def test_invalid_required_evidence_is_unknown_without_opa(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, plan = self.evidence_plan(root)
            evidence_path = root / "evidence"
            evidence_path.mkdir()
            document = self.evidence_document(value=7)
            document["collected_at"] = "not-rfc3339"
            (evidence_path / "invalid.json").write_text(
                json.dumps(document),
                encoding="utf-8",
            )

            with patch("tools.evaluate_plan.evaluate_control") as evaluate:
                report = evaluate_plan_document(
                    plan,
                    evidence_path,
                    (source,),
                    evaluated_at=datetime(2026, 8, 23, 12, tzinfo=UTC),
                )

        evaluate.assert_not_called()
        result = report["results"][0]
        self.assertEqual(result["status"], "unknown")
        self.assertNotIn("evidence_ids", result)
        self.assertIn("rejected as invalid", result["reason"])
        errors = result["observed"]["evidence_validation_errors"]
        self.assertEqual(
            {error["path"] for error in errors},
            {"/collected_at", "/payload/value"},
        )
        self.assertTrue(all(
            error["evidence_type"] == "test.evidence/v1" for error in errors
        ))
        self.assertEqual(report["outcome"], "unknown")

    def test_invalid_evidence_for_another_subject_is_not_evaluated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, plan = self.evidence_plan(root)
            evidence_path = root / "evidence"
            evidence_path.mkdir()
            document = self.evidence_document(subject_id="host/other", value=7)
            (evidence_path / "other.json").write_text(
                json.dumps(document),
                encoding="utf-8",
            )

            with patch(
                "tools.evaluate_plan.evaluate_control",
                return_value=self.control_result(plan, "unknown"),
            ) as evaluate:
                report = evaluate_plan_document(
                    plan,
                    evidence_path,
                    (source,),
                    evaluated_at=datetime(2026, 8, 23, 12, tzinfo=UTC),
                )

        self.assertEqual(report["results"][0]["status"], "unknown")
        evaluate.assert_not_called()

    def test_unroutable_evidence_refuses_the_assessment(self):
        cases = (
            ("{", "Expecting property name"),
            ("[]", "evidence document must be an object"),
        )
        for content, message in cases:
            with self.subTest(message=message):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    source, plan = self.evidence_plan(root)
                    evidence_path = root / "evidence"
                    evidence_path.mkdir()
                    (evidence_path / "broken.json").write_text(
                        content,
                        encoding="utf-8",
                    )

                    with self.assertRaisesRegex(ValueError, message):
                        evaluate_plan_document(plan, evidence_path, (source,))

    def test_evaluation_persists_objective_and_top_baseline_rollups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = PolicySource("shared", root / "policy")
            source.path.mkdir()
            (source.path / "release.json").write_text("{}", encoding="utf-8")
            plan = assessment_plan(
                policy_source_revisions((source,)),
                with_requirement=True,
            )
            control_result = {
                "control_id": "test.control",
                "instance_id": "test.check",
                "subject_id": "host/test",
                "plan_id": plan["id"],
                "status": "pass",
                "severity": "medium",
                "reason": "Test condition passed.",
                "expected": {},
                "observed": {},
                "remediation": "",
                "external_refs": [],
                "alignment": "unaltered",
            }
            with patch(
                "tools.evaluate_plan.evaluate_control",
                return_value=control_result,
            ):
                report = evaluate_plan_document(
                    plan,
                    root,
                    (source,),
                    evaluated_at=datetime(2026, 8, 23, 12, tzinfo=UTC),
                )

        self.assertEqual(report["outcome"], "pass")
        self.assertEqual(report["requirement_assessments"][0]["status"], "pass")
        self.assertEqual(report["requirement_baseline_assessments"][0]["status"], "pass")

    def test_active_waiver_preserves_failure_and_reports_waived(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = PolicySource("shared", root / "policy")
            source.path.mkdir()
            (source.path / "release.json").write_text("{}", encoding="utf-8")
            waiver_path = root / "waivers"
            waiver_path.mkdir()
            (waiver_path / "test.yaml").write_text(
                self.waiver_resource(),
                encoding="utf-8",
            )
            plan = assessment_plan(
                policy_source_revisions((source,)),
                with_requirement=True,
            )
            plan_id = plan["id"]
            with patch(
                "tools.evaluate_plan.evaluate_control",
                return_value=self.control_result(plan, "fail"),
            ) as evaluate:
                report = evaluate_plan_document(
                    plan,
                    root,
                    (source,),
                    evaluated_at=datetime(2026, 8, 15, tzinfo=UTC),
                    waiver_path=waiver_path,
                )
            self.assertIsNone(evaluate.call_args.args[2]["waiver"])
            self.assertNotIn(
                "waiver_revision",
                evaluate.call_args.args[2]["assessment"],
            )

        result = report["results"][0]
        self.assertEqual(plan["id"], plan_id)
        self.assertEqual(result["status"], "waived")
        self.assertEqual(result["waiver"]["underlying_status"], "fail")
        self.assertEqual(result["reason"], "Synthetic control result.")
        self.assertEqual(report["outcome"], "waived")
        self.assertNotIn("waiver_revision", report)
        self.assertNotIn("waiver_revision", result)

    def test_expired_waiver_does_not_change_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = PolicySource("shared", root / "policy")
            source.path.mkdir()
            (source.path / "release.json").write_text("{}", encoding="utf-8")
            waiver_path = root / "waivers"
            waiver_path.mkdir()
            (waiver_path / "test.yaml").write_text(
                self.waiver_resource(),
                encoding="utf-8",
            )
            plan = assessment_plan(policy_source_revisions((source,)))
            with patch(
                "tools.evaluate_plan.evaluate_control",
                return_value=self.control_result(plan, "fail"),
            ):
                report = evaluate_plan_document(
                    plan,
                    root,
                    (source,),
                    evaluated_at=datetime(2026, 9, 1, tzinfo=UTC),
                    waiver_path=waiver_path,
                )

        self.assertEqual(report["results"][0]["status"], "fail")
        self.assertNotIn("waiver", report["results"][0])

    def test_active_waiver_does_not_change_a_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = PolicySource("shared", root / "policy")
            source.path.mkdir()
            (source.path / "release.json").write_text("{}", encoding="utf-8")
            waiver_path = root / "waivers"
            waiver_path.mkdir()
            (waiver_path / "test.yaml").write_text(
                self.waiver_resource(),
                encoding="utf-8",
            )
            plan = assessment_plan(policy_source_revisions((source,)))
            with patch(
                "tools.evaluate_plan.evaluate_control",
                return_value=self.control_result(plan, "pass"),
            ):
                report = evaluate_plan_document(
                    plan,
                    root,
                    (source,),
                    evaluated_at=datetime(2026, 8, 15, tzinfo=UTC),
                    waiver_path=waiver_path,
                )

        self.assertEqual(report["results"][0]["status"], "pass")
        self.assertNotIn("waiver", report["results"][0])


if __name__ == "__main__":
    unittest.main()
