"""Synthetic external collector: ordinary JSON construction, no Compliance imports."""
import argparse
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--id', required=True, help='caller-supplied Evidence identity')
parser.add_argument('--subject', required=True)
parser.add_argument('--collected-at', required=True)
parser.add_argument('--observation', required=True, type=Path)
args = parser.parse_args()

# A real collector would obtain this descriptive package inventory from its OS/API.
# Keep the entire observation, including unknown nested extension fields.
payload = json.loads(args.observation.read_text(encoding='utf-8'))
document = {
    'schema': 'compliance.example/evidence/v1',
    'id': args.id,
    'subject': {'id': args.subject, 'type': 'linux-host', 'source_ref': 'synthetic-host-1'},
    'type': 'linux.packages/v1',
    'collected_at': args.collected_at,
    'collector': {'id': 'external-package-example', 'version': '1', 'mode': 'synthetic'},
    'payload': payload,
    'capture': {'synthetic': True, 'note': 'Ordinary construction; extensions retained.'},
}
json.dump(document, sys.stdout, indent=2, ensure_ascii=False, allow_nan=False)
sys.stdout.write('\n')
