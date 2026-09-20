#!/usr/bin/env python3
"""External installed/no-Git exercise. Only public CLI calls and standard-library JSON."""
import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--compliance', required=True)
parser.add_argument('--policy-source', required=True)
parser.add_argument('--examples', required=True, type=Path)
parser.add_argument('--subject-example', required=True, type=Path)
args = parser.parse_args()


def cli(*arguments, raw=None, expected=0):
    result = subprocess.run([args.compliance, 'producer', *arguments], input=raw,
                            text=True, capture_output=True)
    assert result.returncode == expected, (arguments, result.stdout, result.stderr)
    if expected:
        assert not result.stdout and 'Traceback' not in result.stderr, result
        return result.stderr
    return json.loads(result.stdout)


assert not Path('.git').exists()
assert not Path('compliance.yaml').exists()
assert 'explicit --policy-source' in cli('list', expected=2)
source = ['--policy-source', args.policy_source]
contracts = cli('list', *source)['contracts']
contract = next(item for item in contracts if item['type'] == 'linux.packages/v1')
selection = ['--type', contract['type'], '--schema-id', contract['schema_id']]
schema = cli('schema', *source, *selection)
Path('package-schema.json').write_text(json.dumps(schema, indent=2) + '\n')
assert schema['properties']['type']['const'] == contract['type']
assert schema['$id'] == contract['schema_id']

# -S prevents site-packages access: this collector needs only Python's stdlib.
result = subprocess.run([
    sys.executable, '-I', '-S', str(args.examples / 'collect_packages.py'),
    '--id', 'evidence:external-example:001', '--subject', 'host/producer-example',
    '--collected-at', '2000-01-01T00:00:00Z',
    '--observation', str(args.examples / 'package-observation.json'),
], text=True, capture_output=True, check=True)
document = json.loads(result.stdout)
authored = json.loads((args.examples / 'linux-packages.json').read_text())
assert document == authored  # All envelope/nested extensions and caller ID survive.
assert document['payload'] == json.loads((args.examples / 'package-observation.json').read_text())
Path('evidence.json').write_text(result.stdout)
before = Path('evidence.json').read_bytes()
validated = cli('validate', *source, *selection, '--input', 'evidence.json')
assert validated == cli('validate', *source, *selection, '--input', '-', raw=result.stdout)
assert validated['document_valid'] is True and validated['validation_scope'] == 'document-only'
assert not {'status', 'outcome', 'fresh', 'selected', 'admissible'}.intersection(validated)
assert Path('evidence.json').read_bytes() == before

vectors = json.loads((args.examples / 'conformance.json').read_text())
for vector in vectors:
    candidate = copy.deepcopy(document)
    for change in vector['changes']:
        target = candidate
        for part in change['path'][:-1]:
            target = target[part]
        if change.get('remove'):
            del target[change['path'][-1]]
        else:
            target[change['path'][-1]] = change['value']
    cli('validate', *source, *selection, '--input', '-', raw=json.dumps(candidate),
        expected=0 if vector['valid'] else 2)

subject_contract = cli('list', '--kind', 'subject')['contracts'][0]
assert subject_contract['type'] == 'Subject'
subject_schema = cli('schema', '--kind', 'subject', '--schema-id', subject_contract['schema_id'])
Path('subject-schema.json').write_text(json.dumps(subject_schema, indent=2) + '\n')
subject_raw = args.subject_example.read_text()
subject = json.loads(subject_raw)
assert cli('validate', '--kind', 'subject', '--input', '-', raw=subject_raw)['document_valid']
assert cli('validate', '--kind', 'subject', '--input', str(args.subject_example))['document_valid']
subject['spec']['source']['observedAt'] = 'not-a-time'
cli('validate', '--kind', 'subject', '--input', '-', raw=json.dumps(subject), expected=2)
print(f'External producer: installed CLI, canonical schema export, stdlib-only collector, caller ID, '
      f'extensions, file/stdin, {len(vectors)} policy vectors, and Subject document check passed. '
      'The old observation is document-valid; no freshness, selection or policy outcome was asserted.')
