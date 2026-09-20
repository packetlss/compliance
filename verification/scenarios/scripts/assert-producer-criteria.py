#!/usr/bin/env python3
"""Separate evaluator-side reuse proof; this is not assessment admission."""
import argparse
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--policy', required=True, type=Path)
parser.add_argument('--evidence', required=True, type=Path)
args = parser.parse_args()
raw = args.evidence.read_bytes()
document = json.loads(raw)
for criterion, parameters, expected in (
    ('packages_required', {'required': [{'id': 'auditd'}]}, 'pass'),
    ('packages_required', {'required': [{'id': 'sssd'}]}, 'fail'),
    ('packages_only_allowed', {'allowed': ['auditd', 'curl']}, 'pass'),
    ('packages_only_allowed', {'allowed': ['auditd']}, 'fail'),
):
    inputs = {'evidence': [document], 'control': {'parameters': {'ecosystem': 'linux-native', **parameters}}}
    output = json.loads(subprocess.check_output([
        'opa', 'eval', '--format', 'json', '--stdin-input', '--data', str(args.policy / 'controls'),
        f'data.compliance.controls.linux.{criterion}.outcome',
    ], input=json.dumps(inputs), text=True))
    outcome = output['result'][0]['expressions'][0]['value']
    assert outcome['status'] == expected, outcome
assert args.evidence.read_bytes() == raw
print('Separate criterion reuse: unchanged package observation supports required and only-allowed '
      'criteria with differing desired policy (pass/fail each). Direct Rego evaluation does not '
      'establish freshness or assessment admissibility.')
