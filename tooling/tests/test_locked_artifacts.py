from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.artifact_provenance import ContentArtifactProvenance
from tools.artifact_validation import validate_assessment_plan
from tools.locked_artifacts import (
    ASSESSMENT_PLAN_V3,
    ASSESSMENT_RESULTS_V3,
    evaluate_plan_v3,
    render_plan_v3,
    validate_assessment_plan_any,
    validate_assessment_results_any,
)
from tools.policy_diff import build_policy_diff
from tools.render_plan import content_digest
from tools.tooling_source import TOOLING_SOURCE_DIGEST_ALGORITHM


class LockedArtifactTests(unittest.TestCase):
    def _v3_provenance(
        self,
        *,
        lock: str = "a",
        source: str = "1",
        wheel: str = "2",
        version: str = "0.3.0",
    ):
        return ContentArtifactProvenance(
            distribution="compliance-tooling",
            version=version,
            source_digest="sha256:" + source * 64,
            source_digest_algorithm=TOOLING_SOURCE_DIGEST_ALGORITHM,
            artifact_sha256="sha256:" + wheel * 64,
            release_lock_digest="sha256:" + lock * 64,
        )

    def _v1_plan(self):
        plan = {
            "schema": "compliance.example/assessment-plan/v1",
            "policy_revision": "sha256:" + "1" * 64,
            "policy_sources": [{
                "name": "unit-test",
                "digest": "sha256:" + "2" * 64,
            }],
            "inventory_revision": "sha256:" + "3" * 64,
            "assignment_revision": "sha256:" + "4" * 64,
            "subject": {
                "schema": "compliance.example/inventory-subject/v1",
                "id": "host/example",
                "type": "linux-host",
                "status": "active",
                "labels": {},
                "inventory": {
                    "source": "unit-test",
                    "external_id": "example",
                    "observed_at": "2026-08-29T00:00:00Z",
                },
            },
            "resolved_groups": [],
            "assignments": [],
            "resolved_baselines": [],
            "resolved_requirement_baselines": [],
            "requirements": [],
            "controls": [],
            "excluded_controls": [],
            "coverage": {
                "status": "unassigned",
                "assessable": False,
                "reason": "no-policy-assignment",
                "assignment_count": 0,
                "active_control_count": 0,
                "excluded_control_count": 0,
                "requirement_count": 0,
            },
            "resolution": {"status": "valid", "errors": []},
        }
        plan["id"] = content_digest(plan)
        validate_assessment_plan(plan)
        return plan

    def _v3_plan(self, provenance=None):
        base = self._v1_plan()
        return render_plan_v3(lambda: copy.deepcopy(base), provenance or self._v3_provenance())

    def _fake_evaluate(self, projected, *_args, **_kwargs):
        return {
            "schema": "compliance.example/assessment-results/v1",
            "assessment_id": (
                "assessment:"
                + projected["id"].removeprefix("sha256:")[:16]
                + ":2026-08-29T00:00:00Z"
            ),
            "evaluated_at": "2026-08-29T00:00:00Z",
            "plan_id": projected["id"],
            "policy_revision": projected["policy_revision"],
            "inventory_revision": projected["inventory_revision"],
            "assignment_revision": projected["assignment_revision"],
            "subject_id": projected["subject"]["id"],
            "summary": {
                "pass": 0, "fail": 0, "unknown": 0,
                "not_applicable": 0, "error": 0, "waived": 0,
            },
            "requirement_summary": {
                "pass": 0, "fail": 0, "unknown": 0,
                "not_applicable": 0, "error": 0, "waived": 0,
            },
            "requirement_baseline_summary": {
                "pass": 0, "fail": 0, "unknown": 0,
                "not_applicable": 0, "error": 0, "waived": 0,
            },
            "results": [],
            "requirement_assessments": [],
            "requirement_baseline_assessments": [],
        }

    def _fake_opa(self, root: Path, marker: str = "a") -> Path:
        path = root / f"opa-{marker}"
        path.write_text(
            "#!/usr/bin/env sh\n"
            "if [ \"${1:-}\" = version ]; then\n"
            "  printf 'Version: 1.18.2\\n'\n"
            "  exit 0\n"
            "fi\n"
            "printf '{}\\n'\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    def test_v3_content_provenance_participates_in_plan_content_id(self):
        first = self._v3_plan(self._v3_provenance())
        same = self._v3_plan(self._v3_provenance())
        different_lock = self._v3_plan(self._v3_provenance(lock="b"))
        different_source = self._v3_plan(self._v3_provenance(source="c"))
        different_wheel = self._v3_plan(self._v3_provenance(wheel="d"))

        self.assertEqual(first["schema"], ASSESSMENT_PLAN_V3)
        self.assertEqual(first["generator"]["source_digest_algorithm"], TOOLING_SOURCE_DIGEST_ALGORITHM)
        self.assertEqual(first["id"], same["id"])
        self.assertNotEqual(first["id"], different_lock["id"])
        self.assertNotEqual(first["id"], different_source["id"])
        self.assertNotEqual(first["id"], different_wheel["id"])

    def test_locked_validation_keeps_closed_v1_contract_and_rejects_historical_v2(self):
        plan = self._v3_plan()
        validate_assessment_plan_any(plan)
        missing = copy.deepcopy(plan)
        missing.pop("generator")
        with self.assertRaises(ValueError):
            validate_assessment_plan_any(missing)
        wrong = self._v3_plan()
        wrong["schema"] = "compliance.example/assessment-plan/v2"
        wrong["id"] = content_digest({key: value for key, value in wrong.items() if key != "id"})
        with self.assertRaisesRegex(ValueError, "unsupported assessment plan schema"):
            validate_assessment_plan_any(wrong)

    def test_provenance_only_plan_churn_is_context_not_effective_policy(self):
        before = self._v3_plan(self._v3_provenance(lock="a"))
        after = self._v3_plan(self._v3_provenance(lock="b"))
        with patch("tools.policy_diff.validate_assessment_plan", validate_assessment_plan_any):
            diff = build_policy_diff(before, after)
        self.assertFalse(diff["summary"]["changed"], diff)
        self.assertTrue(diff["context"]["changed"], diff)
        self.assertIn("plan_id", diff["context"]["changed_fields"])

    def test_v3_results_bind_exact_evaluator_and_evidence_snapshot(self):
        provenance = self._v3_provenance()
        plan = self._v3_plan(provenance)
        evidence = {
            "schema": "compliance.example/evidence/v1",
            "id": "evidence:unit-test",
            "subject": {"id": "host/example", "type": "linux-host"},
            "type": "unit-test/v1",
            "collected_at": "2026-08-30T00:00:00Z",
            "collector": {"id": "unit-test", "version": "1.0.0"},
            "payload": {"value": 1},
            "integrity": {"digest": "sha256:" + "a" * 64},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "evidence.json").write_text(
                json.dumps(evidence, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            opa = self._fake_opa(root)
            called: dict[str, str] = {}

            def fake_evaluate(projected, evidence_path, *_args, **kwargs):
                called["opa"] = kwargs["opa"]
                called["evidence_path"] = str(evidence_path)
                self.assertNotEqual(Path(evidence_path).resolve(), root.resolve())
                loaded = json.loads((Path(evidence_path) / "evidence.json").read_text(encoding="utf-8"))
                self.assertEqual(loaded, evidence)
                return self._fake_evaluate(projected)

            results = evaluate_plan_v3(
                fake_evaluate,
                provenance,
                plan,
                root,
                (),
                opa=str(opa),
            )
            self.assertEqual(Path(called["opa"]), opa.resolve())

        self.assertEqual(results["schema"], ASSESSMENT_RESULTS_V3)
        self.assertEqual(results["evaluator"]["name"], "opa")
        self.assertEqual(results["evaluator"]["version"], "1.18.2")
        self.assertTrue(results["evaluator"]["executableSha256"].startswith("sha256:"))
        self.assertEqual(
            results["evidence"]["documentDigestAlgorithm"],
            "compliance.example/evidence-document-digest/v1alpha1",
        )
        self.assertEqual(
            results["evidence"]["setDigestAlgorithm"],
            "compliance.example/evidence-set-digest/v1alpha1",
        )
        self.assertEqual(results["evidence"]["documents"][0]["id"], evidence["id"])
        self.assertTrue(results["evidence"]["documents"][0]["digest"].startswith("sha256:"))
        validate_assessment_results_any(results)

    def test_removed_configuration_artifact_schemas_are_unsupported(self):
        for schema in (
            "compliance.example/configuration-plan/v1",
            "compliance.example/configuration-plan/v3",
            "compliance.example/configuration-render-result/v1",
            "compliance.example/configuration-render-result/v3",
            "compliance.example/configuration-explanation/v1",
            "compliance.example/configuration-explanation/v3",
        ):
            with self.subTest(schema=schema):
                with self.assertRaisesRegex(
                    ValueError,
                    "unsupported assessment plan schema",
                ):
                    validate_assessment_plan_any({"schema": schema})


if __name__ == "__main__":
    unittest.main()
