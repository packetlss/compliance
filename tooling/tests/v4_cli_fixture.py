"""Synthetic public CLI v4 proof shared by source tests and installed/no-Git gate."""
import io
import json
import runpy
import tempfile
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from tools.cli import main
from tools.composition import COMPOSITION_LOCK_SCHEMA
from tools.project_config import composition_validation, load_config
from tools.artifact_validation import validate_assessment_plan, validate_assessment_results


def prove_v4_cli():
    build = runpy.run_path(str(Path(__file__).with_name('contract_fixtures.py')))['build_fixture']
    with tempfile.TemporaryDirectory(prefix='assessment-v4-cli-') as directory:
        root = Path(directory)
        build(root)
        project = root/'linux'
        path = project/'compliance.yaml'
        config = json.loads(path.read_text())
        config['schema'] = 'compliance.example/project-config/v1alpha3'
        config['paths'].pop('resourceSchema')
        path.write_text(json.dumps(config))
        # A complete criterion decision with attribution copied from its input.
        (root/'shared/controls/test/policy.rego').write_text('''package test.contract
import rego.v1
evaluate := {
  "control_id": input.control.implementation,
  "instance_id": input.control.instance_id,
  "subject_id": input.subject.id,
  "plan_id": input.assessment.plan_id,
  "inventory_revision": input.assessment.inventory_revision,
  "assignment_revision": input.assessment.assignment_revision,
  "policy_revision": input.assessment.policy_revision,
  "status": "pass", "reason": "Synthetic observation accepted",
  "severity": input.control.severity, "remediation": input.control.remediation,
  "expected": {}, "observed": {}, "evidence_ids": [],
  "external_refs": [], "alignment": input.control.alignment,
}
''')
        evidence = project/'generated/evidence'
        evidence.mkdir(parents=True)
        doc = {'id':'test:observation','type':'test.linux-host/v1',
               'subject':{'id':'host/configuration-linux-01','type':'linux-host'},
               'collected_at':'2026-08-23T11:00:00Z','payload':{'value':True}}
        (evidence/'observation.json').write_text(json.dumps(doc))
        def run(*command):
            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(io.StringIO()): main(['--config',str(path),*command])
            return output.getvalue()
        run('assessment','run','host/configuration-linux-01','--at','2026-08-23T12:00:00Z')
        plan_path, = (project/'generated/plans').rglob('*.json')
        result_path, = (project/'generated/results').rglob('*.json')
        plan = json.loads(plan_path.read_text()); report = json.loads(result_path.read_text())
        validate_assessment_plan(plan); validate_assessment_results(report)
        assert plan['schema'].endswith('/v4') and report['schema'].endswith('/v4')
        assert report['summary']['pass'] == len(plan['controls']) > 0, report
        assert len(report['provenance']['selectedEvidence']) == len(plan['controls'])
        assert all(not item['evidence_ids'] for item in report['results'])  # orchestration, not OPA IDs
        assert json.loads(run('plan','show','host/configuration-linux-01','--format','json'))['id'] == plan['id']
        run('assessment','explain','host/configuration-linux-01','--format','json')
        actual = composition_validation(load_config(path))['actual']
        lock = {'schema':COMPOSITION_LOCK_SCHEMA, 'expected':{
            'tooling':actual['tooling'], 'policySources':{item['name']:{'content':item['content']} for item in actual['policySources']}}}
        (project/'compliance.lock.yaml').write_text(json.dumps(lock))
        config['expectedComposition'] = {'path':'compliance.lock.yaml'}
        for source in config['policySources']:
            source['expectedContent'] = next(item['content'] for item in actual['policySources'] if item['name']==source['name'])
        path.write_text(json.dumps(config))
        run('assessment','run','host/configuration-linux-01','--at','2026-08-23T12:00:00Z')
        assert json.loads(plan_path.read_text())['id'] == plan['id']
        assert json.loads(result_path.read_text())['id'] == report['id']
        # Canonical documents with distinct complete metadata select none.
        (evidence/'second.json').write_text(json.dumps({**doc,'extension':True}))
        run('assessment','run','host/configuration-linux-01','--at','2026-08-23T12:00:00Z')
        ambiguous = json.loads(result_path.read_text())
        assert ambiguous['summary']['unknown'] == len(plan['controls'])
        assert ambiguous['provenance']['selectedEvidence'] == []
        assert 'evidence_selection_ambiguity' in run('assessment','explain','host/configuration-linux-01')
        before = result_path.read_bytes()
        (evidence/'second.json').write_text('{not JSON')
        try:
            run('assessment','run','host/configuration-linux-01','--at','2026-08-23T12:00:00Z')
        except SystemExit:
            pass
        else:
            raise AssertionError('unsafe evidence did not refuse')
        assert result_path.read_bytes() == before
        return report['provenance']['evaluationComposition']['actual']['tooling']['execution']['kind']
