"""Standalone producer behavior, using synthetic schema contracts."""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from contract_fixtures import evidence_schema
from tools.cli import main
from tools.evidence_provenance import evidence_document_digest


class ProducerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'policy'
        self.schema_path = self.source / 'schemas/evidence/arbitrary-filename.json'
        self.schema_path.parent.mkdir(parents=True)
        self.schema = evidence_schema('test.observation/v1', 'test-subject')
        self.schema['properties']['payload'] = {
            'type': 'object', 'required': ['count'], 'additionalProperties': True,
            'properties': {'count': {'type': 'integer', 'minimum': 0}},
        }
        self.write_schema()
        self.document = {
            'schema': 'compliance.example/evidence/v1', 'id': 'caller-assigned-id',
            'type': 'test.observation/v1', 'subject': {'id': 'test/one', 'type': 'test-subject'},
            'collected_at': '2000-01-01T00:00:00Z',
            'collector': {'id': 'test-collector', 'version': '1'}, 'payload': {'count': 3},
        }

    def write_schema(self):
        self.schema_path.write_text(json.dumps(self.schema))

    def cli(self, *args, raw='', exit_code=0):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), patch('sys.stdin', io.StringIO(raw)):
            try:
                main(['producer', *args])
            except SystemExit as error:
                self.assertEqual(error.code, exit_code, err.getvalue())
            else:
                self.assertEqual(exit_code, 0, out.getvalue())
        if exit_code:
            self.assertEqual(out.getvalue(), '')
            self.assertNotIn('Traceback', err.getvalue())
            return err.getvalue()
        return json.loads(out.getvalue())

    def source_args(self):
        return ['--policy-source', f'test={self.source}']

    def validate(self, document=None, **kwargs):
        return self.cli('validate', *self.source_args(), '--type', 'test.observation/v1',
                        '--input', '-', raw=json.dumps(document if document is not None else self.document), **kwargs)

    def test_discovery_exact_export_and_file_stdin_without_config(self):
        with patch('tools.compliance.select_config', side_effect=AssertionError('no config')):
            listed = self.cli('list', *self.source_args())
            self.assertEqual(listed['contracts'], [{'type': 'test.observation/v1', 'schema_id': self.schema['$id']}])
            self.assertEqual(self.cli('schema', *self.source_args(), '--type', 'test.observation/v1',
                                     '--schema-id', self.schema['$id']), self.schema)
            result = self.validate()
            self.assertEqual(result, {'document_valid': True, 'validation_scope': 'document-only',
                                     'kind': 'evidence', 'type': 'test.observation/v1', 'schema_id': self.schema['$id']})
            path = self.root / 'document.json'
            path.write_text(json.dumps(self.document))
            before = path.read_bytes()
            self.assertEqual(self.cli('validate', *self.source_args(), '--type', 'test.observation/v1',
                                      '--input', str(path)), result)
            self.assertEqual(path.read_bytes(), before)

    def test_opaque_reference_annotations_survive_discovery_export_and_validation(self):
        for keyword in ('$ref', '$dynamicRef'):
            for value in ('https://example.invalid/annotation', 123):
                with self.subTest(keyword=keyword, value=value):
                    opaque = {keyword: value}
                    self.schema['_annotation'] = opaque
                    payload = self.schema['properties']['payload']
                    payload['default'] = opaque
                    payload['examples'] = [opaque]
                    payload['properties']['$ref'] = {'const': opaque, 'enum': [opaque]}
                    payload['_annotation'] = [opaque]
                    self.write_schema()
                    self.assertEqual(self.cli('list', *self.source_args())['contracts'][0]['type'],
                                     'test.observation/v1')
                    self.assertEqual(self.cli('schema', *self.source_args(),
                                             '--type', 'test.observation/v1'), self.schema)
                    self.assertTrue(self.validate()['document_valid'])

    def test_real_references_are_checked_in_nested_subschema_locations(self):
        original = copy.deepcopy(self.schema)
        locations = (
            lambda ref: {'allOf': [ref]},
            lambda ref: {'properties': {'optional': ref}},
            lambda ref: {'$defs': {'unused': ref}},
            lambda ref: {'items': ref},
            lambda ref: {'prefixItems': [ref]},
            lambda ref: {'additionalProperties': ref},
            lambda ref: {'dependentSchemas': {'count': ref}},
            lambda ref: {'if': {'properties': {'count': ref}}},
        )
        for keyword in ('$ref', '$dynamicRef'):
            for target in ('https://example.invalid/schema', '#/$defs/missing'):
                for location in locations:
                    with self.subTest(keyword=keyword, target=target, location=location):
                        self.schema = copy.deepcopy(original)
                        self.schema['properties']['payload'].update(location({keyword: target}))
                        self.write_schema()
                        self.cli('list', *self.source_args(), exit_code=2)
        self.schema = original
        self.schema['properties']['payload'].update({
            '$id': 'https://example.invalid/local-payload',
            '$defs': {'count': {'type': 'integer'}},
            'properties': {'count': {'$ref': '#/$defs/count'}},
        })
        self.write_schema()
        self.assertTrue(self.validate()['document_valid'])

    def test_reference_targets_are_schemas_only_when_explicitly_referenced(self):
        self.schema['_annotation'] = {'$ref': 'https://example.invalid/annotation'}
        self.schema['properties']['payload']['allOf'] = [{'$ref': '#/_annotation'}]
        self.write_schema()
        self.assertIn('unresolvable external', self.cli('list', *self.source_args(), exit_code=2))
        self.schema['_annotation'] = {'$ref': '#/missing'}
        self.write_schema()
        self.cli('list', *self.source_args(), exit_code=2)
        # A recursive schema is legal; preflight must terminate without evaluating it.
        self.schema['_annotation'] = {'$ref': '#/_annotation'}
        self.write_schema()
        self.assertEqual(self.cli('schema', *self.source_args(), '--type',
                                 'test.observation/v1'), self.schema)

    def test_extensions_are_preserved_and_identity_bearing(self):
        doc = copy.deepcopy(self.document)
        for target in (doc, doc['subject'], doc['collector'], doc['payload']):
            target['_extra'] = {'unicode': 'Å', 'ordered': [3, 1], 'nullable': None}
        serialized = json.dumps(doc, ensure_ascii=False)
        self.validate(doc)
        self.assertEqual(json.loads(serialized), doc)
        self.assertEqual(evidence_document_digest(json.loads(serialized)), evidence_document_digest(doc))
        self.assertNotEqual(evidence_document_digest(doc), evidence_document_digest(self.document))

    def test_exact_coalescing_and_divergence_in_both_source_orders(self):
        path = self.root / 'other/schemas/evidence/different-filename.json'
        path.parent.mkdir(parents=True)
        self.schema['_annotation'] = {'$ref': 'https://example.invalid/annotation'}
        self.write_schema()
        path.write_text(json.dumps(self.schema))
        permutations = ([f'a={self.source}', f'b={self.root / "other"}'],
                        [f'b={self.root / "other"}', f'a={self.source}'])
        for sources in permutations:
            args = [item for source in sources for item in ('--policy-source', source)]
            self.assertEqual(self.cli('schema', *args, '--type', 'test.observation/v1'), self.schema)
        changed = copy.deepcopy(self.schema)
        changed['_annotation']['$ref'] = 123
        path.write_text(json.dumps(changed))
        for sources in permutations:
            args = [item for source in sources for item in ('--policy-source', source)]
            self.assertIn('policy-resource-conflict', self.cli('list', *args, exit_code=2))

    def test_unknown_type_schema_and_unavailable_policy_fail_closed(self):
        self.assertIn('explicit --policy-source', self.cli('list', exit_code=2))
        self.assertIn('unknown Evidence type', self.cli('schema', *self.source_args(), '--type', 'unknown/v1', exit_code=2))
        self.assertIn('--type is required', self.cli('schema', *self.source_args(), exit_code=2))
        self.assertIn('schema ID does not match', self.cli('schema', *self.source_args(), '--type', 'test.observation/v1',
                                                         '--schema-id', 'https://invalid.example/schema', exit_code=2))
        self.assertIn('accessible directory', self.cli('list', *self.source_args(), '--policy-source',
                                                     f'absent={self.root / "absent"}', exit_code=2))

    def test_envelope_payload_timestamp_and_type_failures(self):
        for field, value in [('schema', 'wrong'), ('type', 'unknown/v1'), ('id', ''),
                             ('subject', {'id': 'test/one', 'type': 'wrong'}),
                             ('collected_at', 'yesterday'), ('collected_at', '2026-01-01T00:00:00'),
                             ('collector', {'id': 'test'}), ('payload', {'count': '3'})]:
            with self.subTest(field=field, value=value):
                doc = copy.deepcopy(self.document)
                doc[field] = value
                self.assertIn('document invalid', self.validate(doc, exit_code=2))
        doc = copy.deepcopy(self.document)
        del doc['id']
        self.assertIn('document invalid', self.validate(doc, exit_code=2))

    def test_malformed_nonobject_and_unsupported_representation(self):
        invalid = ['{', '[]', 'null', '{"id":1,"id":2}']
        for extra in (float('nan'), float('inf'), 9007199254740992, '\ud800'):
            invalid.append(json.dumps({**self.document, 'extension': extra}))
        for raw in invalid:
            with self.subTest(raw=repr(raw)):
                self.cli('validate', *self.source_args(), '--type', 'test.observation/v1',
                         '--input', '-', raw=raw, exit_code=2)

    def test_invalid_catalog_and_offline_references_even_for_list(self):
        for mutation in (
            lambda s: s.update(type=42), lambda s: s.update(additionalProperties=False),
            lambda s: s.update(**{'$id': 'https://wrong.example/wrong'}),
            lambda s: s.update(**{'$ref': '#/missing'}),
            lambda s: s.update(**{'$ref': 'https://example.invalid/remote'}),
            lambda s: s.update(ignored=float('nan')),
        ):
            original = copy.deepcopy(self.schema)
            mutation(self.schema)
            self.write_schema()
            self.cli('list', *self.source_args(), exit_code=2)
            self.schema = original
        self.schema_path.write_text('{"type":"object","type":"object"}')
        self.cli('list', *self.source_args(), exit_code=2)

    def test_subject_check_is_small_and_separate(self):
        contracts = self.cli('list', '--kind', 'subject')['contracts']
        self.assertEqual(len(contracts), 1)
        schema = self.cli('schema', '--kind', 'subject', '--schema-id', contracts[0]['schema_id'])
        self.assertIn('subject', schema['$defs'])
        subject = {'apiVersion': 'compliance.example/v1alpha1', 'kind': 'Subject',
                   'metadata': {'name': 'example'}, 'spec': {'id': 'host/example', 'type': 'linux-host',
                   'lifecycle': 'active', 'source': {'name': 'synthetic', 'externalId': 'one',
                   'observedAt': '2000-01-01T00:00:00Z'}, 'attributes': {'rich': ['preserved']}}}
        self.assertTrue(self.cli('validate', '--kind', 'subject', '--input', '-', raw=json.dumps(subject))['document_valid'])
        subject['kind'] = 'InventoryGroup'
        self.assertIn('expected one normalized Subject', self.cli('validate', '--kind', 'subject', '--input', '-', raw=json.dumps(subject), exit_code=2))
        subject['kind'] = 'Subject'
        subject['spec']['source']['observedAt'] = 'invalid'
        self.cli('validate', '--kind', 'subject', '--input', '-', raw=json.dumps(subject), exit_code=2)
        self.cli('list', '--kind', 'subject', *self.source_args(), exit_code=2)
