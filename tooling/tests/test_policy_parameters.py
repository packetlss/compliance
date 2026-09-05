"""ADR 0012 positive and refusal vectors for direct typed policy parameters."""
import copy
import unittest

from jsonschema import ValidationError

from tools import policy_parameters as p


class PolicyParameterTests(unittest.TestCase):
    def setUp(self):
        schema = {'$id': 'https://example.test/age', 'type': 'string', 'pattern': '^[1-9][0-9]*[smhd]$', 'default': '30d'}
        self.requirement = {'metadata': {'id': 'objective', 'revision': 1}, 'spec': {'parameters': {
            'age': {'required': True, 'binding_mode': 'open', 'schema': schema, 'schema_digest': p.digest(schema),
                    'binding_scope': ['company', 'enclave'], 'representation': 'duration'}}}}
        self.pin = {'requirement': 'objective@1', 'digest': p.digest(self.requirement), 'required': True}
        self.initial = p.declarations(self.requirement)['age']
        self.baseline = {'metadata': {'id': 'company', 'revision': 1}, 'spec': {
            'requirements': [self.pin], 'parameter_operations': [self.operation('bind', self.initial, to='30d')]}}
        self.requirements = {'objective@1': self.requirement}
        self.catalog = {'company@1': self.baseline}
        self.definition = {'metadata': {'id': 'test.check', 'version': 1}, 'spec': {
            'evidence': [{'id': 'observation', 'type': 'test/v1', 'required': True,
                          'inputs_schema': {'$id': 'https://example.test/evidence-input', 'type': 'object',
                                            'properties': {'period': {'type': 'string'}}, 'required': ['period'], 'additionalProperties': False}}]},
            '_parameters_schema': {'type': 'object', 'properties': {'age': {'type': 'string'}}, 'required': ['age'], 'additionalProperties': False}}
        self.controls = {'test.check': self.definition}
        self.realization = {'spec': {'adoption': {'status': 'implemented'},
                                    'checks': [{'instance_id': 'check', 'implementation': 'test.check', 'parameters': {}}],
                                    'satisfaction': {'allOf': ['check']}, 'parameter_links': []}}
        for kind, path in [('parameters', '/age'), ('evidence_inputs', '/period'), ('freshness', '/max_age')]:
            target = {'instance_id': 'check', 'implementation': p.implementation_pin(self.definition), 'kind': kind, 'path': path}
            if kind != 'parameters': target['dependency'] = 'observation'
            self.realization['spec']['parameter_links'].append({'id': kind, 'source': self.initial['pin'], 'destination': target})

    def operation(self, op, state, **values):
        return {'id': op + '-age', 'op': op, 'target': copy.deepcopy(state['pin']),
                'expected_parent_fingerprint': p.fingerprint(state), **values}

    def states(self, reference='company@1'):
        states, _ = p.resolve(reference, self.catalog, self.requirements)
        p.complete(states)
        return states['objective@1']

    def derive(self, value='15d'):
        state = self.states()['age']
        op = self.operation('tailor', state, **{'from': '30d', 'to': value, 'deviation': {
            'id': 'DEV-1', 'classification': 'specialization', 'rationale': 'Synthetic enclave intent',
            'approval_ref': 'provenance-only', 'review_after': '2027-01-01'}})
        child = {'metadata': {'id': 'enclave', 'revision': 1}, 'spec': {'requirements': [self.pin],
                 'extends': {'baseline': 'company@1', 'digest': p.digest(self.baseline)}, 'parameter_operations': [op]}}
        self.catalog['enclave@1'] = child
        return child

    def test_default_does_not_bind_selected_policy(self):
        self.baseline['spec']['parameter_operations'] = []
        with self.assertRaisesRegex(p.ParameterResolutionError, 'unresolved'): self.states()
        self.assertFalse(p.declarations(self.requirement)['age']['bound'])

    def test_binding_and_tailoring_fan_out_without_realization_edits(self):
        original = copy.deepcopy(self.realization)
        first, _ = p.consume(self.realization, self.states(), self.controls)
        self.derive()
        second, records = p.consume(self.realization, self.states('enclave@1'), self.controls)
        self.assertEqual(original, self.realization)
        self.assertEqual(first[0]['parameters']['age'], '2592000s')
        self.assertEqual(second[0]['parameters']['age'], '1296000s')
        self.assertEqual(second[0]['evidence']['observation'], {'inputs': {'period': '1296000s'}, 'max_age': '1296000s'})
        self.assertEqual([record['value'] for record in records], ['1296000s'] * 3)

    def test_fixed_duration_vectors(self):
        for value in ['1d', '24h', '1440m', '86400s']: self.assertEqual(p.duration(value), '86400s')
        for value in ['1.5h', 'P1D', '1M', '0s', 3600, True, '${AGE}', '30d / 2']:
            with self.subTest(value=value), self.assertRaises(p.ParameterResolutionError): p.duration(value)

    def test_stale_pins_from_values_and_missing_deviation_fail(self):
        child = self.derive()
        cases = [lambda d: d['spec']['extends'].update(digest='sha256:'+'0'*64),
                 lambda d: d['spec']['parameter_operations'][0]['target'].update(schema_digest='sha256:'+'0'*64),
                 lambda d: d['spec']['parameter_operations'][0]['target'].update(declaration_digest='sha256:'+'0'*64),
                 lambda d: d['spec']['parameter_operations'][0].update(expected_parent_fingerprint='sha256:'+'0'*64),
                 lambda d: d['spec']['parameter_operations'][0].update({'from': '29d'}),
                 lambda d: d['spec']['parameter_operations'][0].pop('deviation')]
        for mutate in cases:
            self.catalog['enclave@1'] = copy.deepcopy(child)
            mutate(self.catalog['enclave@1'])
            with self.assertRaises(p.ParameterResolutionError): self.states('enclave@1')

    def test_open_binding_cannot_replace_inherited_value(self):
        child = self.derive()
        child['spec']['parameter_operations'][0]['op'] = 'bind'
        with self.assertRaisesRegex(p.ParameterResolutionError, 'replace'): self.states('enclave@1')

    def test_fixed_external_value_and_structural_scope(self):
        fixed = copy.deepcopy(self.requirement)
        fixed['spec']['parameters']['age'].update(binding_mode='fixed', value='30d')
        state = p.declarations(fixed)['age']
        self.assertTrue(state['sealed'])
        self.assertEqual(state['value'], '2592000s')
        self.baseline['metadata']['id'] = 'outsider'
        with self.assertRaisesRegex(p.ParameterResolutionError, 'scope'): self.states()

    def test_seal_is_retained_in_descendants(self):
        child = self.derive()
        state = self.states('enclave@1')['age']
        grandchild = {'metadata': {'id': 'enclave', 'revision': 2}, 'spec': {
            'requirements': [self.pin], 'extends': {'baseline': 'enclave@1', 'digest': p.digest(child)},
            'parameter_operations': [self.operation('seal', state)]}}
        self.catalog['enclave@2'] = grandchild
        sealed = self.states('enclave@2')['age']
        self.assertTrue(sealed['sealed'])
        self.catalog['enclave@3'] = {'metadata': {'id': 'enclave', 'revision': 3}, 'spec': {
            'requirements': [self.pin], 'extends': {'baseline': 'enclave@2', 'digest': p.digest(grandchild)},
            'parameter_operations': [self.operation('bind', sealed, to='1d')]}}
        with self.assertRaisesRegex(p.ParameterResolutionError, 'sealed'): self.states('enclave@3')

    def test_missing_edges_and_literal_imitation_fail(self):
        for mutate in [lambda r: r['spec'].update(parameter_links=[]),
                       lambda r: r['spec']['checks'][0]['parameters'].update(age='2592000s'),
                       lambda r: r['spec']['parameter_links'][0]['destination'].update(path='/nonexistent')]:
            realization = copy.deepcopy(self.realization)
            mutate(realization)
            with self.assertRaises(p.ParameterResolutionError): p.consume(realization, self.states(), self.controls)

    def test_post_substitution_identity_does_not_authorize_stale_input(self):
        changed = copy.deepcopy(self.controls)
        changed['test.check']['metadata']['version'] = 2
        with self.assertRaisesRegex(p.ParameterResolutionError, 'post-substitution'):
            p.consume(self.realization, self.states(), changed)

    def test_duplicate_operations_and_destinations_fail(self):
        self.baseline['spec']['parameter_operations'] *= 2
        with self.assertRaisesRegex(p.ParameterResolutionError, 'duplicate'): self.states()
        self.baseline['spec']['parameter_operations'] = self.baseline['spec']['parameter_operations'][:1]
        duplicate = copy.deepcopy(self.realization['spec']['parameter_links'][0]); duplicate['id'] = 'duplicate'
        self.realization['spec']['parameter_links'].append(duplicate)
        with self.assertRaisesRegex(p.ParameterResolutionError, 'ambiguous'): p.consume(self.realization, self.states(), self.controls)

    def test_atomic_json_and_adopted_constraints(self):
        for value, schema in [([1, 2], {'type': 'array', 'items': {'type': 'integer'}}),
                              ({'a': 1}, {'type': 'object', 'required': ['a'], 'properties': {'a': {'type': 'integer'}}})]:
            declaration = {'schema': {'$id': 'https://example.test/atomic', **schema}}
            self.assertEqual(p.value_for(declaration, value), value)
        company = {'schema': {'$id': 'https://example.test/company', 'type': 'integer'}}
        self.assertEqual(p.value_for(company, 45), 45)  # External <=30 is not an adopted constraint.
        company['schema']['maximum'] = 30
        with self.assertRaises(ValidationError): p.value_for(company, 45)

    def test_link_order_is_nonsemantic(self):
        expected = p.consume(self.realization, self.states(), self.controls)
        self.realization['spec']['parameter_links'].reverse()
        self.assertEqual(p.consume(self.realization, self.states(), self.controls), expected)

    def test_control_cannot_supply_implicit_freshness(self):
        instance = {'evidence': {}, 'parameters': {}}
        with self.assertRaisesRegex(p.ParameterResolutionError, 'explicit policy freshness'):
            p.evidence_for(instance, self.definition)

    def test_nested_symbolic_input_validates_after_materialization(self):
        from jsonschema import Draft202012Validator
        schema = {'type': 'object', 'properties': {'settings': {'type': 'object',
                  'properties': {'age': {'type': 'string'}}, 'required': ['age']}}, 'required': ['settings']}
        self.definition['_parameters_schema'] = schema
        self.realization['spec']['checks'][0]['parameters'] = {'settings': {}}
        for link in self.realization['spec']['parameter_links']:
            link['destination']['implementation'] = p.implementation_pin(self.definition)
            if link['destination']['kind'] == 'parameters': link['destination']['path'] = '/settings/age'
        partial = p.partial_parameter_schema(schema, ['/settings/age'])
        Draft202012Validator(partial).validate({'settings': {}})
        with self.assertRaises(ValidationError): Draft202012Validator(schema).validate({'settings': {}})
        checks, _ = p.consume(self.realization, self.states(), self.controls)
        self.assertEqual(checks[0]['parameters'], {'settings': {'age': '2592000s'}})
        Draft202012Validator(schema).validate(checks[0]['parameters'])
