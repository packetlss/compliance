"""ADR 0012 positive and refusal vectors for direct typed policy parameters."""
import copy
import unittest

from jsonschema import ValidationError

from tools import policy_parameters as p


class PolicyParameterTests(unittest.TestCase):
    def setUp(self):
        schema = {
            '$id': 'https://compliance.example/schemas/requirements/objective/parameters/age/v1.schema.json',
            'type': 'string',
            'pattern': '^[1-9][0-9]*[smhd]$',
            'default': '30d',
        }
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
            'evidence': [{'id': 'observation', 'type': 'test/v1',
                          'inputs_schema': {'$id': 'https://compliance.example/schemas/controls/test.check/evidence/observation/inputs/v1.schema.json', 'type': 'object',
                                            'properties': {'period': {'type': 'string'}}, 'required': ['period'], 'additionalProperties': False}}]},
            '_parameters_schema': {'$id': 'https://compliance.example/schemas/controls/test.check/parameters/v1.schema.json',
                                   'type': 'object', 'properties': {'age': {'type': 'string'}},
                                   'required': ['age'], 'additionalProperties': False}}
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

    def test_declarations_reject_noncanonical_slot_at_frozen_boundary(self):
        requirement = copy.deepcopy(self.requirement)
        declaration = requirement['spec']['parameters'].pop('age')
        declaration['schema']['$id'] = (
            'https://compliance.example/schemas/requirements/objective/'
            'parameters/bad__slot/v1.schema.json'
        )
        declaration['schema_digest'] = p.digest(declaration['schema'])
        requirement['spec']['parameters']['bad__slot'] = declaration

        with self.assertRaisesRegex(
            p.ParameterResolutionError,
            'invalid requirement parameter slot',
        ):
            p.declarations(requirement)

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

    def additive_inputs(self, *, base=None, schema_update=None, declaration_update=None):
        value_schema = {
            '$id': 'https://compliance.example/schemas/requirements/objective/parameters/allowed/v1.schema.json',
            'type': 'array',
            'items': {'type': 'string'},
            'uniqueItems': True,
        }
        value_schema.update(schema_update or {})
        declaration = {
            'required': True,
            'binding_mode': 'open',
            'schema': value_schema,
            'schema_digest': p.digest(value_schema),
            'binding_scope': ['base', 'tailored'],
            'composition': {'kind': 'additive-set'},
        }
        declaration.update(declaration_update or {})
        requirement = {
            'metadata': {'id': 'objective', 'revision': 1},
            'spec': {'parameters': {'allowed': declaration}},
        }
        pin = {
            'requirement': 'objective@1',
            'digest': p.digest(requirement),
            'required': True,
        }
        initial = p.declarations(requirement)['allowed']
        baseline = {
            'metadata': {'id': 'base', 'revision': 1},
            'spec': {
                'requirements': [pin],
                'parameter_operations': [
                    {
                        'id': 'bind-allowed',
                        'op': 'bind',
                        'target': copy.deepcopy(initial['pin']),
                        'expected_parent_fingerprint': p.fingerprint(initial),
                        'to': ['base', 'shared'] if base is None else base,
                    }
                ],
            },
            '_sources': [{'policy_source': 'test', 'path': 'base.json'}],
        }
        requirements = {'objective@1': requirement}
        baselines = {'base@1': baseline}
        return requirement, requirements, baselines

    @staticmethod
    def contribution_baseline(members, *, revision=1):
        return {
            'metadata': {'id': 'contributor', 'revision': revision},
            'spec': {
                'parameter_contributions': [{
                    'id': 'packages',
                    'target': {'requirement': 'objective', 'slot': 'allowed'},
                    'members': members,
                }],
            },
            '_sources': [{'policy_source': 'test', 'path': 'contributor.json'}],
        }

    @staticmethod
    def selected(reference, baselines, requirements, assignment):
        states, ancestry = p.resolve(reference, baselines, requirements)
        p.complete(states)
        return {
            'reference': reference,
            'applicability': {
                'group': f'group/{assignment}',
                'assignment': assignment,
                'baseline': reference,
            },
            'states': states,
            'ancestry': ancestry,
        }

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
        schema = {'$id': 'https://compliance.example/schemas/controls/test.check/parameters/v1.schema.json',
                  'type': 'object', 'properties': {'settings': {'type': 'object',
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

    def test_additive_set_canonical_union_and_complete_origin_attribution(self):
        _, requirements, baselines = self.additive_inputs(base=['shared', 'base', 'shared'])
        base_only = self.selected('base@1', baselines, requirements, 'base')
        p.compose_selected([base_only], baselines)
        self.assertEqual(base_only['states']['objective@1']['allowed']['value'], ['base', 'shared'])

        baselines['contributor@1'] = self.contribution_baseline(['zeta', 'shared', 'alpha'])
        selected = [
            self.selected('base@1', baselines, requirements, 'base'),
            self.selected('contributor@1', baselines, requirements, 'feature-a'),
            self.selected('contributor@1', baselines, requirements, 'feature-b'),
        ]
        p.compose_selected(selected, baselines)
        state = selected[0]['states']['objective@1']['allowed']
        self.assertEqual(state['value'], ['alpha', 'base', 'shared', 'zeta'])
        contribution = state['composition']['contributions'][0]
        self.assertEqual(len(contribution['applicability']), 2)
        shared = next(item for item in state['composition']['member_origins'] if item['member'] == 'shared')
        self.assertEqual([origin['kind'] for origin in shared['origins']], ['base', 'contribution'])
        self.assertEqual(
            selected[1]['states'],
            {},
            'a contribution-only baseline must not import its target requirement',
        )

    def test_additive_set_tracks_separate_contributors_and_survives_compatible_changes(self):
        _, requirements, baselines = self.additive_inputs(base=['base'])
        baselines['contributor@1'] = self.contribution_baseline(['shared'])
        second = self.contribution_baseline(['shared', 'second'], revision=2)
        second['metadata']['id'] = 'other-contributor'
        baselines['other-contributor@2'] = second
        resolutions = [
            self.selected('base@1', baselines, requirements, 'base'),
            self.selected('contributor@1', baselines, requirements, 'one'),
            self.selected('other-contributor@2', baselines, requirements, 'two'),
        ]
        p.compose_selected(resolutions, baselines)
        state = resolutions[0]['states']['objective@1']['allowed']
        shared = next(item for item in state['composition']['member_origins'] if item['member'] == 'shared')
        self.assertEqual(len(shared['origins']), 2)

        changed_requirement = copy.deepcopy(requirements['objective@1'])
        changed_requirement['metadata']['revision'] = 2
        changed_requirement['spec']['statement'] = 'Unrelated text change.'
        changed_requirement['spec']['parameters']['allowed']['schema']['maxItems'] = 8
        schema = changed_requirement['spec']['parameters']['allowed']['schema']
        changed_requirement['spec']['parameters']['allowed']['schema_digest'] = p.digest(schema)
        changed_requirements = {'objective@2': changed_requirement}
        initial = p.declarations(changed_requirement)['allowed']
        changed_base = copy.deepcopy(baselines['base@1'])
        changed_base['metadata']['revision'] = 2
        changed_base['spec']['requirements'] = [{
            'requirement': 'objective@2',
            'digest': p.digest(changed_requirement),
            'required': True,
        }]
        changed_base['spec']['parameter_operations'][0].update({
            'target': copy.deepcopy(initial['pin']),
            'expected_parent_fingerprint': p.fingerprint(initial),
            'to': ['new-base', 'base'],
        })
        changed_baselines = {
            'base@2': changed_base,
            'contributor@1': baselines['contributor@1'],
        }
        changed = [
            self.selected('base@2', changed_baselines, changed_requirements, 'base'),
            self.selected('contributor@1', changed_baselines, changed_requirements, 'one'),
        ]
        p.compose_selected(changed, changed_baselines)
        self.assertEqual(
            changed[0]['states']['objective@2']['allowed']['value'],
            ['base', 'new-base', 'shared'],
        )

    def test_additive_set_tailoring_cannot_suppress_contributions(self):
        _, requirements, baselines = self.additive_inputs(base=['base'])
        parent_state = self.selected('base@1', baselines, requirements, 'base')['states']['objective@1']['allowed']
        child = {
            'metadata': {'id': 'tailored', 'revision': 1},
            'spec': {
                'requirements': copy.deepcopy(baselines['base@1']['spec']['requirements']),
                'extends': {'baseline': 'base@1', 'digest': p.digest(p.document(baselines['base@1']))},
                'parameter_operations': [{
                    'id': 'tailor-allowed',
                    'op': 'tailor',
                    'target': copy.deepcopy(parent_state['pin']),
                    'expected_parent_fingerprint': p.fingerprint(parent_state),
                    'from': ['base'],
                    'to': [],
                    'deviation': {
                        'id': 'DEV-SET',
                        'classification': 'specialization',
                        'rationale': 'Tailor only the base.',
                        'approval_ref': 'reviewed',
                        'review_after': '2027-01-01',
                    },
                }],
            },
            '_sources': [{'policy_source': 'test', 'path': 'tailored.json'}],
        }
        baselines['tailored@1'] = child
        baselines['contributor@1'] = self.contribution_baseline(['contributed'])
        resolutions = [
            self.selected('tailored@1', baselines, requirements, 'tailored'),
            self.selected('contributor@1', baselines, requirements, 'feature'),
        ]
        p.compose_selected(resolutions, baselines)
        state = resolutions[0]['states']['objective@1']['allowed']
        self.assertEqual(state['composition']['base_value'], [])
        self.assertEqual(state['value'], ['contributed'])

    def test_additive_set_refuses_incompatible_current_policy(self):
        def resolve_with(*, schema_update=None, declaration_update=None, members=None, include_base=True):
            _, requirements, baselines = self.additive_inputs(
                schema_update=schema_update,
                declaration_update=declaration_update,
            )
            baselines['contributor@1'] = self.contribution_baseline(['member'] if members is None else members)
            resolutions = [self.selected('contributor@1', baselines, requirements, 'feature')]
            if include_base:
                resolutions.insert(0, self.selected('base@1', baselines, requirements, 'base'))
            p.compose_selected(resolutions, baselines)

        cases = {
            'member rejected by current item contract': {
                'schema_update': {'items': {'type': 'string', 'pattern': '^allowed$'}},
            },
            'completed union rejected': {'schema_update': {'maxItems': 2}},
            'missing declaration and base': {'include_base': False},
        }
        for name, kwargs in cases.items():
            with self.subTest(name=name), self.assertRaises(p.ParameterResolutionError):
                resolve_with(**kwargs)

        _, requirements, baselines = self.additive_inputs()
        atomic = copy.deepcopy(requirements['objective@1'])
        atomic['spec']['parameters']['allowed'].pop('composition')
        atomic['spec']['parameters']['allowed']['schema_digest'] = p.digest(
            atomic['spec']['parameters']['allowed']['schema']
        )
        atomic_requirements = {'objective@1': atomic}
        initial = p.declarations(atomic)['allowed']
        baselines['base@1']['spec']['requirements'][0]['digest'] = p.digest(atomic)
        baselines['base@1']['spec']['parameter_operations'][0].update(
            target=copy.deepcopy(initial['pin']),
            expected_parent_fingerprint=p.fingerprint(initial),
        )
        baselines['contributor@1'] = self.contribution_baseline(['member'])
        with self.assertRaisesRegex(p.ParameterResolutionError, 'atomic'):
            p.compose_selected([
                self.selected('base@1', baselines, atomic_requirements, 'base'),
                self.selected('contributor@1', baselines, atomic_requirements, 'feature'),
            ], baselines)

    def test_additive_set_refuses_fixed_sealed_and_ambiguous_bases(self):
        requirement, requirements, baselines = self.additive_inputs()
        baselines['contributor@1'] = self.contribution_baseline(['member'])
        initial = p.declarations(requirement)['allowed']
        sealed_state = self.selected('base@1', baselines, requirements, 'base')['states']['objective@1']['allowed']
        sealed_base = {
            'metadata': {'id': 'base', 'revision': 2},
            'spec': {
                'requirements': copy.deepcopy(baselines['base@1']['spec']['requirements']),
                'extends': {
                    'baseline': 'base@1',
                    'digest': p.digest(p.document(baselines['base@1'])),
                },
                'parameter_operations': [{
                    'id': 'seal-allowed',
                    'op': 'seal',
                    'target': copy.deepcopy(initial['pin']),
                    'expected_parent_fingerprint': p.fingerprint(sealed_state),
                }],
            },
            '_sources': [{'policy_source': 'test', 'path': 'sealed.json'}],
        }
        baselines['base@2'] = sealed_base
        with self.assertRaisesRegex(p.ParameterResolutionError, 'sealed'):
            p.compose_selected([
                self.selected('base@2', baselines, requirements, 'base'),
                self.selected('contributor@1', baselines, requirements, 'feature'),
            ], baselines)

        fixed = copy.deepcopy(requirement)
        fixed_declaration = fixed['spec']['parameters']['allowed']
        fixed_declaration.update(binding_mode='fixed', value=['fixed'])
        fixed_declaration.pop('binding_scope')
        fixed_requirements = {'objective@1': fixed}
        fixed_base = {
            'metadata': {'id': 'fixed-policy', 'revision': 1},
            'spec': {'requirements': [{
                'requirement': 'objective@1',
                'digest': p.digest(fixed),
                'required': True,
            }]},
            '_sources': [{'policy_source': 'test', 'path': 'fixed.json'}],
        }
        fixed_baselines = {
            'fixed-policy@1': fixed_base,
            'contributor@1': self.contribution_baseline(['member']),
        }
        with self.assertRaisesRegex(p.ParameterResolutionError, 'fixed or sealed'):
            p.compose_selected([
                self.selected('fixed-policy@1', fixed_baselines, fixed_requirements, 'fixed'),
                self.selected('contributor@1', fixed_baselines, fixed_requirements, 'feature'),
            ], fixed_baselines)

        _, requirements, baselines = self.additive_inputs()
        duplicate = copy.deepcopy(baselines['base@1'])
        duplicate['metadata']['id'] = 'other-base'
        duplicate['spec']['parameter_operations'][0]['id'] = 'other-bind'
        duplicate['spec']['parameter_operations'][0]['to'] = ['different']
        requirements['objective@1']['spec']['parameters']['allowed']['binding_scope'].append('other-base')
        declaration = requirements['objective@1']['spec']['parameters']['allowed']
        pin = {
            'requirement': 'objective@1',
            'digest': p.digest(requirements['objective@1']),
            'required': True,
        }
        initial = p.declarations(requirements['objective@1'])['allowed']
        for baseline in (baselines['base@1'], duplicate):
            baseline['spec']['requirements'] = [copy.deepcopy(pin)]
            baseline['spec']['parameter_operations'][0].update(
                target=copy.deepcopy(initial['pin']),
                expected_parent_fingerprint=p.fingerprint(initial),
            )
        baselines['other-base@1'] = duplicate
        with self.assertRaisesRegex(p.ParameterResolutionError, 'conflict'):
            p.compose_selected([
                self.selected('base@1', baselines, requirements, 'base'),
                self.selected('other-base@1', baselines, requirements, 'other'),
            ], baselines)

    def test_additive_set_refuses_concurrent_requirement_revisions_and_renamed_slot(self):
        requirement, requirements, baselines = self.additive_inputs()
        newer = copy.deepcopy(requirement)
        newer['metadata']['revision'] = 2
        newer['spec']['statement'] = 'A different current revision.'
        newer_declaration = newer['spec']['parameters']['allowed']
        newer_declaration['binding_scope'] = ['other-base']
        newer['spec']['parameters']['allowed']['schema_digest'] = p.digest(
            newer['spec']['parameters']['allowed']['schema']
        )
        requirements['objective@2'] = newer
        initial = p.declarations(newer)['allowed']
        other = {
            'metadata': {'id': 'other-base', 'revision': 1},
            'spec': {
                'requirements': [{
                    'requirement': 'objective@2',
                    'digest': p.digest(newer),
                    'required': True,
                }],
                'parameter_operations': [{
                    'id': 'bind-other',
                    'op': 'bind',
                    'target': copy.deepcopy(initial['pin']),
                    'expected_parent_fingerprint': p.fingerprint(initial),
                    'to': ['base'],
                }],
            },
            '_sources': [{'policy_source': 'test', 'path': 'other.json'}],
        }
        baselines['other-base@1'] = other
        with self.assertRaisesRegex(p.ParameterResolutionError, 'conflict'):
            p.compose_selected([
                self.selected('base@1', baselines, requirements, 'base'),
                self.selected('other-base@1', baselines, requirements, 'other'),
            ], baselines)

        renamed = copy.deepcopy(requirement)
        renamed['spec']['parameters']['renamed'] = renamed['spec']['parameters'].pop('allowed')
        renamed['spec']['parameters']['renamed']['schema']['$id'] = (
            'https://compliance.example/schemas/requirements/objective/'
            'parameters/renamed/v1.schema.json'
        )
        renamed['spec']['parameters']['renamed']['schema_digest'] = p.digest(
            renamed['spec']['parameters']['renamed']['schema']
        )
        renamed_requirements = {'objective@1': renamed}
        renamed_initial = p.declarations(renamed)['renamed']
        renamed_base = copy.deepcopy(baselines['base@1'])
        renamed_base['spec']['requirements'][0]['digest'] = p.digest(renamed)
        renamed_base['spec']['parameter_operations'][0].update(
            target=copy.deepcopy(renamed_initial['pin']),
            expected_parent_fingerprint=p.fingerprint(renamed_initial),
        )
        renamed_baselines = {
            'base@1': renamed_base,
            'contributor@1': self.contribution_baseline(['member']),
        }
        with self.assertRaisesRegex(p.ParameterResolutionError, 'no applicable'):
            p.compose_selected([
                self.selected('base@1', renamed_baselines, renamed_requirements, 'base'),
                self.selected('contributor@1', renamed_baselines, renamed_requirements, 'feature'),
            ], renamed_baselines)

    def test_additive_set_selection_order_is_nonsemantic(self):
        _, requirements, baselines = self.additive_inputs(base=['zeta', 'base'])
        baselines['contributor@1'] = self.contribution_baseline(['beta', 'alpha'])
        first = [
            self.selected('base@1', baselines, requirements, 'base'),
            self.selected('contributor@1', baselines, requirements, 'feature-b'),
            self.selected('contributor@1', baselines, requirements, 'feature-a'),
        ]
        second = copy.deepcopy(list(reversed(first)))
        p.compose_selected(first, baselines)
        p.compose_selected(second, baselines)
        first_state = next(item for item in first if item['reference'] == 'base@1')['states']
        second_state = next(item for item in second if item['reference'] == 'base@1')['states']
        self.assertEqual(first_state, second_state)

    def test_additive_set_authored_member_and_contribution_order_is_nonsemantic(self):
        _, requirements, first_catalog = self.additive_inputs(base=['zeta', 'base', 'zeta'])
        first_catalog['contributor@1'] = self.contribution_baseline(['beta', 'alpha', 'beta'])
        first_catalog['contributor@1']['spec']['parameter_contributions'].append({
            'id': 'more-packages',
            'target': {'requirement': 'objective', 'slot': 'allowed'},
            'members': ['delta', 'charlie'],
        })
        second_catalog = copy.deepcopy(first_catalog)
        second_catalog['base@1']['spec']['parameter_operations'][0]['to'].reverse()
        second_catalog['contributor@1']['spec']['parameter_contributions'].reverse()
        for contribution in second_catalog['contributor@1']['spec']['parameter_contributions']:
            contribution['members'].reverse()

        first = [
            self.selected('base@1', first_catalog, requirements, 'base'),
            self.selected('contributor@1', first_catalog, requirements, 'feature'),
        ]
        second = [
            self.selected('base@1', second_catalog, requirements, 'base'),
            self.selected('contributor@1', second_catalog, requirements, 'feature'),
        ]
        p.compose_selected(first, first_catalog, requirements)
        p.compose_selected(second, second_catalog, requirements)

        self.assertEqual(first, second)
        self.assertEqual(
            p.resource_digest(first_catalog['base@1'], requirements),
            p.resource_digest(second_catalog['base@1'], requirements),
        )
        self.assertEqual(
            p.resource_digest(first_catalog['contributor@1'], requirements),
            p.resource_digest(second_catalog['contributor@1'], requirements),
        )
