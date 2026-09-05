"""Retired discriminators fail at ordinary config/artifact/CLI boundaries."""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from tools.artifact_validation import validate_assessment_plan, validate_assessment_results
from tools.assessment import load_result_reports
from tools.cli import main
from tools.compliance import _run_plan_show
from tools.composition import load_composition_lock
from tools.evaluate_plan import evaluate_plan_document, write_json
from tools.policy_diff import load_policy_plan_set
from tools.project_config import load_config, ProjectConfig
from test_evaluate_plan import EvidenceFreshnessTests
from argparse import Namespace


class PredecessorRetirementTests(unittest.TestCase):
    def test_retired_configs_and_release_lock_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'compliance.yaml'
            for revision in ('v1alpha1', 'v1alpha2'):
                with self.subTest(revision=revision):
                    path.write_text(json.dumps({'schema': f'compliance.example/project-config/{revision}'}))
                    with self.assertRaisesRegex(ValueError, 'unsupported configuration schema'):
                        load_config(path)
            path = Path(directory) / 'compliance.lock.yaml'
            path.write_text(json.dumps({'schema': 'compliance.example/release-lock/v1alpha2'}))
            with self.assertRaises(ValueError):
                load_composition_lock(path)

    def test_retired_assessments_are_never_loaded_evaluated_or_written(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, native = EvidenceFreshnessTests().evidence_plan(root)
            # A valid successor payload with an old discriminator must still refuse.
            for revision in ('v1', 'v3'):
                for family, validator in (('assessment-plan', validate_assessment_plan),
                                          ('assessment-results', validate_assessment_results)):
                    with self.subTest(revision=revision, family=family):
                        document = copy.deepcopy(native) if family == 'assessment-plan' else {}
                        document['schema'] = f'compliance.example/{family}/{revision}'
                        path = root / 'artifact.json'
                        path.write_text(json.dumps(document))
                        with self.assertRaises(ValueError): validator(document)
                        output = root / 'output.json'
                        with self.assertRaises(ValueError): write_json(document, output)
                        self.assertFalse(output.exists())
                        if family == 'assessment-plan':
                            with self.assertRaises(ValueError):
                                evaluate_plan_document(document, root, ())
                            with self.assertRaises(ValueError): load_policy_plan_set(root)
                            with self.assertRaises(ValueError):
                                _run_plan_show(Namespace(plan=root, project_config=ProjectConfig(), format='json'))
                        else:
                            with self.assertRaises(ValueError): load_result_reports(path)
                            with self.assertRaises(ValueError): load_result_reports(root)

    def test_release_dispatch_is_removed_without_alias(self):
        for operation in ('show', 'validate'):
            with self.subTest(operation=operation), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    main(['--no-config', 'release', operation])
                self.assertEqual(error.exception.code, 2)
