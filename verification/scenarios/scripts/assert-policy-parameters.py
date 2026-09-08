"""Canonical ADR 0012 cutover through public CLI and separated synthetic roots."""
import argparse
import copy
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

from tools import policy_parameters as p
from tools.artifact_validation import validate_assessment_plan
from tools.policy_diff import build_policy_diff
from tools.operation import plan_coverage


def run(root):
    with tempfile.TemporaryDirectory(prefix='parameter-conformance-') as temporary:
        work = Path(temporary)
        sources = {}
        for name, source in [('control-library', root/'policy-sources/control-library/policies'),
                             ('verification-policy', root/'policy-sources/verification-policy/policies'),
                             ('environment-private', root/'external-sources/environment-private')]:
            sources[name] = work/name
            shutil.copytree(source, sources[name])
        fixture = root/'verification/fixtures/iam-private-boundary'
        shutil.copytree(fixture/'assignments', work/'assignments')
        config = {'schema': 'compliance.example/project-config/v1alpha3',
                  'policySources': [{'name': name, 'path': str(path)} for name, path in sources.items()],
                  'paths': {'inventory': str(fixture/'inventory'), 'assignments': str(work/'assignments'),
                            'evidence': str(work/'evidence'), 'plan': str(work/'plans'), 'results': str(work/'results'), 'waivers': str(work/'waivers')}}
        config_path = work/'compliance.yaml'
        config_path.write_text(yaml.safe_dump(config))
        command = ['compliance', '--config', str(config_path)]

        def render(name):
            output = work/name
            subprocess.run([*command, 'plan', 'render', 'host/restricted-linux-01', '--output', str(output)], check=True, text=True)
            files = list(output.rglob('*.json'))
            assert len(files) == 1, files
            plan = json.loads(files[0].read_text())
            validate_assessment_plan(plan)
            return plan

        first = render('original')
        assert plan_coverage(first)['assessable']
        requirement = first['requirements'][0]
        slot = requirement['parameter_facts']['states']['privileged_evidence_max_age']
        assert slot['value'] == '86400s'
        realization_path = sources['environment-private']/'realizations/restricted/restricted-linux-role-based-access.json'
        realization_bytes = realization_path.read_bytes()
        baseline_record = first['resolved_requirement_baselines'][0]
        parent = baseline_record['parameter_derivation']['ancestry'][-1]['document']
        baseline_ref = baseline_record['reference']
        child_ref = parent['metadata']['id']+'@2'
        child = {'apiVersion': parent['apiVersion'], 'kind': parent['kind'],
                 'metadata': {'id': parent['metadata']['id'], 'revision': 2},
                 'spec': {'title': 'Restricted Linux enclave access policy',
                          'requirements': copy.deepcopy(parent['spec']['requirements']),
                          'extends': {'baseline': baseline_ref, 'digest': p.digest(parent)},
                          'parameter_operations': [{'id': 'enclave-freshness', 'op': 'tailor', 'target': slot['pin'],
                            'expected_parent_fingerprint': p.fingerprint(slot), 'from': '24h', 'to': '1h',
                            'deviation': {'id': 'SYNTHETIC-AGE', 'classification': 'specialization',
                                'rationale': 'Canonical explicit freshness change', 'approval_ref': 'synthetic/review', 'review_after': '2027-01-01'}}]}}
        child_path = sources['environment-private']/'requirement-baselines/enclave.json'
        child_path.parent.mkdir()
        child_path.write_text(json.dumps(child))
        assignment = next((work/'assignments').glob('*.yaml'))
        original_assignment = yaml.safe_load(assignment.read_text())
        selected = copy.deepcopy(original_assignment)
        selected['spec']['baselineRefs'] = [{'name': parent['metadata']['id'], 'revision': '2'}]
        assignment.write_text(yaml.safe_dump(selected))
        second = render('tailored')
        assert plan_coverage(second)['assessable']
        assert realization_path.read_bytes() == realization_bytes
        assert all(c['evidence'][0]['max_age'] == '3600s' for c in second['controls'])
        assert build_policy_diff(first, second)['summary']['changed']
        selected['spec']['baselineRefs'] = [{'name': parent['metadata']['id'], 'revision': revision} for revision in ['1', '2']]
        assignment.write_text(yaml.safe_dump(selected))
        assert not plan_coverage(render('conflict'))['assessable']
        print('ADR 0012: private tailoring, immutable fan-out, and assignment conflict passed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--integration-root', type=Path, required=True)
    run(parser.parse_args().integration_root)
