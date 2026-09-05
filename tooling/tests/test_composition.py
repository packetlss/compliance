"""Successor composition identity and fail-closed configuration contracts."""
import copy
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

import yaml

from tools._canonical_json import canonical_json_bytes
from tools.cli import main
from tools.composition import (
    COMPOSITION_LOCK_SCHEMA, POLICY_SOURCE_DIGEST_ALGORITHM, CompositionError,
    CompositionLock, composition_digest, composition_projection, load_composition_lock,
    observe_composition, require_composition, validate_composition,
)
from tools.policy_sources import PolicySource, source_tree_digest
from tools.project_config import CONFIG_SCHEMA_V1ALPHA3, ProjectConfigError, load_config, select_config
from tools.tooling_identity import actual_tooling_identity
from tools.tooling_source import TOOLING_SOURCE_DIGEST_ALGORITHM, tooling_source_digest

ROOT = Path(__file__).resolve().parents[1]


def content(value='a'):
    return {'digestAlgorithm': POLICY_SOURCE_DIGEST_ALGORITHM, 'digest': 'sha256:' + value * 64}


def identity():
    return {'source': {'digestAlgorithm': TOOLING_SOURCE_DIGEST_ALGORITHM, 'digest': 'sha256:' + 'b' * 64},
            'execution': {'kind': 'source'}}


def lock_document(actual):
    return {'schema': COMPOSITION_LOCK_SCHEMA, 'expected': {
        'tooling': actual['tooling'],
        'policySources': {item['name']: {'content': item['content']} for item in actual['policySources']},
    }}


class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = []
        for name in ('control-library', 'verification-policy'):
            path = self.root / name
            path.mkdir()
            (path / 'policy.yaml').write_text('test: synthetic\n')
            self.sources.append(PolicySource(name, path))
        self.sources = tuple(self.sources)
        self.config = self.root / 'compliance.yaml'
        self.document = {'schema': CONFIG_SCHEMA_V1ALPHA3,
                         'policySources': [{'name': s.name, 'path': str(s.path)} for s in self.sources],
                         'paths': {key: key for key in ('inventory', 'assignments', 'evidence', 'plan', 'results', 'waivers')}}
        self.write_config()

    def write_config(self):
        self.config.write_text(yaml.safe_dump(self.document))

    def test_fixed_jcs_and_digest_vectors(self):
        document = {'tooling': identity(), 'policySources': [{'name': 'control-library', 'content': content()}]}
        encoded = (b'{"policySources":[{"content":{"digest":"sha256:' + b'a'*64 +
                   b'","digestAlgorithm":"compliance.example/policy-source-tree-digest/v1alpha1"},"name":"control-library"}],'
                   b'"tooling":{"execution":{"kind":"source"},"source":{"digest":"sha256:' + b'b'*64 +
                   b'","digestAlgorithm":"compliance.example/tooling-source-tree-digest/v1alpha1"}}}')
        self.assertEqual(canonical_json_bytes(composition_projection(document)), encoded)
        self.assertEqual(composition_digest(document), 'sha256:380a06d5aa4458521c3ecf3e9795c8e10c64e0c6723e13d8ccfddc32a60a59db')
        lock = CompositionLock(self.root / 'ignored', document)
        lock_bytes = b'{"expected":' + encoded + b',"schema":"compliance.example/composition-lock/v1alpha1"}'
        self.assertEqual(canonical_json_bytes(lock.semantic_document()), lock_bytes)
        self.assertEqual(lock.digest(), 'sha256:df40bebe6494632910ef85a862edc5ad6e66b86db24667f18382837d96ceb298')

    def test_order_path_git_release_and_expectation_invariance_name_sensitivity(self):
        actual = observe_composition(self.sources)
        self.assertEqual(actual, observe_composition(tuple(reversed(self.sources))))
        moved = self.root / 'elsewhere' / '.git' / 'build' / 'policy'
        shutil.copytree(self.sources[0].path, moved)
        moved_sources = (PolicySource(self.sources[0].name, moved), self.sources[1])
        self.assertEqual(actual, observe_composition(moved_sources))
        decorated = copy.deepcopy(actual)
        decorated.update(repository='repo', path='/checkout', git='commit', provider='github', url='https://example.invalid', release='v1', expected='different')
        decorated['tooling']['metadata'] = {'version': '9', 'distribution': 'anything'}
        decorated['policySources'][0]['path'] = '/elsewhere'
        self.assertEqual(composition_digest(actual), composition_digest(decorated))
        decorated['policySources'][0]['name'] = 'environment-private'
        self.assertNotEqual(composition_digest(actual), composition_digest(decorated))

    def test_source_actual_is_recalculated_without_wheel(self):
        actual = actual_tooling_identity()
        self.assertEqual(actual['source']['digest'], tooling_source_digest(ROOT))
        self.assertEqual(actual['execution'], {'kind': 'source'})
        with patch('tools.tooling_identity.tooling_source_digest', side_effect=['sha256:'+'a'*64, 'sha256:'+'b'*64]):
            self.assertNotEqual(actual_tooling_identity(), actual_tooling_identity())

    def test_direct_and_complete_enforcement(self):
        actual = observe_composition(self.sources)
        lock = CompositionLock(self.root / 'lock', actual)
        direct = {s['name']: s['content'] for s in actual['policySources']}
        report = require_composition(self.sources, direct=direct, lock=lock)
        self.assertTrue(report['valid'])
        self.assertEqual(require_composition(self.sources)['compositionDigest'], report['compositionDigest'])
        direct['control-library'] = content('c')
        with self.assertRaisesRegex(CompositionError, 'direct.*mismatch.*disagree'):
            require_composition(self.sources, direct=direct, lock=lock)
        (self.sources[0].path / 'policy.yaml').write_text('changed: true\n')
        with self.assertRaisesRegex(CompositionError, 'composition-lock mismatch'):
            require_composition(self.sources, lock=lock)

    def test_complete_lock_all_mismatches(self):
        actual = observe_composition(self.sources)
        cases = []
        value = copy.deepcopy(actual); value['policySources'].pop(); cases.append(value)
        value = copy.deepcopy(actual); value['policySources'].append({'name': 'environment-private', 'content': content()}); cases.append(value)
        value = copy.deepcopy(actual); value['policySources'][0]['name'] = 'other'; cases.append(value)
        value = copy.deepcopy(actual); value['policySources'][0]['content'] = content(); cases.append(value)
        value = copy.deepcopy(actual); value['policySources'][0]['content']['digestAlgorithm'] = 'other'; cases.append(value)
        value = copy.deepcopy(actual); value['tooling']['source']['digest'] = 'sha256:'+'c'*64; cases.append(value)
        value = copy.deepcopy(actual); value['tooling']['execution'] = {'kind': 'installed-wheel', 'wheelSha256': 'sha256:'+'c'*64}; cases.append(value)
        for expected in cases:
            with self.subTest(expected=expected), self.assertRaises(CompositionError):
                require_composition(self.sources, lock=CompositionLock(self.root / 'lock', expected))
        wheel_actual = copy.deepcopy(actual)
        wheel_actual['tooling']['execution'] = {'kind': 'installed-wheel', 'wheelSha256': 'sha256:'+'c'*64}
        wheel_expected = copy.deepcopy(wheel_actual)
        wheel_expected['tooling']['execution']['wheelSha256'] = 'sha256:'+'d'*64
        with patch('tools.composition.observe_composition', return_value=wheel_actual):
            with self.assertRaisesRegex(CompositionError, 'composition-lock mismatch'):
                require_composition(self.sources, lock=CompositionLock(self.root / 'lock', wheel_expected))

    def test_actual_identity_missing_never_uses_expected(self):
        actual = observe_composition(self.sources)
        with patch('tools.composition.actual_tooling_identity', side_effect=ValueError('missing receipt')):
            with self.assertRaisesRegex(CompositionError, 'actual composition unavailable'):
                require_composition(self.sources, lock=CompositionLock(self.root / 'lock', actual))

    def test_lock_yaml_normalization_metadata_and_duplicate_refusal(self):
        path = self.root / 'compliance.lock.yaml'
        document = lock_document(observe_composition(self.sources))
        path.write_text(yaml.safe_dump(document))
        digest = load_composition_lock(path).digest()
        document['metadata'] = {'repository': 'elsewhere', 'version': '2', 'unicode': '\u20ac\U0001f600'}
        path.write_text(yaml.safe_dump(document, sort_keys=False))
        self.assertEqual(load_composition_lock(path).digest(), digest)
        path.write_text('schema: one\nschema: two\n')
        with self.assertRaisesRegex(CompositionError, 'duplicate YAML key'):
            load_composition_lock(path)

    def test_strict_config_and_duplicate_names(self):
        for key in ('policies', 'resourceSchema'):
            self.document['paths'][key] = 'forbidden'
            self.write_config()
            with self.assertRaises(ProjectConfigError): load_config(self.config)
            self.document['paths'].pop(key)
        for field in ('name', 'path'):
            previous = self.document['policySources'][0].pop(field)
            self.write_config()
            with self.assertRaises(ProjectConfigError): load_config(self.config)
            self.document['policySources'][0][field] = previous
        self.document['policySources'].append(self.document['policySources'][0])
        self.write_config()
        with self.assertRaisesRegex(ProjectConfigError, 'duplicate policy source'): load_config(self.config)
        with self.assertRaisesRegex(ValueError, 'duplicate policy source'):
            observe_composition((self.sources[0], self.sources[0]))

    def test_lock_selection_traversal_symlink_and_direct_guard(self):
        for path in ('../compliance.lock.yaml', '/tmp/compliance.lock.yaml', './compliance.lock.yaml', 'other.yaml'):
            self.document['expectedComposition'] = {'path': path}
            self.write_config()
            with self.assertRaises(ProjectConfigError): load_config(self.config)
        self.document['expectedComposition'] = {'path': 'compliance.lock.yaml'}
        self.write_config()
        lock = self.root / 'compliance.lock.yaml'
        external = self.root / 'external.yaml'
        external.write_text(yaml.safe_dump(lock_document(observe_composition(self.sources))))
        lock.symlink_to(external)
        with self.assertRaisesRegex(ProjectConfigError, 'adjacent'): load_config(self.config)
        lock.unlink(); lock.write_text(external.read_text())
        self.document['policySources'][0]['expectedContent'] = {'digestAlgorithm': POLICY_SOURCE_DIGEST_ALGORITHM, 'digest': source_tree_digest(self.sources[0].path)}
        self.write_config()
        select_config(['--config', str(self.config)])
        self.document['policySources'][0]['expectedContent'] = content()
        self.write_config()
        with self.assertRaisesRegex(ProjectConfigError, 'disagree'):
            select_config(['--config', str(self.config)])

    def test_override_refusal_including_equals(self):
        for flag in ('--policy-source', '--policies', '--resource-schema', '--policy-sour', '--resource-s'):
            for tail in ([flag, 'x'], [flag+'=x']):
                with self.assertRaisesRegex(ProjectConfigError, 'runtime contract overrides'):
                    select_config(['--config', str(self.config), *tail], validate_release=False)

    def test_cli_diagnostics_config_and_missing_inputs_no_writes(self):
        for command in (['composition', 'show', '--format', 'json'], ['composition', 'validate', '--format', 'json'], ['config', 'validate']):
            output = io.StringIO()
            with redirect_stdout(output): main(['--config', str(self.config), *command])
            self.assertIn('v1alpha', output.getvalue())
        for command in (['plan', 'render', 'host/test'], ['assessment', 'run', 'host/test']):
            with redirect_stderr(io.StringIO()) as errors, self.assertRaises(SystemExit):
                main(['--config', str(self.config), *command])
            self.assertIn('resource path does not exist', errors.getvalue())
            self.assertFalse((self.root / 'plan').exists())
            self.assertFalse((self.root / 'results').exists())
        self.document['policySources'][0]['expectedContent'] = content()
        self.write_config()
        with redirect_stdout(io.StringIO()) as output:
            main(['--config', str(self.config), 'composition', 'show', '--format', 'json'])
        self.assertFalse(json.loads(output.getvalue())['valid'])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            main(['--config', str(self.config), 'composition', 'validate'])
        self.assertEqual(caught.exception.code, 2)


if __name__ == '__main__': unittest.main()
