#!/usr/bin/env python3
"""Installed/no-Git successor proof, executed by the package gate's isolated Python."""
from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import tempfile
from importlib import metadata
from pathlib import Path
from unittest.mock import patch

import yaml

from tools.cli import main
from tools.composition import COMPOSITION_LOCK_SCHEMA
from tools.project_config import CONFIG_SCHEMA_V1ALPHA3, composition_validation, load_config
from tools.tooling_identity import (
    RECEIPT_FILENAME, WHEEL_FILENAME, ToolingIdentityError, actual_tooling_identity,
)


def refuse_mutation(path: Path, replacement: bytes | None) -> None:
    original = path.read_bytes()
    try:
        if replacement is None:
            path.unlink()
        else:
            path.write_bytes(replacement)
        try:
            actual_tooling_identity()
        except ToolingIdentityError:
            pass
        else:
            raise AssertionError(f"tampered installed provenance accepted: {path.name}")
    finally:
        path.write_bytes(original)


def main_proof() -> None:
    dist = metadata.distribution('compliance-tooling')
    info = next(Path(dist.locate_file(item)).parent for item in dist.files
                if str(item).endswith('.dist-info/METADATA'))
    wheel = info / WHEEL_FILENAME
    expected_wheel = 'sha256:' + hashlib.sha256(wheel.read_bytes()).hexdigest()
    # Runtime must not invoke Git, providers, subprocesses, or network access.
    with (patch.object(subprocess, 'run', side_effect=AssertionError('runtime subprocess')),
         patch.object(socket, 'create_connection', side_effect=AssertionError('runtime network'))):
        actual = actual_tooling_identity()
        assert actual['execution'] == {'kind': 'installed-wheel', 'wheelSha256': expected_wheel}
        for name in (RECEIPT_FILENAME, WHEEL_FILENAME, 'RECORD'):
            path = info / name
            refuse_mutation(path, None)
            refuse_mutation(path, b'invalid')
        receipt = json.loads((info / RECEIPT_FILENAME).read_text())
        for key, value in (('wheelSha256', 'sha256:'+'0'*64), ('distribution', 'different'), ('version', '99')):
            changed = dict(receipt, **{key: value})
            refuse_mutation(info / RECEIPT_FILENAME, json.dumps(changed).encode())
        for name in ('tools/cli.py', 'tools/release-metadata.json', 'schemas/inventory/resource.schema.json'):
            path = Path(dist.locate_file(name))
            refuse_mutation(path, path.read_bytes()+b'\n# tampered\n')
            refuse_mutation(path, None)
        unrecorded = Path(dist.locate_file('tools/unrecorded.py'))
        try:
            unrecorded.write_text('x = 1\n')
            try:
                actual_tooling_identity()
            except ToolingIdentityError:
                pass
            else:
                raise AssertionError('unrecorded module accepted')
        finally:
            unrecorded.unlink()
        with tempfile.TemporaryDirectory(prefix='composition-no-git-') as temporary:
            root = Path(temporary)
            policy = root / 'policy'
            policy.mkdir()
            (policy / 'synthetic.yaml').write_text('test: true\n')
            config_path = root / 'compliance.yaml'
            config = {'schema': CONFIG_SCHEMA_V1ALPHA3,
                      'policySources': [{'name': 'control-library', 'path': str(policy)}],
                      'paths': {key: key for key in ('inventory', 'assignments', 'evidence', 'plan', 'results', 'waivers')}}
            config_path.write_text(yaml.safe_dump(config))
            report = composition_validation(load_config(config_path))
            assert report['valid']
            lock = {'schema': COMPOSITION_LOCK_SCHEMA, 'expected': {
                'tooling': report['actual']['tooling'],
                'policySources': {item['name']: {'content': item['content']} for item in report['actual']['policySources']},
            }}
            lock_path = root / 'compliance.lock.yaml'
            lock_path.write_text(yaml.safe_dump(lock))
            config['expectedComposition'] = {'path': 'compliance.lock.yaml'}
            config_path.write_text(yaml.safe_dump(config))
            assert composition_validation(load_config(config_path), require=True)['valid']
            main(['--config', str(config_path), 'composition', 'validate'])
            lock['expected']['tooling']['execution']['wheelSha256'] = 'sha256:'+'0'*64
            lock_path.write_text(yaml.safe_dump(lock))
            assert not composition_validation(load_config(config_path))['valid']
            lock['expected']['tooling']['execution'] = {'kind': 'source'}
            lock_path.write_text(yaml.safe_dump(lock))
            assert not composition_validation(load_config(config_path))['valid']
    print('Installed successor composition: receipt, wheel, RECORD, no-Git/network, and mismatch proofs passed.')


if __name__ == '__main__':
    main_proof()
