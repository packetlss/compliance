"""Canonical ParameterPolicy tailoring through public CLI and private roots."""
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
from tools.operation import plan_disposition


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

        tailored = render('tailored')
        assert plan_disposition(tailored) == 'result_required'
        states, _, _ = p.reconstruct_frozen_parameters(tailored)
        slot = states['company.iam.role-based-access@1']['privileged_evidence_max_age']
        assert slot['value'] == '3600s'
        realization_path = sources['environment-private']/'realizations/restricted/restricted-linux-role-based-access.json'
        realization_bytes = realization_path.read_bytes()
        assert any(
            item['reference'] == 'restricted.iam.role-based-access@1'
            and {source['policy_source'] for source in item['policy_sources']} == {
                'environment-private'
            }
            for item in tailored['parameters']['documents']
        )
        assignment = next((work/'assignments').glob('*.yaml'))
        original_assignment = yaml.safe_load(assignment.read_text())
        base_selected = copy.deepcopy(original_assignment)
        base_selected['spec']['parameterPolicyRefs'] = [{
            'name': 'company.iam.role-based-access-defaults', 'revision': '1',
        }]
        assignment.write_text(yaml.safe_dump(base_selected))
        base = render('base')
        assert plan_disposition(base) == 'result_required'
        assert realization_path.read_bytes() == realization_bytes
        assert all(c['evidence'][0]['max_age'] == '86400s' for c in base['controls'])
        assert build_policy_diff(base, tailored)['summary']['changed']
        conflict = copy.deepcopy(original_assignment)
        conflict['spec']['parameterPolicyRefs'].append({
            'name': 'company.iam.role-based-access-defaults', 'revision': '1',
        })
        assignment.write_text(yaml.safe_dump(conflict))
        assert plan_disposition(render('conflict')) == 'invalid'
        print('ADR 0024: private ParameterPolicy tailoring, immutable fan-out, and assignment conflict passed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--integration-root', type=Path, required=True)
    run(parser.parse_args().integration_root)
