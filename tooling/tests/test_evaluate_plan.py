import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.evaluate_plan import (
    evaluate_control,
    evaluate_plan_document,
)
from tools.policy_sources import PolicySource, policy_source_revisions
from assessment_fixture import (
    assessment_plan,
    control_result,
    evidence_document,
    evidence_plan,
    waiver_resource,
)


class EvidenceFreshnessTests(unittest.TestCase):
    def setUp(self):
        from tools.evaluator import EvaluatorIdentity
        identity = patch('tools.evaluator.resolve_opa_evaluator', return_value=(EvaluatorIdentity('opa', '1.18.2', 'sha256:'+'e'*64), 'opa'))
        identity.start()
        self.addCleanup(identity.stop)

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

    def test_process_and_non_json_failures_have_closed_safe_classification(self):
        cases = (
            (
                SimpleNamespace(
                    returncode=1, stdout='private stdout', stderr='private stderr'
                ),
                'criterion_execution_failed',
            ),
            (
                SimpleNamespace(
                    returncode=0, stdout='private non-json', stderr=''
                ),
                'criterion_decision_invalid',
            ),
        )
        for process, expected_code in cases:
            with self.subTest(code=expected_code), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source, plan = evidence_plan(root)
                evidence_path = root / 'evidence'
                evidence_path.mkdir()
                (evidence_path / 'valid.json').write_text(
                    json.dumps(evidence_document()), encoding='utf-8'
                )
                with patch('tools.evaluate_plan.subprocess.run', return_value=process):
                    report = evaluate_plan_document(
                        plan, evidence_path, (source,),
                        evaluated_at=datetime(2026, 8, 23, 12, tzinfo=UTC),
                    )
            result, = report['results']
            self.assertEqual(result['evaluation_error']['code'], expected_code)
            serialized = json.dumps(report)
            self.assertNotIn('private stdout', serialized)
            self.assertNotIn('private stderr', serialized)
            self.assertNotIn('private non-json', serialized)


    def test_valid_typed_evidence_reaches_opa_with_extensions_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, plan = evidence_plan(root)
            evidence_path = root / "evidence"
            evidence_path.mkdir()
            document = evidence_document()
            document["payload"]["extension"] = {"richer": True}
            document["collector"]["build"] = "test-build"
            (evidence_path / "test.json").write_text(
                json.dumps(document),
                encoding="utf-8",
            )

            with patch(
                "tools.evaluate_plan.evaluate_control",
                return_value=control_result(plan, "pass"),
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
            source, plan = evidence_plan(root)
            evidence_path = root / "evidence"
            evidence_path.mkdir()
            document = evidence_document(value=7)
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
        disposition, = report["dependency_dispositions"]
        self.assertEqual(disposition["disposition"], "invalid")
        errors = disposition["diagnostics"]
        self.assertEqual(
            {error["schema_path"] for error in errors},
            {
                "/properties/collected_at/format",
                "/properties/payload/properties/value/type",
            },
        )
        self.assertTrue(all(error["code"] == "evidence_schema_invalid" for error in errors))
        self.assertEqual(report["outcome"], "unknown")

    def test_invalid_evidence_for_another_subject_is_not_evaluated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, plan = evidence_plan(root)
            evidence_path = root / "evidence"
            evidence_path.mkdir()
            document = evidence_document(subject_id="host/other", value=7)
            (evidence_path / "other.json").write_text(
                json.dumps(document),
                encoding="utf-8",
            )

            with patch(
                "tools.evaluate_plan.evaluate_control",
                return_value=control_result(plan, "unknown"),
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
                    source, plan = evidence_plan(root)
                    evidence_path = root / "evidence"
                    evidence_path.mkdir()
                    (evidence_path / "broken.json").write_text(
                        content,
                        encoding="utf-8",
                    )

                    with self.assertRaisesRegex(ValueError, message):
                        evaluate_plan_document(plan, evidence_path, (source,))

    def test_active_waiver_preserves_failure_and_reports_waived(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = PolicySource("shared", root / "policy")
            source.path.mkdir()
            (source.path / "release.json").write_text("{}", encoding="utf-8")
            waiver_path = root / "waivers"
            waiver_path.mkdir()
            (waiver_path / "test.yaml").write_text(
                waiver_resource(),
                encoding="utf-8",
            )
            plan = assessment_plan(
                policy_source_revisions((source,)),
                with_requirement=True,
            )
            plan_id = plan["id"]
            with patch(
                "tools.evaluate_plan.evaluate_control",
                return_value=control_result(plan, "fail"),
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
                waiver_resource(),
                encoding="utf-8",
            )
            plan = assessment_plan(policy_source_revisions((source,)))
            with patch(
                "tools.evaluate_plan.evaluate_control",
                return_value=control_result(plan, "fail"),
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
                waiver_resource(),
                encoding="utf-8",
            )
            plan = assessment_plan(policy_source_revisions((source,)))
            with patch(
                "tools.evaluate_plan.evaluate_control",
                return_value=control_result(plan, "pass"),
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
